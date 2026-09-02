"""Evaluation metrics for fraud-ring detection outputs.

The detector outputs one JSON object per line (JSONL) with a ``participants``
array. Ground truth is usually a JSON document with a top-level ``rings`` array.
This module compares rings at the participant-set level and reports precision,
recall, F1, and supporting counts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

Ring = Mapping[str, Any]
ParticipantKey = Tuple[str, ...]


@dataclass(frozen=True)
class RingMatch:
    """A matched predicted/ground-truth ring pair."""

    predicted_ring_id: str | None
    ground_truth_ring_id: str | None
    predicted_participants: ParticipantKey
    ground_truth_participants: ParticipantKey
    jaccard: float


def canonical_participant_key(participants: Sequence[Any]) -> ParticipantKey:
    """Return a stable participant-set key for a fraud ring."""

    return tuple(sorted({str(participant) for participant in participants if participant is not None}))


def participant_jaccard(left: Sequence[Any], right: Sequence[Any]) -> float:
    """Compute Jaccard overlap between two participant sets."""

    left_set = set(canonical_participant_key(left))
    right_set = set(canonical_participant_key(right))
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line_number, raw_line in enumerate(file_obj, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}, got {type(record).__name__}")
            records.append(record)
    return records


def load_rings(path: str | Path) -> List[Dict[str, Any]]:
    """Load rings from JSONL or JSON.

    Supported formats:
    - JSONL: one ring object per line, as in ``data/cycledetection/.../*.jsonl``.
    - JSON object with top-level ``rings`` list, as in ground truth.
    - JSON list of ring objects.
    """

    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        return _load_jsonl(input_path)

    with input_path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if isinstance(payload, dict):
        rings = payload.get("rings")
        if rings is None:
            raise ValueError(f"JSON file {input_path} does not contain a top-level 'rings' array")
    elif isinstance(payload, list):
        rings = payload
    else:
        raise ValueError(f"Expected JSON object/list in {input_path}, got {type(payload).__name__}")

    if not isinstance(rings, list):
        raise ValueError(f"Expected 'rings' to be a list in {input_path}")
    if not all(isinstance(ring, dict) for ring in rings):
        raise ValueError(f"Expected every ring in {input_path} to be a JSON object")
    return list(rings)


def filter_predicted_rings(
    rings: Iterable[Dict[str, Any]],
    predicted_label_field: str | None = "is_fraud_ring",
    keep_unlabeled: bool = True,
) -> List[Dict[str, Any]]:
    """Keep records considered positive fraud-ring predictions.

    If ``predicted_label_field`` is present, only truthy records are kept. If it
    is absent and ``keep_unlabeled`` is true, the record is kept because many
    detector JSONL files contain only predicted fraud rings and no explicit
    label.
    """

    if predicted_label_field is None:
        return list(rings)

    filtered: List[Dict[str, Any]] = []
    for ring in rings:
        if predicted_label_field in ring:
            if bool(ring.get(predicted_label_field)):
                filtered.append(ring)
        elif keep_unlabeled:
            filtered.append(ring)
    return filtered


def _unique_by_participants(rings: Iterable[Ring]) -> Dict[ParticipantKey, Ring]:
    unique: Dict[ParticipantKey, Ring] = {}
    for ring in rings:
        key = canonical_participant_key(ring.get("participants") or [])
        if not key:
            continue
        unique.setdefault(key, ring)
    return unique


def match_rings(
    predicted_rings: Iterable[Ring],
    ground_truth_rings: Iterable[Ring],
    min_jaccard: float = 1.0,
) -> Tuple[List[RingMatch], List[Ring], List[Ring]]:
    """Match predictions to ground truth with one-to-one participant overlap.

    ``min_jaccard=1.0`` requires exact same participant set. Lower values allow
    partial-overlap matching; ties are resolved by higher Jaccard, then smaller
    participant-count difference, then ground-truth ring id.

    Returns ``(matches, false_positive_rings, false_negative_rings)``.
    """

    if not 0.0 < min_jaccard <= 1.0:
        raise ValueError("min_jaccard must be in the range (0, 1]")

    predictions_by_key = _unique_by_participants(predicted_rings)
    truth_by_key = _unique_by_participants(ground_truth_rings)

    matched_truth_keys: set[ParticipantKey] = set()
    matches: List[RingMatch] = []
    false_positives: List[Ring] = []

    for pred_key, pred_ring in sorted(predictions_by_key.items()):
        best_truth_key: ParticipantKey | None = None
        best_score = 0.0
        best_size_delta = 10**9
        for truth_key, truth_ring in truth_by_key.items():
            if truth_key in matched_truth_keys:
                continue
            score = participant_jaccard(pred_key, truth_key)
            size_delta = abs(len(pred_key) - len(truth_key))
            if (
                score > best_score
                or (score == best_score and size_delta < best_size_delta)
                or (
                    score == best_score
                    and size_delta == best_size_delta
                    and str(truth_ring.get("ring_id", "")) < str(truth_by_key.get(best_truth_key, {}).get("ring_id", "~"))
                )
            ):
                best_score = score
                best_size_delta = size_delta
                best_truth_key = truth_key

        if best_truth_key is not None and best_score >= min_jaccard:
            truth_ring = truth_by_key[best_truth_key]
            matched_truth_keys.add(best_truth_key)
            matches.append(
                RingMatch(
                    predicted_ring_id=pred_ring.get("ring_id"),
                    ground_truth_ring_id=truth_ring.get("ring_id"),
                    predicted_participants=pred_key,
                    ground_truth_participants=best_truth_key,
                    jaccard=round(best_score, 6),
                )
            )
        else:
            false_positives.append(pred_ring)

    false_negatives = [truth_ring for truth_key, truth_ring in truth_by_key.items() if truth_key not in matched_truth_keys]
    return matches, false_positives, false_negatives


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def classification_metrics(true_positives: int, false_positives: int, false_negatives: int) -> Dict[str, float]:
    """Compute precision, recall, F1 from detection counts."""

    precision = safe_divide(true_positives, true_positives + false_positives)
    recall = safe_divide(true_positives, true_positives + false_negatives)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def evaluate_fraud_rings(
    predicted_rings: Iterable[Dict[str, Any]],
    ground_truth_rings: Iterable[Dict[str, Any]],
    min_jaccard: float = 1.0,
) -> Dict[str, Any]:
    """Evaluate predicted fraud rings against ground truth rings."""

    predicted_list = list(predicted_rings)
    truth_list = list(ground_truth_rings)
    matches, false_positives, false_negatives = match_rings(
        predicted_list,
        truth_list,
        min_jaccard=min_jaccard,
    )

    tp = len(matches)
    fp = len(false_positives)
    fn = len(false_negatives)
    metrics = classification_metrics(tp, fp, fn)

    type_matches = 0
    for match in matches:
        pred_ring = next(ring for ring in predicted_list if canonical_participant_key(ring.get("participants") or []) == match.predicted_participants)
        truth_ring = next(ring for ring in truth_list if canonical_participant_key(ring.get("participants") or []) == match.ground_truth_participants)
        if pred_ring.get("ring_type") == truth_ring.get("ring_type"):
            type_matches += 1

    return {
        **metrics,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "predicted_count": len({_key for _key in (_unique_by_participants(predicted_list).keys())}),
        "ground_truth_count": len({_key for _key in (_unique_by_participants(truth_list).keys())}),
        "min_jaccard": min_jaccard,
        "mean_match_jaccard": round(safe_divide(sum(match.jaccard for match in matches), tp), 6),
        "ring_type_accuracy_on_matches": round(safe_divide(type_matches, tp), 6),
        "matches": [match.__dict__ for match in matches],
        "false_positive_ring_ids": [ring.get("ring_id") for ring in false_positives],
        "false_negative_ring_ids": [ring.get("ring_id") for ring in false_negatives],
    }


def evaluate_fraud_ring_file(
    predictions_path: str | Path,
    ground_truth_path: str | Path,
    min_jaccard: float = 1.0,
    predicted_label_field: str | None = "is_fraud_ring",
    keep_unlabeled: bool = True,
) -> Dict[str, Any]:
    """Load prediction/ground-truth files and compute fraud-ring metrics."""

    predicted_rings = filter_predicted_rings(
        load_rings(predictions_path),
        predicted_label_field=predicted_label_field,
        keep_unlabeled=keep_unlabeled,
    )
    ground_truth_rings = load_rings(ground_truth_path)
    return evaluate_fraud_rings(predicted_rings, ground_truth_rings, min_jaccard=min_jaccard)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate fraud-ring JSONL output against ground truth.")
    parser.add_argument("--predictions", required=True, help="Path to predicted fraud-ring JSONL/JSON file")
    parser.add_argument("--ground-truth", required=True, help="Path to ground-truth JSON/JSONL file")
    parser.add_argument("--min-jaccard", type=float, default=1.0, help="Minimum participant-set Jaccard for a TP match")
    parser.add_argument("--output", help="Optional path to write metrics JSON")
    parser.add_argument(
        "--all-records-are-predictions",
        action="store_true",
        help="Ignore is_fraud_ring and evaluate every prediction record as positive",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    metrics = evaluate_fraud_ring_file(
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
