from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("data/cycledetection")
RUN_ID = (ROOT / ".current_d4_v02_run").read_text(encoding="utf-8").strip()
RUN_DIR = ROOT / RUN_ID


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ff_total(path: Path) -> int:
    data = load(path)
    block = data.get("total", data)
    return int(block["unique_sets"])


def unique_jsonl(path: Path) -> int:
    values: set[tuple[str, ...]] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            participants = tuple(sorted(set(map(str, row.get("participants") or []))))
            if participants:
                values.add(participants)
    return len(values)


def entry(value: int | None, status: str, scope: str, source: str, note: str | None = None) -> dict:
    result = {"n_unique": value, "status": status, "scope": scope, "source": source}
    if note:
        result["note"] = note
    return result


def main() -> None:
    d4 = load(RUN_DIR / "BENCHMARK_SUMMARY.json")
    d2_run_id = (ROOT / ".current_d2_nunique_run").read_text(encoding="utf-8").strip()
    d2_run_dir = ROOT / d2_run_id
    d2_pattern = load(d2_run_dir / "D2_N_UNIQUE_SUMMARY.json")
    data = {
        "definition": "N_unique = number of exact canonical participant sets before transitive overlap merging.",
        "datasets": {
            "D1 / d1-v03": {
                "cypher_pattern": entry(ff_total(ROOT / "d1/cypher_pattern_ff.json"), "SUCCESS", "k=3,5,8", "data/cycledetection/d1/cypher_pattern_ff.json"),
                "cypher_optimized": entry(ff_total(ROOT / "d1/cypher_optimized_ff.json"), "SUCCESS", "k=3,5,8", "data/cycledetection/d1/cypher_optimized_ff.json"),
                "hybrid_networkx": entry(ff_total(ROOT / "d1/hybrid_ff.json"), "SUCCESS", "k=3,5,8", "data/cycledetection/d1/hybrid_ff.json"),
                "gds_scc": entry(5, "SUCCESS", "bounded SCC", "data/cycledetection/d1/gds_summary.json"),
            },
            "D2 / d2-v03": {
                "cypher_pattern": entry(
                    int(d2_pattern["n_unique_completed_total"]),
                    "PARTIAL",
                    "completed k=3,5; k=8 OOM",
                    str(d2_run_dir / "D2_N_UNIQUE_SUMMARY.json"),
                    "Live label-blind exact-set count; the previously reported N_raw=15,853 is incompatible with this verified baseline and should not be reused.",
                ),
                "cypher_optimized": entry(ff_total(ROOT / "cypher_v02/ff_optimized.json"), "SUCCESS", "k=3,5,8", "data/cycledetection/cypher_v02/ff_optimized.json"),
                "hybrid_networkx": entry(ff_total(ROOT / "hybrid_v03/ff_d2.json"), "SUCCESS", "k=3,5,8", "data/cycledetection/hybrid_v03/ff_d2.json"),
                "gds_scc": entry(45, "SUCCESS", "bounded SCC", "data/cycledetection/gds_v02/gds_summary.json"),
            },
            "D3 / d3-v03": {
                "cypher_pattern": entry(unique_jsonl(ROOT / "d3/cypher_pattern_completed_raw.jsonl"), "PARTIAL", "completed k=3,5; k=8 OOM", "data/cycledetection/d3/cypher_pattern_completed_raw.jsonl"),
                "cypher_optimized": entry(unique_jsonl(ROOT / "d3/cypher_optimized_raw.jsonl"), "SUCCESS", "k=3,5,8", "data/cycledetection/d3/cypher_optimized_raw.jsonl"),
                "hybrid_networkx": entry(unique_jsonl(ROOT / "d3/hybrid_raw.jsonl"), "SUCCESS", "k=3,5,8", "data/cycledetection/d3/hybrid_raw.jsonl"),
                "gds_scc": entry(10, "SUCCESS", "bounded SCC", "data/cycledetection/d3/gds_summary_3_8.json"),
            },
            "D4 / d4-v02": {
                "cypher_pattern": entry(int(d4["methods"]["cypher_pattern"]["completed_total"]["ff"]["unique_sets"]), "PARTIAL", "completed k=4,5; k=6,7 OOM", str(RUN_DIR / "cypher_pattern/ff_completed.json")),
                "cypher_optimized": entry(int(d4["methods"]["cypher_optimized"]["completed_total"]["ff"]["unique_sets"]), "PARTIAL", "completed k=4,5; k=6,7 OOM", str(RUN_DIR / "cypher_optimized/ff_completed.json")),
                "hybrid_networkx": entry(0, "SUCCESS_EMPTY", "existing identical-fingerprint D4 benchmark", "data/cycledetection/d4_structural_20260726_191202/hybrid/summary.json"),
                "gds_scc": entry(0, "SUCCESS_EMPTY", "existing identical-fingerprint D4 benchmark", "data/cycledetection/d4_structural_20260726_191202/gds_rerun_20260726_192419/summary.json"),
            },
            "D5 / d5-v02": {
                "cypher_pattern": entry(None, "OOM", "k=4,5,6,7 all OOM", "data/cycledetection/d5_structural_20260726_193423/cypher_pattern_clean/summary.json"),
                "cypher_optimized": entry(ff_total(ROOT / "d5_structural_20260726_193423/cypher_optimized/ff_completed.json"), "PARTIAL", "completed k=4; k=5,6,7 OOM", "data/cycledetection/d5_structural_20260726_193423/cypher_optimized/ff_completed.json"),
                "hybrid_networkx": entry(0, "SUCCESS_EMPTY", "bounded SCC", "data/cycledetection/d5_structural_20260726_193423/hybrid/summary.json"),
                "gds_scc": entry(0, "SUCCESS_EMPTY", "bounded SCC", "data/cycledetection/d5_structural_20260726_193423/gds/summary.json"),
            },
        },
        "cautions": [
            "N_unique is not N_cluster: exact deduplication occurs before transitive overlap merging.",
            "N/A is used for failed or unverifiable runs; zero is reserved for methods that successfully returned an empty output.",
            "D4 values come from the new d4-v02 rerun over k=4..7 and cover completed k=4,5 only.",
        ],
    }
    json_path = RUN_DIR / "N_UNIQUE_5_DATASETS.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    methods = ("cypher_pattern", "cypher_optimized", "hybrid_networkx", "gds_scc")
    lines = [
        "N_unique trên 5 database",
        "Định nghĩa: số participant-set chính xác sau canonicalization/dedupe, trước gộp giao nhau bắc cầu.",
        "",
        "Dataset\tCypher Pattern\tCypher Optimized\tHybrid NetworkX\tGDS SCC",
    ]
    for dataset, methods_data in data["datasets"].items():
        cells = []
        for method in methods:
            item = methods_data[method]
            value = "N/A" if item["n_unique"] is None else f"{item['n_unique']:,}".replace(",", ".")
            if item["status"] not in {"SUCCESS", "SUCCESS_EMPTY"}:
                value += f" [{item['status']}]"
            cells.append(value)
        lines.append(dataset + "\t" + "\t".join(cells))
    lines.extend([
        "",
        "Ghi chú:",
        "- D2 Cypher Pattern: N_unique=16.858 trên k=3,5; k=8 OOM. Giá trị N_raw=15.853 cũ không tương thích và không nên tiếp tục dùng.",
        "- D3 Cypher Pattern: chỉ k=3,5; k=8 OOM.",
        "- D4 hai phương pháp Cypher: chỉ k=4,5; k=6,7 OOM.",
        "- D5 Cypher Optimized: chỉ k=4; Cypher Pattern OOM toàn bộ.",
    ])
    (RUN_DIR / "N_UNIQUE_5_DATASETS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(json_path), "txt": str(RUN_DIR / "N_UNIQUE_5_DATASETS.txt")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
