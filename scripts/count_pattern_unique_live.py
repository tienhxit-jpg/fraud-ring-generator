"""Count exact participant sets for Cypher Pattern without writing raw transaction paths.

The query preserves the transaction-node existence semantics of the unoptimized
baseline but inserts DISTINCT after each leg. Parallel transaction choices are
therefore removed early; this does not change the final canonical participant
sets and avoids materializing tens of millions of duplicate path rows.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase, Query
from neo4j.exceptions import Neo4jError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.neo4j_config import NEO4J_CONFIG


def build_unique_count_query(cycle_size: int) -> str:
    if cycle_size < 3:
        raise ValueError("cycle_size must be >= 3")
    accounts = [f"a{i}" for i in range(cycle_size)]
    lines = [
        "MATCH (a0:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a1:Account)",
        "WHERE a0.account_id <> a1.account_id",
        "WITH DISTINCT a0, a1",
    ]
    for index in range(1, cycle_size - 1):
        current = accounts[index]
        following = accounts[index + 1]
        prior = ", ".join(f"{name}.account_id" for name in accounts[: index + 1])
        retained = ", ".join(accounts[: index + 2])
        lines.extend(
            [
                f"MATCH ({current}:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->({following}:Account)",
                f"WHERE NOT {following}.account_id IN [{prior}]",
                f"WITH DISTINCT {retained}",
            ]
        )
    retained = ", ".join(accounts)
    participant_ids = ", ".join(f"{name}.account_id" for name in accounts)
    lines.extend(
        [
            f"MATCH ({accounts[-1]}:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a0)",
            f"WITH DISTINCT {retained}",
            f"WITH DISTINCT coll.sort([{participant_ids}]) AS participants",
            "RETURN count(*) AS n_unique",
        ]
    )
    return "\n".join(lines)


def build_batched_unique_count_query(cycle_size: int) -> str:
    """Count canonical sets whose lexicographically smallest account is in a batch."""
    query = build_unique_count_query(cycle_size)
    query = query.replace(
        "WHERE a0.account_id <> a1.account_id",
        "WHERE a0.account_id IN $anchor_ids AND a0.account_id < a1.account_id",
        1,
    )
    for index in range(1, cycle_size - 1):
        following = f"a{index + 1}"
        prior = ", ".join(f"a{i}.account_id" for i in range(index + 1))
        query = query.replace(
            f"WHERE NOT {following}.account_id IN [{prior}]",
            f"WHERE NOT {following}.account_id IN [{prior}] "
            f"AND a0.account_id < {following}.account_id",
            1,
        )
    return query


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--cycle-sizes", default="3,5,8")
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--force-batched", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sizes = [int(value) for value in args.cycle_sizes.split(",") if value.strip()]

    driver = GraphDatabase.driver(
        NEO4J_CONFIG.uri,
        auth=(NEO4J_CONFIG.user, NEO4J_CONFIG.password),
    )
    results = []
    try:
        with driver.session(database=args.database) as session:
            account_ids = [
                str(record["account_id"])
                for record in session.run(
                    "MATCH (a:Account) RETURN a.account_id AS account_id ORDER BY account_id"
                )
            ]
            for size in sizes:
                query = build_unique_count_query(size)
                started = time.perf_counter()
                try:
                    if args.force_batched:
                        total = 0
                        batch_query = build_batched_unique_count_query(size)
                        for offset in range(0, len(account_ids), args.batch_size):
                            anchors = account_ids[offset : offset + args.batch_size]
                            record = session.run(
                                Query(batch_query, timeout=args.timeout),
                                anchor_ids=anchors,
                            ).single()
                            total += int(record["n_unique"])
                        n_unique = total
                        mode = f"batched_min_anchor_{args.batch_size}"
                    else:
                        record = session.run(Query(query, timeout=args.timeout)).single()
                        n_unique = int(record["n_unique"])
                        mode = "single_query"
                    results.append(
                        {
                            "cycle_size": size,
                            "status": "SUCCESS",
                            "n_unique": n_unique,
                            "mode": mode,
                            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                        }
                    )
                except Neo4jError as exc:
                    text = str(exc)
                    status = "OOM" if "MemoryPoolOutOfMemory" in text else "TIMEOUT_OR_ERROR"
                    results.append(
                        {
                            "cycle_size": size,
                            "status": status,
                            "n_unique": None,
                            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                            "error": text,
                        }
                    )
    finally:
        driver.close()

    successful = [item for item in results if item["status"] == "SUCCESS"]
    summary = {
        "approach": "cypher_pattern_exact_unique_count_early_logical_dedup",
        "database": args.database,
        "cycle_sizes": sizes,
        "results": results,
        "completed_cycle_sizes": [item["cycle_size"] for item in successful],
        "n_unique_completed_total": sum(item["n_unique"] for item in successful),
        "equivalence_note": (
            "DISTINCT removes parallel transaction choices after each logical leg; "
            "the final canonical participant sets are identical to deduplicating the "
            "full unoptimized transaction-path JSONL. Runtime is not a baseline runtime."
        ),
        "label_blind": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
