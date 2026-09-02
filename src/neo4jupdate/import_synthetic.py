"""Import generated synthetic fraud-ring data into Neo4j.

Expected v02/v2 input layout:
  data/synthetic/v2/raw/accounts.csv
  data/synthetic/v2/raw/merchants.csv
  data/synthetic/v2/raw/transactions.csv

The graph schema loaded by this script matches the cycle-detection code:
  (:Customer)-[:OWNS]->(:Account)
  (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)

Ground-truth fraud labels remain as plain properties on Account/Transaction
rows, but this importer intentionally does not create FraudRing nodes or
MEMBER_OF/PART_OF relationships. That keeps detection/evaluation from seeing
answer-key graph structures during cycle detection.

Example:
  python src/neo4jupdate/import_synthetic.py --data-dir data/synthetic/v2 \
      --uri bolt://localhost:7687 --user neo4j --password your_password --clear
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence


def _parse_bool(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    return value


def _parse_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value

    text = str(value).strip()
    if text == "":
        return None

    if text.lower() in {"true", "false"}:
        return text.lower() == "true"

    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except ValueError:
        return value


def _load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[Dict[str, Any]] = []
        for row in reader:
            cleaned: Dict[str, Any] = {}
            for key, value in row.items():
                value = value.strip() if isinstance(value, str) else value
                if value == "":
                    cleaned[key] = None
                    continue
                cleaned[key] = _parse_number(value)
            rows.append(cleaned)
        return rows


def _chunked(items: Sequence[Dict[str, Any]], size: int) -> Iterator[List[Dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


@dataclass
class ImportStats:
    accounts: int = 0
    merchants: int = 0
    transactions: int = 0


class SyntheticNeo4jImporter:
    """Load the v02/v2 synthetic transaction dataset into Neo4j."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        data_dir: str | Path = "data/synthetic/v2",
        database: Optional[str] = None,
        batch_size: int = 250,
        clear_batch_size: int = 1000,
    ) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.data_dir = Path(data_dir)
        self.database = database
        self.batch_size = batch_size
        self.clear_batch_size = clear_batch_size
        self.driver = None

    def _create_driver(self):
        try:
            from neo4j import GraphDatabase
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Missing dependency: install the 'neo4j' Python package before running the importer."
            ) from exc

        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def _get_driver(self):
        if self.driver is None:
            self.driver = self._create_driver()
        return self.driver

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def _session_kwargs(self) -> Dict[str, Any]:
        if self.database:
            return {"database": self.database}
        return {}

    def _resolve_raw_dir(self) -> Path:
        """Support both --data-dir data/synthetic/v2 and --data-dir .../raw."""
        if (self.data_dir / "accounts.csv").exists():
            return self.data_dir
        return self.data_dir / "raw"

    def load_data(self) -> Dict[str, Any]:
        raw_dir = self._resolve_raw_dir()

        return {
            "accounts": _load_csv(raw_dir / "accounts.csv"),
            "merchants": _load_csv(raw_dir / "merchants.csv"),
            "transactions": _load_csv(raw_dir / "transactions.csv"),
        }

    def prepare_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (n:Account) REQUIRE n.account_id IS UNIQUE",
            "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (n:Customer) REQUIRE n.customer_id IS UNIQUE",
            "CREATE CONSTRAINT merchant_id_unique IF NOT EXISTS FOR (n:Merchant) REQUIRE n.merchant_id IS UNIQUE",
            "CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS FOR (n:Transaction) REQUIRE n.transaction_id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX account_fraud_member_idx IF NOT EXISTS FOR (n:Account) ON (n.fraud_ring_member)",
            "CREATE INDEX account_kyc_risk_idx IF NOT EXISTS FOR (n:Account) ON (n.kyc_risk_score)",
            "CREATE INDEX transaction_fraud_idx IF NOT EXISTS FOR (n:Transaction) ON (n.is_fraud)",
            "CREATE INDEX transaction_ring_idx IF NOT EXISTS FOR (n:Transaction) ON (n.fraud_ring_id)",
            "CREATE INDEX transaction_date_idx IF NOT EXISTS FOR (n:Transaction) ON (n.date)",
        ]
        with self._get_driver().session(**self._session_kwargs()) as session:
            for query in constraints + indexes:
                session.run(query).consume()

    def clear_database(self) -> int:
        """Delete existing graph data in small transactions.

        A single `MATCH (n) DETACH DELETE n` can exceed Neo4j's transaction
        memory pool on this dataset. Deleting bounded chunks keeps each
        transaction small and avoids MemoryPoolOutOfMemoryError.
        """
        query = """
        MATCH (n)
        WITH n LIMIT $batch_size
        DETACH DELETE n
        RETURN count(n) AS deleted
        """
        total_deleted = 0
        with self._get_driver().session(**self._session_kwargs()) as session:
            while True:
                record = session.run(query, batch_size=self.clear_batch_size).single()
                deleted = int(record["deleted"] or 0) if record else 0
                total_deleted += deleted
                if deleted == 0:
                    break
        return total_deleted

    def import_all(self, clear_first: bool = False) -> ImportStats:
        data = self.load_data()
        stats = ImportStats()

        self.prepare_schema()

        if clear_first:
            self.clear_database()
            self.prepare_schema()

        with self._get_driver().session(**self._session_kwargs()) as session:
            stats.accounts = self._import_accounts(session, data["accounts"])
            stats.merchants = self._import_merchants(session, data["merchants"])
            stats.transactions = self._import_transactions(session, data["transactions"])
        return stats

    def _import_accounts(self, session, accounts: List[Dict[str, Any]]) -> int:
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
        for batch in _chunked(accounts, self.batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        return imported

    def _import_merchants(self, session, merchants: List[Dict[str, Any]]) -> int:
        query = """
        UNWIND $rows AS row
        MERGE (m:Merchant {merchant_id: row.merchant_id})
        SET m += row
        RETURN count(m) AS count
        """

        imported = 0
        for batch in _chunked(merchants, self.batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        return imported

    def _import_transactions(self, session, transactions: List[Dict[str, Any]]) -> int:
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
        for batch in _chunked(transactions, self.batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        return imported

    def verify_counts(self) -> Dict[str, int]:
        query = """
        MATCH (a:Account)
        WITH count(a) AS accounts
        OPTIONAL MATCH (t:Transaction)
        WITH accounts, count(t) AS transactions
        OPTIONAL MATCH (m:Merchant)
        WITH accounts, transactions, count(m) AS merchants
        OPTIONAL MATCH (:Account)-[sent:SENT]->(:Transaction)
        WITH accounts, transactions, merchants, count(sent) AS sent_relationships
        OPTIONAL MATCH (:Transaction)-[received:RECEIVED_BY]->(:Account)
        RETURN accounts, transactions, merchants,
               sent_relationships, count(received) AS received_relationships
        """
        with self._get_driver().session(**self._session_kwargs()) as session:
            record = session.run(query).single()
        if record is None:
            return {}
        return {key: int(record[key] or 0) for key in record.keys()}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import v02/v2 synthetic transaction data into Neo4j")
    parser.add_argument("--data-dir", default="data/synthetic/v2", help="Synthetic output directory, or its raw/ directory")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j Bolt URI")
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"), help="Neo4j username")
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""), help="Neo4j password")
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE"), help="Neo4j database name")
    parser.add_argument("--batch-size", type=int, default=250, help="Rows per import batch; lower this if Neo4j hits transaction memory limits")
    parser.add_argument("--clear", action="store_true", help="Delete all existing nodes before importing")
    parser.add_argument("--clear-batch-size", type=int, default=1000, help="Nodes to delete per transaction when --clear is used")
    parser.add_argument("--verify", action="store_true", help="Print database counts after import")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.password:
        parser.error("--password or NEO4J_PASSWORD is required")

    importer = SyntheticNeo4jImporter(
        uri=args.uri,
        user=args.user,
        password=args.password,
        data_dir=args.data_dir,
        database=args.database,
        batch_size=args.batch_size,
        clear_batch_size=args.clear_batch_size,
    )

    try:
        stats = importer.import_all(clear_first=args.clear)
        print("Import completed")
        print(f"  Accounts:         {stats.accounts}")
        print(f"  Merchants:        {stats.merchants}")
        print(f"  Transactions:     {stats.transactions}")
        if args.verify:
            print("Verification counts:")
            for key, value in importer.verify_counts().items():
                print(f"  {key}: {value}")
        return 0

    finally:
        importer.close()


if __name__ == "__main__":
    raise SystemExit(main())
