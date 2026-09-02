import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cycle_detection.v02.cypher_cycle_detection_v02 import CypherCycleDetectorV02, write_jsonl
from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings, load_rings

ROOT = Path("data/cycledetection")
run_id = (ROOT / ".current_d4_run").read_text().strip()
run_dir = ROOT / run_id
truth_path = run_dir / "ground_truth.json"
truth = load_rings(truth_path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def consolidate(method_dir, raw_names):
    raw = []
    for name in raw_names:
        raw.extend(load_jsonl(method_dir / name))
    unique = {}
    for row in raw:
        key = tuple(sorted(set(row.get("participants") or [])))
        if key:
            unique.setdefault(key, row)
    merged = CypherCycleDetectorV02.merge_overlapping_cycle_records(unique.values())
    write_jsonl(method_dir / "combined_completed_raw.jsonl", raw)
    write_jsonl(method_dir / "combined_completed_unique.jsonl", unique.values())
    write_jsonl(method_dir / "combined_completed_merged.jsonl", merged)
    ff = {
        "raw_cycles": len(raw),
        "unique_sets": len(unique),
        "merged_clusters": len(merged),
        "ff_enumeration": len(raw) / len(unique) if unique else None,
        "ff_fragmentation": len(unique) / len(merged) if merged else None,
        "ff_total": len(raw) / len(merged) if merged else None,
    }
    evaluation = evaluate_fraud_rings(merged, truth, min_jaccard=1.0)
    save_json(method_dir / "ff_completed.json", ff)
    save_json(method_dir / "evaluation_completed.json", evaluation)
    return ff, evaluation


opt_dir = run_dir / "cypher_optimized"
opt_summaries = {str(k): load_json(opt_dir / f"summary_{k}.json") for k in (3, 4, 5)}
opt_ff, opt_eval = consolidate(opt_dir, [f"raw_{k}.jsonl" for k in (3, 4, 5)])
opt_status = {str(k): ("SUCCESS" if (opt_dir / f"summary_{k}.json").exists() else "OOM") for k in range(3, 9)}
opt_failure_ms = {}
for k in (6, 7, 8):
    text = (opt_dir / f"run_{k}.log").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"failed after ([0-9.]+)s", text)
    opt_failure_ms[str(k)] = float(match.group(1)) * 1000 if match else None
prep_log = (opt_dir / "run_3.log").read_text(encoding="utf-8", errors="replace")
prep_match = re.search(r"aggregate preparation finished \(([0-9.]+)s, batches=(\d+), pairs=(\d+)\)", prep_log)
preparation = {
    "status": "SUCCESS",
    "elapsed_ms": float(prep_match.group(1)) * 1000 if prep_match else None,
    "batches": int(prep_match.group(2)) if prep_match else None,
    "aggregate_pairs": int(prep_match.group(3)) if prep_match else None,
    "batch_size": 1000,
    "amount_filter": None,
    "label_blind": True,
}

pattern_dir = run_dir / "cypher_pattern"
pattern_summary = load_json(pattern_dir / "summary.json")
pattern_status = {}
pattern_success_sizes = []
for item in pattern_summary["results"]:
    k = int(item["cycle_size"])
    if item["status"] == "completed":
        pattern_status[str(k)] = "SUCCESS"
        pattern_success_sizes.append(k)
    else:
        error = item.get("error", "")
        pattern_status[str(k)] = "OOM" if "MemoryPoolOutOfMemory" in error else "TIMEOUT_OR_RESOURCE_LIMIT"
pattern_ff, pattern_eval = consolidate(pattern_dir, [f"cycle_size_{k}_raw.jsonl" for k in pattern_success_sizes])

hybrid_dir = run_dir / "hybrid"
hybrid_summary = load_json(hybrid_dir / "summary.json")
hybrid_eval = evaluate_fraud_rings(load_jsonl(hybrid_dir / "merged_candidates.jsonl"), truth, min_jaccard=1.0)
save_json(hybrid_dir / "evaluation.json", hybrid_eval)

gds_dir = run_dir / "gds"
gds_status = {
    "status": "UNAVAILABLE",
    "reason": "Required procedure gds.graph.project.cypher is not installed in this database.",
    "metrics": None,
    "log": "gds/run.log",
}
save_json(gds_dir / "status.json", gds_status)

fingerprint_probe = load_json(run_dir / "fingerprint.json")
topology = load_json(run_dir / "post_detection_topology.json")
size_distribution = Counter(str(r["participant_count"]) for r in truth)
summary = {
    "benchmark_id": run_id,
    "mode": "structural_label_blind",
    "graph_fingerprint": {
        "accounts": fingerprint_probe["fingerprint"][0]["accounts"],
        "transactions": fingerprint_probe["fingerprint"][0]["transactions"],
        "logical_edges": fingerprint_probe["fingerprint"][0]["logical_edges"],
        "logical_pairs": fingerprint_probe["fingerprint"][0]["logical_pairs"],
        "ground_truth_rings": len(truth),
        "fraud_transactions": topology["boundary"]["fraud_transactions"],
        "ring_size_distribution": dict(sorted(size_distribution.items())),
        "largest_scc": topology["largest_scc_sizes"][0],
        "eligible_scc_3_12": topology["eligible_scc_3_12"],
        "exact_amount_9999_transactions": topology["amount_profile"]["exact_9999"],
    },
    "parameters": {
        "cycle_sizes": [3, 4, 5, 6, 7, 8],
        "min_pair_transactions": 1,
        "min_pair_amount": 0.0,
        "min_total_amount": 0.0,
        "limit": 0,
        "scc_window": "3..12",
        "query_timeout_seconds": 300.0,
        "label_blind": True,
    },
    "methods": {
        "gds_scc": gds_status,
        "hybrid_networkx": {"status": "SUCCESS_EMPTY", "summary": hybrid_summary, "evaluation": hybrid_eval},
        "cypher_optimized": {
            "status_by_cycle_size": opt_status,
            "preparation": preparation,
            "completed_summaries": opt_summaries,
            "failure_elapsed_ms": opt_failure_ms,
            "ff_completed": opt_ff,
            "evaluation_completed": opt_eval,
        },
        "cypher_pattern": {
            "status_by_cycle_size": pattern_status,
            "summary": pattern_summary,
            "ff_completed": pattern_ff,
            "evaluation_completed": pattern_eval,
        },
    },
    "topology_audit": topology,
    "integrity_notes": [
        "All detector amount thresholds were zero.",
        "Ground truth was read only after detector outputs were frozen.",
        "The old amount-assisted D4 run is excluded from structural conclusions.",
        f"Partial Cypher metrics cover completed sizes {','.join(map(str, pattern_success_sizes))} only.",
        "GDS is UNAVAILABLE on this live database because the required projection procedure is absent.",
    ],
}
save_json(run_dir / "BENCHMARK_SUMMARY.json", summary)
print(json.dumps({
    "run_id": run_id,
    "fingerprint": summary["graph_fingerprint"],
    "optimized": {"status": opt_status, "ff": opt_ff, "evaluation": opt_eval},
    "pattern": {"status": pattern_status, "ff": pattern_ff, "evaluation": pattern_eval},
    "hybrid": {"status": "SUCCESS_EMPTY", "elapsed_ms": hybrid_summary["elapsed_ms"]},
    "gds": gds_status["status"],
}, ensure_ascii=False, indent=2))
