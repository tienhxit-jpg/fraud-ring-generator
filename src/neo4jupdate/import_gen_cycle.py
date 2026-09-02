"""Import ./data/genCycle CSV shards into Neo4j using the same graph schema as import_synthetic.py.

Input layout:
  data/genCycle/accounts/accounts_*.csv
  data/genCycle/transactions/transactions_*.csv
  data/genCycle/fraud/fraud_cases.csv
  data/genCycle/fraud/transactions_fraud.csv

Loaded Neo4j schema:
  (:Customer)-[:OWNS]->(:Account)
  (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)

The genCycle CSV columns are normalized to the property names expected by the
cycle-detection code and by src/neo4jupdate/import_synthetic.py:
  account risk_score       -> Account.kyc_risk_score
  tx_id                    -> Transaction.transaction_id
  src_id                   -> Transaction.source_account
  dst_id                   -> Transaction.destination_account
  amount                   -> Transaction.amount_usd
  fraud_cases participants -> Account.fraud_ring_member / fraud_ring_ids
  fraud transaction edges  -> Transaction.is_fraud / fraud_ring_id

Ground-truth fraud cases are kept as properties only. This importer does not
create (:FraudRing), MEMBER_OF, or PART_OF structures, so detectors cannot read
answer-key relationships from the graph.

Example:
  python src/neo4jupdate/import_gen_cycle.py --data-dir data/genCycle \
      --uri bolt://localhost:7687 --user neo4j --password your_password \
      --clear --verify
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    # Package import (tests, ``python -m src.neo4jupdate.import_gen_cycle``).
    from .import_synthetic import SyntheticNeo4jImporter
except ImportError:  # pragma: no cover - direct script execution fallback
    # ``python src/neo4jupdate/import_gen_cycle.py`` puts this directory on
    # sys.path, so keep the documented invocation working as well.
    from import_synthetic import SyntheticNeo4jImporter


def _parse_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value

    text = str(value).strip()
    if text == "":
        return None

    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        if "." in text or "e" in lowered:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _read_csv_rows(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cleaned: Dict[str, Any] = {}
            for key, value in row.items():
                value = value.strip() if isinstance(value, str) else value
                cleaned[key] = _parse_number(value)
            yield cleaned


def _chunked(items: Iterable[Dict[str, Any]], size: int) -> Iterator[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _sorted_csv_files(directory: Path, pattern: str) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern), key=lambda path: path.name)


@dataclass
class FraudMetadata:
    account_to_ring_ids: Dict[str, List[str]]
    edge_to_ring_ids: Dict[Tuple[str, str], List[str]]
    ring_depth: Dict[str, int]
    ring_type: Dict[str, str]

    @property
    def fraud_accounts(self) -> set[str]:
        return set(self.account_to_ring_ids)


def load_fraud_metadata(data_dir: str | Path) -> FraudMetadata:
    """Load fraud_cases.csv and derive account/edge labels for genCycle rows."""
    data_dir = Path(data_dir)
    cases_path = data_dir / "fraud" / "fraud_cases.csv"
    account_to_ring_ids: Dict[str, List[str]] = {}
    edge_to_ring_ids: Dict[Tuple[str, str], List[str]] = {}
    ring_depth: Dict[str, int] = {}
    ring_type: Dict[str, str] = {}

    if not cases_path.exists():
        return FraudMetadata(account_to_ring_ids, edge_to_ring_ids, ring_depth, ring_type)

    for row in _read_csv_rows(cases_path):
        ring_id = str(row.get("pattern_id") or "")
        if not ring_id:
            continue
        participants_text = str(row.get("involved_accounts") or "")
        participants = [item for item in participants_text.split("|") if item]
        if not participants:
            continue

        ring_depth[ring_id] = int(row.get("depth") or len(participants))
        ring_type[ring_id] = str(row.get("pattern_type") or "cycle")

        for account_id in participants:
            account_to_ring_ids.setdefault(account_id, []).append(ring_id)

        # genCycle fraud rows are emitted as directed cycle edges in participant order.
        for idx, source in enumerate(participants):
            target = participants[(idx + 1) % len(participants)]
            edge_to_ring_ids.setdefault((source, target), []).append(ring_id)

    return FraudMetadata(account_to_ring_ids, edge_to_ring_ids, ring_depth, ring_type)


def normalize_account(row: Dict[str, Any], fraud: FraudMetadata) -> Dict[str, Any]:
    account_id = str(row.get("account_id") or "")
    ring_ids = fraud.account_to_ring_ids.get(account_id, [])
    normalized = dict(row)
    normalized["account_id"] = account_id
    normalized.setdefault("customer_name", f"Customer_{account_id}")
    normalized["customer_id"] = normalized.get("customer_id") or f"customer_{account_id}"
    normalized["kyc_risk_score"] = normalized.get("kyc_risk_score", normalized.get("risk_score"))
    normalized["fraud_ring_member"] = bool(ring_ids)
    normalized["fraud_ring_ids"] = "|".join(ring_ids) if ring_ids else None
    return normalized


def normalize_transaction(
    row: Dict[str, Any],
    fraud: FraudMetadata,
    *,
    is_fraud_file: bool = False,
    include_embedding: bool = False,
) -> Dict[str, Any]:
    source = str(row.get("src_id") or row.get("source_account") or "")
    destination = str(row.get("dst_id") or row.get("destination_account") or "")
    ring_ids = fraud.edge_to_ring_ids.get((source, destination), [])
    fraud_ring_id = ring_ids[0] if ring_ids else None

    normalized: Dict[str, Any] = {
        "transaction_id": row.get("transaction_id") or row.get("tx_id"),
        "source_account": source,
        "destination_account": destination,
        "amount": row.get("amount"),
        "amount_usd": row.get("amount_usd", row.get("amount")),
        "timestamp": row.get("timestamp"),
        "date": str(row.get("timestamp") or "")[:10] or None,
        "description": row.get("description"),
        "is_fraud": 1 if (is_fraud_file or fraud_ring_id) else 0,
        "fraud_ring_id": fraud_ring_id,
        "fraud_ring_ids": "|".join(ring_ids) if ring_ids else None,
        "cycle_num": fraud_ring_id,
        "fraud_pattern_type": fraud.ring_type.get(fraud_ring_id) if fraud_ring_id else None,
        "fraud_pattern_depth": fraud.ring_depth.get(fraud_ring_id) if fraud_ring_id else None,
    }
    if include_embedding and row.get("embedding") is not None:
        # Keep the pipe-delimited vector as a string. Parsing millions of large
        # embeddings into Python float lists is slow and produces oversized Neo4j properties.
        normalized["embedding"] = row.get("embedding")
    return normalized


@dataclass
class ImportStats:
    accounts: int = 0
    transactions: int = 0
    fraud_cases: int = 0
    fraud_transactions: int = 0


class GenCycleNeo4jImporter(SyntheticNeo4jImporter):
    """Stream genCycle shards using the current synthetic importer infrastructure.

    Connection handling, schema preparation, batched database clearing, and
    session options are inherited from :class:`SyntheticNeo4jImporter`.  Only
    the genCycle-specific file discovery, normalization, and streaming import
    paths are implemented here.  This keeps both importers on the same Neo4j
    schema when the synthetic importer evolves.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        data_dir: str | Path = "data/genCycle",
        database: Optional[str] = None,
        batch_size: int = 250,
        clear_batch_size: int = 1000,
        include_embedding: bool = False,
    ) -> None:
        super().__init__(
            uri=uri,
            user=user,
            password=password,
            data_dir=data_dir,
            database=database,
            batch_size=batch_size,
            clear_batch_size=clear_batch_size,
        )
        self.include_embedding = include_embedding
        self.fraud_metadata = load_fraud_metadata(self.data_dir)

    def account_files(self) -> List[Path]:
        return _sorted_csv_files(self.data_dir / "accounts", "accounts_*.csv")

    def transaction_files(self) -> List[Path]:
        return _sorted_csv_files(self.data_dir / "transactions", "transactions_*.csv")

    def fraud_transaction_file(self) -> Optional[Path]:
        path = self.data_dir / "fraud" / "transactions_fraud.csv"
        return path if path.exists() else None


    def import_all(self, clear_first: bool = False) -> ImportStats:
        stats = ImportStats(fraud_cases=len(self.fraud_metadata.ring_depth))

        self.prepare_schema()
        if clear_first:
            self.clear_database()
            self.prepare_schema()

        account_files = self.account_files()
        transaction_files = self.transaction_files()
        fraud_transaction_file = self.fraud_transaction_file()

        if not account_files:
            raise FileNotFoundError(f"No account shards found under {self.data_dir / 'accounts'}")
        if not transaction_files and fraud_transaction_file is None:
            raise FileNotFoundError(f"No transaction CSV files found under {self.data_dir}")

        with self._get_driver().session(**self._session_kwargs()) as session:
            for path in account_files:
                stats.accounts += self._import_accounts(session, path)
            for path in transaction_files:
                stats.transactions += self._import_transactions(session, path, is_fraud_file=False)
            if fraud_transaction_file is not None:
                imported = self._import_transactions(session, fraud_transaction_file, is_fraud_file=True)
                stats.transactions += imported
                stats.fraud_transactions = imported
        return stats

    def _iter_accounts(self, path: Path) -> Iterator[Dict[str, Any]]:
        for row in _read_csv_rows(path):
            yield normalize_account(row, self.fraud_metadata)

    def _iter_transactions(self, path: Path, *, is_fraud_file: bool) -> Iterator[Dict[str, Any]]:
        for row in _read_csv_rows(path):
            yield normalize_transaction(
                row,
                self.fraud_metadata,
                is_fraud_file=is_fraud_file,
                include_embedding=self.include_embedding,
            )

    def _import_accounts(self, session, path: Path) -> int:
        query = """
        UNWIND $rows AS row
        MERGE (c:Customer {customer_id: row.customer_id})
        SET c.customer_name = row.customer_name
        MERGE (a:Account {account_id: row.account_id})
        SET a += row
        MERGE (c)-[:OWNS]->(a)
        RETURN count(a) AS count
        """

        imported = 0
        for batch in _chunked(self._iter_accounts(path), self.batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        return imported

    def _import_transactions(self, session, path: Path, *, is_fraud_file: bool) -> int:
        query = """
        UNWIND $rows AS row
        MATCH (src:Account {account_id: row.source_account})
        MATCH (dst:Account {account_id: row.destination_account})
        MERGE (t:Transaction {transaction_id: row.transaction_id})
        SET t += row
        WITH row, src, dst, t,
             coalesce(row.amount_usd, row.amount, row.original_amount, 0.0) AS amount
        MERGE (src)-[sent:SENT]->(t)
        SET sent.transaction_id = row.transaction_id,
            sent.amount = amount,
            sent.amount_usd = amount,
            sent.timestamp = row.timestamp,
            sent.is_fraud = coalesce(row.is_fraud, 0),
            sent.fraud_ring_id = row.fraud_ring_id
        MERGE (t)-[received:RECEIVED_BY]->(dst)
        SET received.transaction_id = row.transaction_id,
            received.amount = amount,
            received.amount_usd = amount,
            received.timestamp = row.timestamp,
            received.is_fraud = coalesce(row.is_fraud, 0),
            received.fraud_ring_id = row.fraud_ring_id
        RETURN count(t) AS count
        """

        imported = 0
        for batch in _chunked(self._iter_transactions(path, is_fraud_file=is_fraud_file), self.batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        return imported

    def verify_counts(self) -> Dict[str, int]:
        query = """
        MATCH (a:Account)
        WITH count(a) AS accounts
        OPTIONAL MATCH (t:Transaction)
        WITH accounts, count(t) AS transactions
        OPTIONAL MATCH (:Account)-[sent:SENT]->(:Transaction)
        WITH accounts, transactions, count(sent) AS sent_relationships
        OPTIONAL MATCH (:Transaction)-[received:RECEIVED_BY]->(:Account)
        WITH accounts, transactions, sent_relationships, count(received) AS received_relationships
        OPTIONAL MATCH (fa:Account {fraud_ring_member: true})
        WITH accounts, transactions, sent_relationships, received_relationships, count(fa) AS fraud_accounts
        OPTIONAL MATCH (ft:Transaction {is_fraud: 1})
        RETURN accounts, transactions, sent_relationships, received_relationships,
               fraud_accounts, count(ft) AS fraud_transactions
        """
        with self._get_driver().session(**self._session_kwargs()) as session:
            record = session.run(query).single()
        if record is None:
            return {}
        return {key: int(record[key] or 0) for key in record.keys()}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import genCycle data into Neo4j with synthetic-compatible schema")
    parser.add_argument("--data-dir", default="data/genCycle", help="genCycle output directory")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j Bolt URI")
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"), help="Neo4j username")
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""), help="Neo4j password")
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE"), help="Neo4j database name")
    parser.add_argument("--batch-size", type=int, default=250, help="Rows per import batch; lower this if Neo4j hits transaction memory limits")
    parser.add_argument("--clear", action="store_true", help="Delete all existing nodes before importing")
    parser.add_argument("--clear-batch-size", type=int, default=1000, help="Nodes to delete per transaction when --clear is used")
    parser.add_argument("--include-embedding", action="store_true", help="Store the large pipe-delimited embedding column on Transaction nodes")
    parser.add_argument("--verify", action="store_true", help="Print database counts after import")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.password:
        parser.error("--password or NEO4J_PASSWORD is required")

    importer = GenCycleNeo4jImporter(
        uri=args.uri,
        user=args.user,
        password=args.password,
        data_dir=args.data_dir,
        database=args.database,
        batch_size=args.batch_size,
        clear_batch_size=args.clear_batch_size,
        include_embedding=args.include_embedding,
    )

    try:
        stats = importer.import_all(clear_first=args.clear)
        print("Import completed")
        print(f"  Accounts:            {stats.accounts}")
        print(f"  Transactions:        {stats.transactions}")
        print(f"  Fraud cases:         {stats.fraud_cases}")
        print(f"  Fraud transactions:  {stats.fraud_transactions}")
        if args.verify:
            print("Verification counts:")
            for key, value in importer.verify_counts().items():
                print(f"  {key}: {value}")
        return 0
    finally:
        importer.close()


if __name__ == "__main__":
    raise SystemExit(main())
