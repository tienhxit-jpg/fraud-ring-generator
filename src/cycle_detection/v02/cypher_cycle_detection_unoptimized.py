"""Unoptimized Pure Cypher baseline for cycle-size runtime comparison.

The query intentionally expands the original Account-Transaction-Account schema
without logical-edge aggregation, canonical rotation removal, participant-set
deduplication, business predicates, ordering, or result limits. Each matched
transaction path is streamed to a size-specific JSONL file.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from neo4j import GraphDatabase, Query
from neo4j.exceptions import Neo4jError

try:
    from src.neo4j_config import NEO4J_CONFIG
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from src.neo4j_config import NEO4J_CONFIG


DEFAULT_URI = NEO4J_CONFIG.uri
DEFAULT_USER = NEO4J_CONFIG.user
DEFAULT_PASSWORD = NEO4J_CONFIG.password
DEFAULT_DATABASE = NEO4J_CONFIG.database


def progress_log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


class UnoptimizedCypherBaseline:
    """Run direct fixed-length transaction-path queries for baseline timing."""

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        database: Optional[str] = None,
        driver: Any = "auto",
        logger=progress_log,
        heartbeat_seconds: float = 30.0,
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password)) if driver == "auto" else driver
        self.database = database
        self.logger = logger
        self.heartbeat_seconds = max(float(heartbeat_seconds), 0.0)

    def _session(self):
        return self.driver.session(database=self.database) if self.database else self.driver.session()

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    @staticmethod
    def build_query(cycle_size: int) -> str:
        if cycle_size < 2:
            raise ValueError("cycle_size must be >= 2")
        accounts = [f"a{i}" for i in range(cycle_size)]
        txs = [f"t{i}" for i in range(cycle_size)]
        lines = []
        for index in range(cycle_size):
            source = accounts[index]
            destination = accounts[(index + 1) % cycle_size]
            tx = txs[index]
            lines.append(
                f"MATCH ({source}:Account)-[:SENT]->({tx}:Transaction)-[:RECEIVED_BY]->({destination}:Account)"
            )
        checks = [
            f"{accounts[left]}.account_id <> {accounts[right]}.account_id"
            for left in range(cycle_size)
            for right in range(left + 1, cycle_size)
        ]
        participants = ", ".join(f"{account}.account_id" for account in accounts)
        transaction_ids = ", ".join(f"{tx}.transaction_id" for tx in txs)
        amount_expression = " + ".join(
            f"coalesce({tx}.amount_usd, {tx}.amount, 0.0)" for tx in txs
        )
        lines.extend(
            [
                "WHERE " + "\n  AND ".join(checks),
                f"RETURN [{participants}] AS participants,",
                f"       {cycle_size} AS cycle_size,",
                f"       [{transaction_ids}] AS transaction_ids,",
                f"       {cycle_size} AS transactions,",
                f"       {amount_expression} AS total_amount",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def timeout_for_size(cycle_size: int, query_timeout: float, cycle8_timeout: float) -> float:
        return cycle8_timeout if cycle_size == 8 else query_timeout

    @staticmethod
    def _is_skippable_error(exc: BaseException) -> bool:
        text = str(exc).lower()
        return any(term in text for term in ("timeout", "timed out", "terminated", "memorypool", "outofmemory"))

    def run_size(
        self,
        cycle_size: int,
        output_path: str | Path,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        self._log(f"cycle_size={cycle_size} started (timeout={timeout_seconds:.0f}s)")
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(self.heartbeat_seconds):
                elapsed = time.perf_counter() - started
                self._log(f"cycle_size={cycle_size} still running ({elapsed:.0f}s, rows={row_count})")

        row_count = 0
        thread = None
        if self.heartbeat_seconds > 0:
            thread = threading.Thread(target=heartbeat, daemon=True)
            thread.start()
        try:
            with output.open("w", encoding="utf-8") as handle:
                with self._session() as session:
                    result = session.run(Query(self.build_query(cycle_size), timeout=timeout_seconds))
                    for record in result:
                        handle.write(json.dumps(dict(record), ensure_ascii=False, default=str) + "\n")
                        row_count += 1
            elapsed = time.perf_counter() - started
            self._log(f"cycle_size={cycle_size} finished ({elapsed:.1f}s, rows={row_count})")
            return {
                "cycle_size": cycle_size,
                "status": "completed",
                "rows": row_count,
                "elapsed_ms": round(elapsed * 1000, 3),
                "output": str(output),
                "timeout_seconds": timeout_seconds,
            }
        except Neo4jError as exc:
            elapsed = time.perf_counter() - started
            if not self._is_skippable_error(exc):
                raise
            self._log(
                f"cycle_size={cycle_size} skipped after {elapsed:.1f}s "
                f"({type(exc).__name__})"
            )
            return {
                "cycle_size": cycle_size,
                "status": "skipped_timeout_or_resource_limit",
                "rows": row_count,
                "elapsed_ms": round(elapsed * 1000, 3),
                "output": str(output),
                "timeout_seconds": timeout_seconds,
                "error": str(exc),
            }
        finally:
            stop.set()
            if thread is not None:
                thread.join(timeout=1.0)

    def run(
        self,
        cycle_sizes: Sequence[int],
        output_dir: str | Path,
        query_timeout: float,
        cycle8_timeout: float,
        skip_cycle8: bool = False,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        results = []
        for cycle_size in cycle_sizes:
            if cycle_size == 8 and skip_cycle8:
                results.append(
                    {
                        "cycle_size": 8,
                        "status": "skipped_by_flag",
                        "rows": 0,
                        "elapsed_ms": 0.0,
                    }
                )
                continue
            timeout = self.timeout_for_size(cycle_size, query_timeout, cycle8_timeout)
            results.append(
                self.run_size(
                    cycle_size,
                    output / f"cycle_size_{cycle_size}_raw.jsonl",
                    timeout,
                )
            )
        summary = {
            "approach": "pure_cypher_unoptimized_transaction_path_baseline",
            "parameters": {
                "cycle_sizes": list(cycle_sizes),
                "query_timeout_seconds": query_timeout,
                "cycle8_timeout_seconds": cycle8_timeout,
                "skip_cycle8": skip_cycle8,
            },
            "results": results,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        (output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return summary


def parse_cycle_sizes(value: str) -> Tuple[int, ...]:
    sizes = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not sizes or any(size < 2 for size in sizes):
        raise argparse.ArgumentTypeError("cycle sizes must be integers >= 2")
    return sizes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unoptimized Pure Cypher transaction-path baseline")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--cycle-sizes", type=parse_cycle_sizes, default=(3, 5, 8))
    parser.add_argument("--query-timeout", type=float, default=900.0)
    parser.add_argument("--cycle8-timeout", type=float, default=60.0)
    parser.add_argument("--skip-cycle8", action="store_true")
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", default="data/cycledetection/cypher_unoptimized")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {str(size): UnoptimizedCypherBaseline.build_query(size) for size in args.cycle_sizes},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    baseline = UnoptimizedCypherBaseline(
        args.uri,
        args.user,
        args.password,
        database=args.database,
        logger=None if args.quiet else progress_log,
        heartbeat_seconds=args.heartbeat_seconds,
    )
    try:
        summary = baseline.run(
            args.cycle_sizes,
            args.output_dir,
            args.query_timeout,
            args.cycle8_timeout,
            skip_cycle8=args.skip_cycle8,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    finally:
        baseline.close()


if __name__ == "__main__":
    main()
