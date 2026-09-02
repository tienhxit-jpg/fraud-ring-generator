"""Cycle-fragment-level evaluation for fraud-ring detection outputs.

Ring-level metrics count one detected group as one prediction. This module adds a
second view that counts the cycle/path fragments inside each ring. It is useful
when comparing fragmented cycle detectors against component-level outputs.

Because most ground-truth files in this project store only a ring-level
``cycles`` count, not every explicit path, this metric compares fragment counts
per matched participant set:

- matched ring: TP += min(predicted_fragments, ground_truth_fragments)
- matched ring with extra predicted fragments: FP += predicted - ground_truth
- matched ring with missing fragments: FN += ground_truth - predicted
- unmatched predicted ring: FP += predicted_fragments
- unmatched ground-truth ring: FN += ground_truth_fragments

The result should be reported as ``cycle-fragment-level`` F1, not as exact
path-level F1, unless both files contain explicit ``cycle_instances``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

try:
    from src.evaluation.fraud_ring_metrics import (
        Ring,
        canonical_participant_key,
        classification_metrics,
        filter_predicted_rings,
        load_rings,
        match_rings,
    )
except ModuleNotFoundError:  # Allows direct execution from src/evaluation
    from fraud_ring_metrics import (  # type: ignore
        Ring,
        canonical_participant_key,
        classification_metrics,
        filter_predicted_rings,
        load_rings,
        match_rings,
    )


def _as_positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def cycle_fragment_count(ring: Mapping[str, Any]) -> int:
    """Return how many cycle/path fragments a ring record represents.

    Priority:
    1. explicit ``cycle_instances`` list length;
    2. ``fragment_count`` from component-merge outputs;
    3. ``cycles`` from detector/ground-truth summaries;
    4. fallback to one fragment for a plain cycle/ring row.
    """

    cycle_instances = ring.get("cycle_instances")
    if isinstance(cycle_instances, list):
        return max(len(cycle_instances), 1)
    if ring.get("fragment_count") is not None:
        return _as_positive_int(ring.get("fragment_count"), default=1)
    if ring.get("cycles") is not None:
        return _as_positive_int(ring.get("cycles"), default=1)
    return 1


def _ring_by_participant_key(rings: Iterable[Ring]) -> Dict[tuple[str, ...], Ring]:
    keyed: Dict[tuple[str, ...], Ring] = {}
    for ring in rings:
        key = canonical_participant_key(ring.get("participants") or [])
        if key:
            keyed.setdefault(key, ring)
    return keyed


def _prefixed_cycle_metrics(true_positives: int, false_positives: int, false_negatives: int) -> Dict[str, float]:
    base = classification_metrics(true_positives, false_positives, false_negatives)
    return {
        "cycle_precision": base["precision"],
        "cycle_recall": base["recall"],
        "cycle_f1": base["f1"],
    }


def evaluate_cycle_fragments(
    predicted_rings: Iterable[Dict[str, Any]],
    ground_truth_rings: Iterable[Dict[str, Any]],
    min_jaccard: float = 1.0,
) -> Dict[str, Any]:
    """Evaluate predicted outputs by counting ring-internal cycle fragments."""

    predicted_list = list(predicted_rings)
    truth_list = list(ground_truth_rings)
    matches, false_positive_rings, false_negative_rings = match_rings(
        predicted_list,
        truth_list,
        min_jaccard=min_jaccard,
    )

    predicted_by_key = _ring_by_participant_key(predicted_list)
    truth_by_key = _ring_by_participant_key(truth_list)

    cycle_tp = 0
    cycle_fp = 0
    cycle_fn = 0
    matched_details = []

    for match in matches:
        predicted_ring = predicted_by_key[match.predicted_participants]
        truth_ring = truth_by_key[match.ground_truth_participants]
        predicted_fragments = cycle_fragment_count(predicted_ring)
        truth_fragments = cycle_fragment_count(truth_ring)
        true_positive_fragments = min(predicted_fragments, truth_fragments)
        false_positive_fragments = max(predicted_fragments - truth_fragments, 0)
        false_negative_fragments = max(truth_fragments - predicted_fragments, 0)

        cycle_tp += true_positive_fragments
        cycle_fp += false_positive_fragments
        cycle_fn += false_negative_fragments
        matched_details.append(
            {
                "predicted_ring_id": match.predicted_ring_id,
                "ground_truth_ring_id": match.ground_truth_ring_id,
                "predicted_participants": match.predicted_participants,
                "ground_truth_participants": match.ground_truth_participants,
                "jaccard": match.jaccard,
                "predicted_fragments": predicted_fragments,
                "ground_truth_fragments": truth_fragments,
                "cycle_true_positives": true_positive_fragments,
                "cycle_false_positives": false_positive_fragments,
                "cycle_false_negatives": false_negative_fragments,
            }
        )

    for ring in false_positive_rings:
        cycle_fp += cycle_fragment_count(ring)
    for ring in false_negative_rings:
        cycle_fn += cycle_fragment_count(ring)

    metrics = _prefixed_cycle_metrics(cycle_tp, cycle_fp, cycle_fn)
    predicted_total = sum(cycle_fragment_count(ring) for ring in predicted_by_key.values())
    truth_total = sum(cycle_fragment_count(ring) for ring in truth_by_key.values())

    return {
        **metrics,
        "cycle_true_positives": cycle_tp,
        "cycle_false_positives": cycle_fp,
        "cycle_false_negatives": cycle_fn,
        "predicted_cycle_fragments": predicted_total,
        "ground_truth_cycle_fragments": truth_total,
        "matched_ring_count": len(matches),
        "false_positive_ring_count": len(false_positive_rings),
        "false_negative_ring_count": len(false_negative_rings),
        "min_jaccard": min_jaccard,
        "metric_level": "cycle_fragment",
        "counting_rule": "TP per matched ring is min(predicted_fragments, ground_truth_fragments); extra predicted fragments are FP; missing fragments are FN.",
        "matches": matched_details,
        "false_positive_ring_ids": [ring.get("ring_id") for ring in false_positive_rings],
        "false_negative_ring_ids": [ring.get("ring_id") for ring in false_negative_rings],
    }


def evaluate_cycle_fragment_file(
    predictions_path: str | Path,
    ground_truth_path: str | Path,
    min_jaccard: float = 1.0,
    predicted_label_field: str | None = "is_fraud_ring",
    keep_unlabeled: bool = True,
) -> Dict[str, Any]:
    """Load prediction/ground-truth files and compute cycle-fragment metrics."""

    predicted_rings = filter_predicted_rings(
        load_rings(predictions_path),
        predicted_label_field=predicted_label_field,
        keep_unlabeled=keep_unlabeled,
    )
    ground_truth_rings = load_rings(ground_truth_path)
    return evaluate_cycle_fragments(predicted_rings, ground_truth_rings, min_jaccard=min_jaccard)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate fraud-ring outputs at cycle-fragment level.")
    parser.add_argument("--predictions", required=True, help="Path to predicted fraud-ring/cycle JSONL/JSON file")
    parser.add_argument("--ground-truth", required=True, help="Path to ground-truth JSON/JSONL file")
    parser.add_argument("--min-jaccard", type=float, default=1.0, help="Minimum participant-set Jaccard for a ring match")
    parser.add_argument("--output", help="Optional path to write metrics JSON")
    parser.add_argument(
        "--all-records-are-predictions",
        action="store_true",
        help="Ignore is_fraud_ring and evaluate every prediction record as positive",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    metrics = evaluate_cycle_fragment_file(
        args.predictions,
        args.ground_truth,
        min_jaccard=args.min_jaccard,
        predicted_label_field=None if args.all_records_are_predictions else "is_fraud_ring",
    )
    metrics_json = json.dumps(metrics, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(metrics_json + "\n", encoding="utf-8")
    print(metrics_json)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
