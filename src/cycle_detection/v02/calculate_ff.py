"""Calculate label-blind fragmentation metrics from raw cycle JSONL."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def canonical_participants(record: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({str(item) for item in record.get("participants", [])}))


def count_overlap_clusters(participant_sets: Sequence[tuple[str, ...]]) -> int:
    if not participant_sets:
        return 0
    parent = list(range(len(participant_sets)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    owner: dict[str, int] = {}
    for index, participants in enumerate(participant_sets):
        for participant in participants:
            if participant in owner:
                union(index, owner[participant])
            else:
                owner[participant] = index
    return len({find(index) for index in range(len(participant_sets))})


def metric_block(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw_cycles = len(records)
    unique = sorted({canonical_participants(record) for record in records if canonical_participants(record)})
    unique_sets = len(unique)
    merged_clusters = count_overlap_clusters(unique)

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 6) if denominator else None

    return {
        "raw_cycles": raw_cycles,
        "unique_sets": unique_sets,
        "merged_clusters": merged_clusters,
        "ff_enumeration": ratio(raw_cycles, unique_sets),
        "ff_fragmentation": ratio(unique_sets, merged_clusters),
        "ff_total": ratio(raw_cycles, merged_clusters),
    }


def calculate_ff(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(record) for record in records if record.get("participants")]
    by_size: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_size[str(int(row.get("cycle_size") or len(canonical_participants(row))))].append(row)
    return {
        "definition": {
            "ff_enumeration": "raw_cycles / unique_sets",
            "ff_fragmentation": "unique_sets / merged_clusters",
            "ff_total": "raw_cycles / merged_clusters",
        },
        "total": metric_block(rows),
        "by_cycle_size": {
            size: metric_block(by_size[size])
            for size in sorted(by_size, key=int)
        },
    }


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            records.append(value)
    return records


def parse_args():
    parser = argparse.ArgumentParser(description="Calculate FF metrics from raw cycle JSONL")
    parser.add_argument("--raw-jsonl", required=True)
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = calculate_ff(read_jsonl(args.raw_jsonl))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
