"""Pure-Cypher, label-blind cycle detector v02.

This comparison script searches the Account -> Transaction -> Account graph
using only topology and non-label business attributes. It deliberately does not
read answer-key properties. Candidate cycle sizes are configurable; the default
benchmark set is 3, 5, and 8.

Raw and merged JSONL files are written separately. Ground-truth evaluation must
be performed by a separate process after these files are frozen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from neo4j import GraphDatabase, Query

try:
    from src.neo4j_config import NEO4J_CONFIG
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from src.neo4j_config import NEO4J_CONFIG


DEFAULT_URI = NEO4J_CONFIG.uri
DEFAULT_USER = NEO4J_CONFIG.user
DEFAULT_PASSWORD = NEO4J_CONFIG.password
DEFAULT_DATABASE = NEO4J_CONFIG.database


def default_progress_log(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)


class CypherCycleDetectorV02:
    """Find bounded directed account cycles with pure Cypher."""

    @staticmethod
    def available_modes() -> Tuple[str, ...]:
        return ("fixed", "component")

    @staticmethod
    def build_cycle_query(
        cycle_size: int,
        min_pair_transactions: int = 0,
        min_pair_amount: float = 0.0,
    ) -> str:
        if cycle_size < 3:
            raise ValueError("cycle_size must be at least 3")

        accounts = [f"a{i}" for i in range(cycle_size)]
        txs = [f"t{i}" for i in range(cycle_size)]
        matches = []
        for index in range(cycle_size):
            source = accounts[index]
            target = accounts[(index + 1) % cycle_size]
            tx = txs[index]
            matches.append(
                f"MATCH ({source}:Account)-[:SENT]->({tx}:Transaction)-[:RECEIVED_BY]->({target}:Account)"
            )

        distinct_checks = [
            f"{accounts[left]}.account_id <> {accounts[right]}.account_id"
            for left in range(cycle_size)
            for right in range(left + 1, cycle_size)
        ]
        canonical_ids = ", ".join(f"{account}.account_id" for account in accounts[1:])
        participant_ids = ", ".join(f"{account}.account_id" for account in accounts)
        account_nodes = ", ".join(accounts)
        edge_business_filters = []
        for index in range(cycle_size):
            source = accounts[index]
            target = accounts[(index + 1) % cycle_size]
            edge_business_filters.append(
                f"EXISTS {{ MATCH ({source})-[:SENT]->(edge_tx:Transaction)-[:RECEIVED_BY]->({target}) "
                "WITH count(edge_tx) AS pair_transactions, "
                "sum(coalesce(edge_tx.amount_usd, edge_tx.amount, 0.0)) AS pair_amount "
                "WHERE pair_transactions >= $min_pair_transactions "
                "AND pair_amount >= $min_pair_amount }"
            )

        return "\n".join(
            matches
            + [
                "WHERE " + "\n  AND ".join(distinct_checks + edge_business_filters),
                f"WITH DISTINCT [{participant_ids}] AS participants, [{account_nodes}] AS account_nodes",
                "OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)",
                "WHERE src.account_id IN participants AND dst.account_id IN participants",
                "WITH participants, account_nodes, collect(DISTINCT t) AS txs",
                "WITH participants, account_nodes, txs,",
                "     size(txs) AS group_transactions,",
                "     reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS group_total_amount,",
                "     CASE WHEN size(account_nodes) = 0 THEN 0.5",
                "          ELSE reduce(total = 0.0, account IN account_nodes | total + coalesce(account.kyc_risk_score, 0.5)) / size(account_nodes)",
                "     END AS avg_kyc_risk_score",
                "WHERE group_transactions >= $min_internal_transactions",
                "  AND group_total_amount >= $min_total_amount",
                f"RETURN participants, {cycle_size} AS cycle_size,",
                "       group_transactions AS transactions,",
                "       group_total_amount AS total_amount,",
                "       avg_kyc_risk_score,",
                "       1 AS cycles, true AS metrics_are_group_level",
                "ORDER BY total_amount DESC",
                "LIMIT $limit",
            ]
        )

    @classmethod
    def build_cycle_queries(cls, cycle_sizes: Sequence[int]) -> Dict[int, str]:
        return {size: cls.build_cycle_query(size) for size in cycle_sizes}

    @staticmethod
    def build_aggregate_cycle_query(cycle_size: int, limit: int = 0) -> str:
        """Build a label-blind query over one logical edge per account pair."""
        if cycle_size < 3:
            raise ValueError("cycle_size must be at least 3")
        accounts = [f"a{i}" for i in range(cycle_size)]
        relationships = [f"r{i}" for i in range(cycle_size)]
        matches = []
        for index in range(cycle_size):
            source = accounts[index]
            target = accounts[(index + 1) % cycle_size]
            rel = relationships[index]
            matches.append(
                f"MATCH ({source}:Account)-[{rel}:TRANSFER_AGG]->({target}:Account)"
            )
            matches.append(
                f"WHERE {rel}.transaction_count >= $min_pair_transactions "
                f"AND {rel}.total_amount >= $min_pair_amount"
            )
        distinct_checks = [
            f"{accounts[left]}.account_id <> {accounts[right]}.account_id"
            for left in range(cycle_size)
            for right in range(left + 1, cycle_size)
        ]
        participant_ids = ", ".join(f"{account}.account_id" for account in accounts)
        canonical_ids = ", ".join(f"{account}.account_id" for account in accounts[1:])
        rel_list = ", ".join(relationships)
        query = matches + [
            "WITH " + ", ".join(accounts + relationships),
            "WHERE " + "\n  AND ".join(distinct_checks),
            "  AND a0.account_id = reduce(",
            "      min_id = a0.account_id,",
            f"      id IN [{canonical_ids}] | CASE WHEN id < min_id THEN id ELSE min_id END",
            "  )",
            f"WITH DISTINCT [{participant_ids}] AS participants, [{rel_list}] AS rels",
            "WITH participants, rels,",
            "     reduce(total = 0, r IN rels | total + coalesce(r.transaction_count, 0)) AS transactions,",
            "     reduce(total = 0.0, r IN rels | total + coalesce(r.total_amount, 0.0)) AS total_amount",
            "WHERE transactions >= $min_internal_transactions",
            "  AND total_amount >= $min_total_amount",
            f"RETURN DISTINCT participants, {cycle_size} AS cycle_size,",
            "       transactions, total_amount,",
            "       1 AS cycles,",
            "       true AS metrics_are_group_level",
        ]
        if limit > 0:
            query.append("LIMIT $limit")
        return "\n".join(query)

    def __init__(
        self,
        uri=DEFAULT_URI,
        user=DEFAULT_USER,
        password=DEFAULT_PASSWORD,
        database=None,
        driver="auto",
        progress_callback=default_progress_log,
        progress_interval: float = 30.0,
    ):
        self.driver = GraphDatabase.driver(uri, auth=(user, password)) if driver == "auto" else driver
        self.database = database
        self.progress_callback = progress_callback
        self.progress_interval = max(float(progress_interval), 0.0)
        self.last_raw_results: List[Dict[str, Any]] = []
        self.last_merged_results: List[Dict[str, Any]] = []

    def _log(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _session(self):
        return self.driver.session(database=self.database) if self.database else self.driver.session()

    def close(self):
        if self.driver is not None:
            self.driver.close()

    def prepare_aggregate_graph(self, rebuild: bool = True, batch_size: int = 1000) -> int:
        """Create label-blind TRANSFER_AGG relationships in bounded source batches."""
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        self._log(f"aggregate preparation started (rebuild={rebuild}, batch_size={batch_size})")
        started = time.perf_counter()
        with self._session() as session:
            if rebuild:
                session.run("MATCH ()-[r:TRANSFER_AGG]->() DELETE r").consume()
        pairs = 0
        batches = 0
        after_source_id = -1
        while True:
            with self._session() as session:
                page = session.run(
                    """
                    CALL {
                        MATCH (src:Account)
                        WHERE id(src) > $after_source_id
                        RETURN id(src) AS source_id
                        ORDER BY source_id
                        LIMIT $batch_size
                    }
                    RETURN collect(source_id) AS source_ids,
                           max(source_id) AS last_source_id
                    """,
                    after_source_id=after_source_id,
                    batch_size=int(batch_size),
                ).single()
            source_ids = list(page["source_ids"] or []) if page else []
            if not source_ids:
                break
            with self._session() as session:
                record = session.run(
                    """
                    MATCH (src:Account)
                    WHERE id(src) IN $source_ids
                    MATCH (src)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
                    WHERE src <> dst
                    WITH src, dst,
                         count(t) AS transaction_count,
                         sum(coalesce(t.amount_usd, t.amount, 0.0)) AS total_amount,
                         min(t.timestamp) AS first_timestamp,
                         max(t.timestamp) AS last_timestamp
                    MERGE (src)-[r:TRANSFER_AGG]->(dst)
                    SET r.transaction_count = transaction_count,
                        r.total_amount = total_amount,
                        r.first_timestamp = first_timestamp,
                        r.last_timestamp = last_timestamp
                    RETURN count(r) AS aggregate_pairs
                    """,
                    source_ids=source_ids,
                ).single()
            pairs += int(record["aggregate_pairs"] or 0) if record else 0
            batches += 1
            after_source_id = int(page.get("last_source_id") or max(source_ids))
            self._log(f"aggregate batch={batches} finished (pairs_total={pairs})")
        self._log(
            f"aggregate preparation finished ({time.perf_counter() - started:.1f}s, "
            f"batches={batches}, pairs={pairs})"
        )
        return pairs

    def get_graph_stats(self) -> Dict[str, int]:
        with self._session() as session:
            record = session.run(
                """
                MATCH (a:Account)
                WITH count(a) AS accounts
                OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
                RETURN accounts, count(DISTINCT t) AS transactions
                """
            ).single()
        if record is None:
            return {"nodes": 0, "transactions": 0}
        return {"nodes": int(record["accounts"] or 0), "transactions": int(record["transactions"] or 0)}

    def run_query(
        self,
        cycle_size: int,
        limit: int,
        min_pair_transactions: int,
        min_pair_amount: float,
        min_internal_transactions: int,
        min_total_amount: float,
        graph_mode: str = "aggregate",
        query_timeout: float = 0.0,
    ) -> List[Dict[str, Any]]:
        if graph_mode == "aggregate":
            query = self.build_aggregate_cycle_query(cycle_size, limit=limit)
        elif graph_mode == "transactions":
            query = self.build_cycle_query(cycle_size)
            if limit <= 0:
                query = "\n".join(line for line in query.splitlines() if "LIMIT $limit" not in line)
        else:
            raise ValueError("graph_mode must be 'aggregate' or 'transactions'")
        started = time.perf_counter()
        limit_text = "all" if limit <= 0 else str(limit)
        self._log(f"cycle_size={cycle_size} started (limit={limit_text})")
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            while not stop_heartbeat.wait(self.progress_interval):
                elapsed = time.perf_counter() - started
                self._log(f"cycle_size={cycle_size} still running ({elapsed:.0f}s)")

        heartbeat_thread = None
        if self.progress_interval > 0:
            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()
        try:
            with self._session() as session:
                submitted_query = Query(query, timeout=query_timeout) if query_timeout > 0 else query
                result = session.run(
                    submitted_query,
                    limit=limit,
                    min_pair_transactions=int(min_pair_transactions),
                    min_pair_amount=float(min_pair_amount),
                    min_internal_transactions=int(min_internal_transactions),
                    min_total_amount=float(min_total_amount),
                )
                rows = [dict(record) for record in result]
            elapsed = time.perf_counter() - started
            self._log(f"cycle_size={cycle_size} finished ({elapsed:.1f}s, rows={len(rows)})")
            return rows
        except Exception as exc:
            elapsed = time.perf_counter() - started
            self._log(f"cycle_size={cycle_size} failed after {elapsed:.1f}s: {type(exc).__name__}")
            raise
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=1.0)

    def detect(
        self,
        cycle_sizes: Sequence[int] = (3, 5, 8),
        limit: int = 500,
        min_pair_transactions: int = 0,
        min_pair_amount: float = 0.0,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
        merge_overlapping: bool = True,
        graph_mode: str = "aggregate",
        query_timeout: float = 0.0,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        self._log(
            f"detection started (cycle_sizes={','.join(str(size) for size in cycle_sizes)}, "
            f"limit={'all' if limit <= 0 else limit})"
        )
        raw: List[Dict[str, Any]] = []
        per_size: Dict[str, int] = {}
        for cycle_size in cycle_sizes:
            rows = self.run_query(
                cycle_size,
                limit,
                min_pair_transactions,
                min_pair_amount,
                min_internal_transactions,
                min_total_amount,
                graph_mode,
                query_timeout,
            )
            raw.extend(rows)
            per_size[str(cycle_size)] = len(rows)
        self._log(f"cycle queries completed (raw_rows={len(raw)}); merging={merge_overlapping}")
        merged = self.merge_overlapping_cycle_records(raw) if merge_overlapping else list(raw)
        self._log(f"detection finished (raw_rows={len(raw)}, merged_rows={len(merged)})")
        self.last_raw_results = raw
        self.last_merged_results = merged
        return {
            "approach": "pure_cypher_label_blind_v02",
            "parameters": {
                "cycle_sizes": list(cycle_sizes),
                "limit_per_size": limit,
                "min_pair_transactions": min_pair_transactions,
                "min_pair_amount": min_pair_amount,
                "min_internal_transactions": min_internal_transactions,
                "min_total_amount": min_total_amount,
                "merge_overlapping": merge_overlapping,
                "graph_mode": graph_mode,
                "query_timeout_seconds": query_timeout,
            },
            "raw_result_count": len(raw),
            "merged_result_count": len(merged),
            "results_by_cycle_size": per_size,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "notes": [
                "Detection queries only topology, amounts, timestamps through the transaction model, and non-label KYC attributes.",
                "Raw and merged candidate files must be evaluated separately after detection.",
            ],
        }

    @staticmethod
    def merge_overlapping_cycle_records(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        rows = [dict(record) for record in records if record.get("participants")]
        if not rows:
            return []
        parent = list(range(len(rows)))

        def find(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left, right):
            left, right = find(left), find(right)
            if left != right:
                parent[right] = left

        owner: Dict[str, int] = {}
        sets: List[set] = []
        for index, row in enumerate(rows):
            participants = {str(item) for item in row.get("participants", [])}
            sets.append(participants)
            for participant in participants:
                if participant in owner:
                    union(index, owner[participant])
                else:
                    owner[participant] = index

        grouped: Dict[int, List[int]] = {}
        for index in range(len(rows)):
            grouped.setdefault(find(index), []).append(index)

        merged = []
        for member_indexes in grouped.values():
            participants = sorted(set().union(*(sets[index] for index in member_indexes)))
            source = [rows[index] for index in member_indexes]
            merged.append(
                {
                    "participants": participants,
                    "participant_count": len(participants),
                    "cycle_size": len(participants),
                    "transactions": max(int(item.get("transactions", 0) or 0) for item in source),
                    "total_amount": max(float(item.get("total_amount", 0.0) or 0.0) for item in source),
                    "cycles": sum(int(item.get("cycles", 1) or 1) for item in source),
                    "fragment_count": len(source),
                    "candidate_cycle_sizes": sorted({int(item.get("cycle_size", 0)) for item in source}),
                    "method": "pure_cypher_overlap_merge",
                }
            )
        return sorted(merged, key=lambda item: (item["total_amount"], item["cycles"]), reverse=True)

    @staticmethod
    def available_query_specs(cycle_sizes=(3, 5, 8), graph_mode="aggregate", limit=0) -> List[Dict[str, str]]:
        return [
            {
                "name": f"fixed_{size}",
                "description": f"{size}-account directed cycles",
                "cypher": (
                    CypherCycleDetectorV02.build_aggregate_cycle_query(size, limit=limit)
                    if graph_mode == "aggregate"
                    else CypherCycleDetectorV02.build_cycle_query(size)
                ),
            }
            for size in cycle_sizes
        ]


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def parse_cycle_sizes(value: str) -> Tuple[int, ...]:
    sizes = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    if not sizes or any(size < 3 for size in sizes):
        raise argparse.ArgumentTypeError("cycle sizes must be integers >= 3")
    return sizes


def parse_args():
    parser = argparse.ArgumentParser(description="Pure Cypher label-blind cycle detection v02")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--dataset-dir", default="data/synthetic/v03")
    parser.add_argument("--cycle-sizes", type=parse_cycle_sizes, default=(3, 5, 8))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--graph-mode", choices=("aggregate", "transactions"), default="aggregate")
    parser.add_argument("--prepare-aggregates", action="store_true")
    parser.add_argument("--keep-existing-aggregates", action="store_true")
    parser.add_argument("--aggregate-batch-size", type=int, default=1000)
    parser.add_argument("--min-pair-transactions", type=int, default=3)
    parser.add_argument("--min-pair-amount", type=float, default=0.0)
    parser.add_argument("--min-internal-transactions", type=int, default=0)
    parser.add_argument("--min-total-amount", type=float, default=0.0)
    parser.add_argument("--raw-jsonl-out", default="data/cycledetection/cypher_v02/raw_candidates.jsonl")
    parser.add_argument("--merged-jsonl-out", default="data/cycledetection/cypher_v02/merged_candidates.jsonl")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        help="Seconds between heartbeat logs while Neo4j is running a query; 0 disables heartbeat",
    )
    parser.add_argument(
        "--query-timeout",
        type=float,
        default=0.0,
        help="Neo4j transaction timeout in seconds for each cycle-size query; 0 disables it",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable progress logs")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dry_run:
        print(
            json.dumps(
                CypherCycleDetectorV02.available_query_specs(
                    args.cycle_sizes, graph_mode=args.graph_mode, limit=args.limit
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    detector = CypherCycleDetectorV02(
        args.uri,
        args.user,
        args.password,
        database=args.database,
        progress_callback=None if args.quiet else default_progress_log,
        progress_interval=args.progress_interval,
    )
    try:
        if args.prepare_aggregates:
            detector.prepare_aggregate_graph(
                rebuild=not args.keep_existing_aggregates,
                batch_size=args.aggregate_batch_size,
            )
        summary = detector.detect(
            cycle_sizes=args.cycle_sizes,
            limit=args.limit,
            min_pair_transactions=args.min_pair_transactions,
            min_pair_amount=args.min_pair_amount,
            min_internal_transactions=args.min_internal_transactions,
            min_total_amount=args.min_total_amount,
            merge_overlapping=not args.no_merge,
            graph_mode=args.graph_mode,
            query_timeout=args.query_timeout,
        )
        summary["dataset_dir"] = args.dataset_dir
        raw_count = write_jsonl(args.raw_jsonl_out, detector.last_raw_results)
        merged_count = write_jsonl(args.merged_jsonl_out, detector.last_merged_results)
        detector._log(f"outputs written (raw={raw_count}, merged={merged_count})")
        summary["raw_jsonl_count"] = raw_count
        summary["merged_jsonl_count"] = merged_count
        if args.json_out:
            output = Path(args.json_out)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        detector.close()


if __name__ == "__main__":
    main()
