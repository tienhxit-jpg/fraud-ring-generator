from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cycle_detection.v02.cypher_cycle_detection_v02 import (  # noqa: E402
    CypherCycleDetectorV02,
    write_jsonl,
)
from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings  # noqa: E402

ROOT = Path("data/cycledetection")
RUN_ID = (ROOT / ".current_d4_v02_run").read_text(encoding="utf-8").strip()
RUN_DIR = ROOT / RUN_ID
CYCLE_SIZES = (4, 5, 6, 7)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def save_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_participant_sets(rows: list[dict]) -> dict[tuple[str, ...], dict]:
    result: dict[tuple[str, ...], dict] = {}
    for row in rows:
        key = tuple(sorted(set(map(str, row.get("participants") or []))))
        if key:
            result.setdefault(key, row)
    return result


def consolidate(method_dir: Path, raw_paths: list[Path], truth: list[dict]) -> dict:
    rows = [row for path in raw_paths for row in load_jsonl(path)]
    unique = unique_participant_sets(rows)
    merged = CypherCycleDetectorV02.merge_overlapping_cycle_records(unique.values())
    write_jsonl(method_dir / "combined_completed_raw.jsonl", rows)
    write_jsonl(method_dir / "combined_completed_unique.jsonl", unique.values())
    write_jsonl(method_dir / "combined_completed_merged.jsonl", merged)
    ff = {
        "raw_cycles": len(rows),
        "unique_sets": len(unique),
        "merged_clusters": len(merged),
        "ff_enumeration": len(rows) / len(unique) if unique else None,
        "ff_fragmentation": len(unique) / len(merged) if merged else None,
        "ff_total": len(rows) / len(merged) if merged else None,
    }
    evaluation = evaluate_fraud_rings(merged, truth, min_jaccard=1.0)
    save_json(method_dir / "ff_completed.json", ff)
    save_json(method_dir / "evaluation_completed.json", evaluation)
    return {"ff": ff, "evaluation": evaluation}


def freeze_ground_truth() -> tuple[list[dict], int]:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    transfer_agg_after = 0
    try:
        with driver.session(database="d4-v02") as session:
            for record in session.run(
                "MATCH (a:Account) WHERE a.fraud_ring_ids IS NOT NULL "
                "RETURN a.fraud_ring_ids AS ring_id, a.account_id AS account_id "
                "ORDER BY ring_id, account_id"
            ):
                grouped[str(record["ring_id"])].append(str(record["account_id"]))
            transfer_agg_after = session.run(
                "MATCH ()-[r:TRANSFER_AGG]->() RETURN count(r) AS count"
            ).single()["count"]
    finally:
        driver.close()
    rings = []
    for ring_id, participants in sorted(grouped.items()):
        participants = sorted(set(participants))
        rings.append(
            {
                "ring_id": ring_id,
                "ring_type": "ground_truth",
                "participants": participants,
                "participant_count": len(participants),
                "transactions": None,
                "total_amount": None,
                "pattern": "ground_truth",
                "cycles": 1,
            }
        )
    save_json(RUN_DIR / "ground_truth.json", {"rings": rings})
    return rings, int(transfer_agg_after)


def status_from_error(text: str) -> str:
    if "MemoryPoolOutOfMemoryError" in text:
        return "OOM"
    if "TimeOut" in text or "timeout" in text.lower():
        return "TIMEOUT"
    return "FAILED"


def elapsed_from_log(text: str) -> float | None:
    match = re.search(r"failed after ([0-9.]+)s", text)
    return float(match.group(1)) if match else None


def count_file(path: Path) -> tuple[int, int]:
    rows = load_jsonl(path)
    return len(rows), len(unique_participant_sets(rows))


def main() -> None:
    truth, transfer_agg_after = freeze_ground_truth()
    fingerprint = load_json(RUN_DIR / "fingerprint.json")["fingerprint"][0]

    optimized_dir = RUN_DIR / "cypher_optimized"
    optimized_by_k: dict[str, dict] = {}
    optimized_success: list[int] = []
    for k in CYCLE_SIZES:
        summary_path = optimized_dir / f"summary_{k}.json"
        if summary_path.exists():
            item = load_json(summary_path)
            raw, unique = count_file(optimized_dir / f"raw_{k}.jsonl")
            optimized_by_k[str(k)] = {
                "status": "SUCCESS",
                "runtime_seconds": item["elapsed_ms"] / 1000,
                "n_raw": raw,
                "n_unique": unique,
            }
            optimized_success.append(k)
        else:
            text = (optimized_dir / f"run_{k}.log").read_text(encoding="utf-8", errors="replace")
            optimized_by_k[str(k)] = {
                "status": status_from_error(text),
                "runtime_seconds": elapsed_from_log(text),
                "n_raw": None,
                "n_unique": None,
            }
    optimized_total = consolidate(
        optimized_dir,
        [optimized_dir / f"raw_{k}.jsonl" for k in optimized_success],
        truth,
    )

    pattern_dir = RUN_DIR / "cypher_pattern"
    pattern_summary = load_json(pattern_dir / "summary.json")
    pattern_by_k: dict[str, dict] = {}
    pattern_success: list[int] = []
    for result in pattern_summary["results"]:
        k = int(result["cycle_size"])
        if result["status"] == "completed":
            raw, unique = count_file(pattern_dir / f"cycle_size_{k}_raw.jsonl")
            pattern_by_k[str(k)] = {
                "status": "SUCCESS",
                "runtime_seconds": result["elapsed_ms"] / 1000,
                "n_raw": raw,
                "n_unique": unique,
            }
            pattern_success.append(k)
        else:
            pattern_by_k[str(k)] = {
                "status": status_from_error(result.get("error", "")),
                "runtime_seconds": result["elapsed_ms"] / 1000,
                "n_raw": None,
                "n_unique": None,
            }
    pattern_total = consolidate(
        pattern_dir,
        [pattern_dir / f"cycle_size_{k}_raw.jsonl" for k in pattern_success],
        truth,
    )

    benchmark = {
        "benchmark_id": RUN_ID,
        "database": "d4-v02",
        "mode": "label_blind_k4_k7",
        "fingerprint": fingerprint,
        "database_side_effects": {
            "transfer_agg_before": fingerprint["transfer_agg"],
            "transfer_agg_after": transfer_agg_after,
        },
        "ground_truth": {
            "ring_count": len(truth),
            "size_distribution": {
                str(size): sum(r["participant_count"] == size for r in truth)
                for size in sorted({r["participant_count"] for r in truth})
            },
        },
        "parameters": {
            "cycle_sizes": list(CYCLE_SIZES),
            "limit": 0,
            "query_timeout_seconds": 300,
            "min_pair_transactions": 1,
            "min_pair_amount": 0,
            "min_internal_transactions": 0,
            "min_total_amount": 0,
            "label_blind": True,
        },
        "methods": {
            "cypher_pattern": {
                "by_cycle_size": pattern_by_k,
                "completed_cycle_sizes": pattern_success,
                "completed_total": pattern_total,
            },
            "cypher_optimized": {
                "by_cycle_size": optimized_by_k,
                "completed_cycle_sizes": optimized_success,
                "completed_total": optimized_total,
            },
        },
        "notes": [
            "N_unique is the number of exact canonical participant sets before transitive overlap merging.",
            "Metrics marked completed_total cover successful cycle sizes only.",
            "Ground truth was read only after detector outputs were frozen.",
        ],
    }
    save_json(RUN_DIR / "BENCHMARK_SUMMARY.json", benchmark)
    print(json.dumps(benchmark, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
