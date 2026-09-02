import json
from pathlib import Path

root = Path("data/cycledetection")
run_id = (root / ".current_d4_run").read_text().strip()
run_dir = root / run_id
rerun = (run_dir / ".current_gds_rerun").read_text().strip()
rerun_dir = run_dir / rerun
summary = json.loads((rerun_dir / "summary.json").read_text(encoding="utf-8"))
evaluation = json.loads((rerun_dir / "evaluation.json").read_text(encoding="utf-8"))

benchmark_path = run_dir / "BENCHMARK_SUMMARY.json"
benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
gds_record = {
    "status": "SUCCESS_EMPTY",
    "artifact": rerun,
    "summary": summary,
    "evaluation": evaluation,
}
benchmark["methods"]["gds_scc"] = gds_record
benchmark["gds_rerun"] = gds_record
notes = [
    note
    for note in benchmark.get("integrity_notes", [])
    if "GDS is UNAVAILABLE" not in note and "projection procedure is absent" not in note
]
notes.append(
    "GDS rerun succeeded after the required procedures became available; empty output is SUCCESS_EMPTY, not UNAVAILABLE."
)
benchmark["integrity_notes"] = notes
benchmark_path.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

combined_path = root / "benchmark_structural_d4_d5_20260726.json"
combined = json.loads(combined_path.read_text(encoding="utf-8"))
combined["D4"]["observations"]["gds"] = "SUCCESS_EMPTY"
combined["D4"]["gds_rerun_artifact"] = str((rerun_dir / "summary.json").as_posix())
combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps({
    "run_id": run_id,
    "rerun": rerun,
    "status": "SUCCESS_EMPTY",
    "elapsed_ms": summary["elapsed_ms"],
    "project_ms": summary["projection"]["projectMillis"],
    "result_count": summary["result_count"],
    "evaluation": evaluation,
}, ensure_ascii=False, indent=2))
