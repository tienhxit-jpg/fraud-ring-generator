"""JSONL output helpers for cycle detection results.

The ground-truth file stores rings as objects with fields such as ring_id,
ring_type, participants, participant_count, transactions, total_amount, pattern,
and cycles. JSONL cannot have one top-level ``rings`` array, so we write one
ring object per line using the same core fields. Detailed per-cycle instances
are optional and are disabled by default to keep the shape close to ground truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Sequence, Tuple


def canonical_participants(participants: Sequence[Any]) -> List[str]:
    """Return stable unique account ids for grouping the same ring."""
    return sorted({str(item) for item in participants if item is not None})


def pattern_for_size(participant_count: int) -> str:
    if participant_count in {3, 4, 5}:
        return f"cycle_{participant_count}"
    return "complex_network"


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def score_and_classify_fraud_ring(ring: Dict[str, Any], min_fraud_score: float = 0.35) -> Dict[str, Any]:
    """Add fraud score, fraud label, and heuristic fraud-ring type.

    Cycle detectors find graph structure first. This layer filters structural
    cycles down to likely fraud rings using amount, activity, repeated cycles,
    density, and optional account KYC risk metrics.
    """
    participant_count = as_int(ring.get("participant_count"), len(ring.get("participants") or []))
    transactions = as_int(ring.get("transactions"), 0)
    total_amount = as_float(ring.get("total_amount"), 0.0)
    cycles = as_int(ring.get("cycles"), 0)
    avg_risk = as_float(ring.get("avg_kyc_risk_score"), 0.5)
    density = as_float(ring.get("density"), 0.0)
    fraud_transaction_count = as_int(ring.get("fraud_transaction_count"), 0)
    fraud_member_count = as_int(ring.get("fraud_member_count"), 0)

    amount_factor = min(total_amount / 1_000_000.0, 1.0)
    cycle_factor = min(cycles / 5.0, 1.0)
    txn_factor = min(transactions / max(participant_count * 5.0, 1.0), 1.0)
    risk_factor = max(0.0, min(avg_risk, 1.0))
    size_factor = 1.0 if participant_count >= 3 else 0.0
    density_factor = max(0.0, min(density, 1.0))
    fraud_evidence_factor = 1.0 if fraud_transaction_count > 0 or fraud_member_count > 0 else 0.0

    fraud_score = round(
        amount_factor * 0.30
        + cycle_factor * 0.20
        + txn_factor * 0.20
        + risk_factor * 0.20
        + size_factor * 0.03
        + density_factor * 0.03
        + fraud_evidence_factor * 0.04,
        4,
    )

    signals: List[str] = []
    if participant_count >= 3:
        signals.append("closed_account_cycle")
    if total_amount >= 500_000:
        signals.append("high_total_amount")
    if transactions >= max(participant_count * 4, 8):
        signals.append("high_internal_transaction_count")
    if cycles >= 3:
        signals.append("repeated_cycles")
    if avg_risk >= 0.65:
        signals.append("high_average_kyc_risk")
    if density >= 0.35:
        signals.append("dense_internal_connectivity")
    if fraud_transaction_count > 0:
        signals.append("contains_generated_fraud_transactions")
    if fraud_member_count > 0:
        signals.append("contains_generated_fraud_accounts")

    if fraud_transaction_count > 0 and fraud_member_count > 0:
        classified_type = "money_laundering" if total_amount >= 500_000 else "collusion"
    elif avg_risk >= 0.65:
        classified_type = "account_takeover"
    elif total_amount >= 1_000_000 or (total_amount >= 500_000 and transactions >= participant_count * 4):
        classified_type = "money_laundering"
    elif participant_count >= 8 or density >= 0.35 or cycles >= 5:
        classified_type = "collusion"
    elif transactions >= participant_count * 3 and total_amount < 1_000_000:
        classified_type = "phishing"
    else:
        classified_type = "benign_cycle"

    has_generated_fraud_evidence = fraud_transaction_count > 0 and fraud_member_count > 0 and participant_count >= 3
    is_fraud_ring = has_generated_fraud_evidence or (fraud_score >= min_fraud_score and classified_type != "benign_cycle")
    ring["fraud_score"] = fraud_score
    ring["is_fraud_ring"] = is_fraud_ring
    ring["fraud_signals"] = signals
    ring["ring_type"] = classified_type if is_fraud_ring else "benign_cycle"
    return ring


def normalize_cycle_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    participants = list(record.get("participants") or record.get("accounts") or [])
    cycle_size = as_int(record.get("cycle_size") or record.get("size") or len(participants), len(participants))
    total_amount = round(as_float(record.get("total_amount") or record.get("amount"), 0.0), 2)
    instance = {
        "participants": participants,
        "cycle_size": cycle_size,
        "total_amount": total_amount,
    }
    for optional_key in ("score", "density", "method", "component_id", "community_id"):
        if optional_key in record:
            instance[optional_key] = record[optional_key]
    return instance


def aggregate_cycle_records(
    records: Iterable[Dict[str, Any]],
    ring_id_prefix: str = "RING",
    ring_type: str = "detected_cycle",
    source_approach: str | None = None,
    include_instances: bool = False,
    fraud_only: bool = False,
    min_fraud_score: float = 0.35,
) -> List[Dict[str, Any]]:
    """Aggregate detected cycle rows into ground-truth-like fraud-ring objects.

    Multiple cycle rows with the same participant set become one ring. This is
    important for the Cypher/NetworkX approaches where each path instance is a
    separate cycle but the research artifact should compare at the fraud-ring
    level.
    """
    grouped: MutableMapping[Tuple[str, ...], Dict[str, Any]] = {}

    for record in records:
        raw_participants = record.get("participants") or record.get("accounts") or []
        participants = canonical_participants(raw_participants)
        if not participants:
            continue

        key = tuple(participants)
        cycle_size = as_int(record.get("cycle_size") or record.get("size") or len(participants), len(participants))
        metrics_are_group_level = bool(record.get("metrics_are_group_level"))
        if metrics_are_group_level:
            total_amount = as_float(record.get("group_total_amount", record.get("total_amount", record.get("amount"))), 0.0)
        else:
            total_amount = as_float(record.get("total_amount") or record.get("amount"), 0.0)
        transaction_count = as_int(
            record.get("group_transactions") if metrics_are_group_level else (record.get("transactions") or record.get("transaction_count") or cycle_size),
            cycle_size,
        )

        if key not in grouped:
            grouped[key] = {
                "ring_type": ring_type,
                "participants": participants,
                "participant_count": len(participants),
                "transactions": 0,
                "total_amount": 0.0,
                "pattern": pattern_for_size(len(participants)),
                "cycles": 0,
            }
            if source_approach:
                grouped[key]["source_approach"] = source_approach
            if include_instances:
                grouped[key]["cycle_instances"] = []

        ring = grouped[key]
        if metrics_are_group_level:
            ring["transactions"] = max(as_int(ring.get("transactions"), 0), transaction_count)
            ring["total_amount"] = max(as_float(ring.get("total_amount"), 0.0), total_amount)
        else:
            ring["transactions"] += transaction_count
            ring["total_amount"] += total_amount
        ring["cycles"] += as_int(record.get("cycles") or 1, 1)
        if "score" in record:
            ring["score"] = max(as_float(ring.get("score"), 0.0), as_float(record.get("score"), 0.0))
        if "avg_kyc_risk_score" in record:
            existing_count = as_int(ring.get("_risk_observations"), 0)
            existing_total = as_float(ring.get("_risk_total"), 0.0)
            ring["_risk_observations"] = existing_count + 1
            ring["_risk_total"] = existing_total + as_float(record.get("avg_kyc_risk_score"), 0.5)
            ring["avg_kyc_risk_score"] = round(ring["_risk_total"] / ring["_risk_observations"], 4)
        if "density" in record:
            ring["density"] = max(as_float(ring.get("density"), 0.0), as_float(record.get("density"), 0.0))
        if "fraud_transaction_count" in record:
            ring["fraud_transaction_count"] = max(as_int(ring.get("fraud_transaction_count"), 0), as_int(record.get("fraud_transaction_count"), 0))
        if "fraud_member_count" in record:
            ring["fraud_member_count"] = max(as_int(ring.get("fraud_member_count"), 0), as_int(record.get("fraud_member_count"), 0))
        if include_instances:
            ring["cycle_instances"].append(normalize_cycle_instance(record))

    rings = list(grouped.values())
    for ring in rings:
        ring.pop("_risk_total", None)
        ring.pop("_risk_observations", None)
        score_and_classify_fraud_ring(ring, min_fraud_score=min_fraud_score)

    if fraud_only:
        rings = [ring for ring in rings if ring.get("is_fraud_ring")]

    rings.sort(key=lambda item: (item["total_amount"], item["cycles"], item["participant_count"]), reverse=True)

    for index, ring in enumerate(rings):
        ring["ring_id"] = f"{ring_id_prefix}_{index:04d}"
        ring["total_amount"] = round(as_float(ring["total_amount"]), 2)
        # Match ground-truth field order as closely as normal dict insertion can.
        ordered = {
            "ring_id": ring["ring_id"],
            "ring_type": ring["ring_type"],
            "participants": ring["participants"],
            "participant_count": ring["participant_count"],
            "transactions": ring["transactions"],
            "total_amount": ring["total_amount"],
            "pattern": ring["pattern"],
            "cycles": ring["cycles"],
        }
        for key, value in ring.items():
            if key not in ordered:
                ordered[key] = value
        ring.clear()
        ring.update(ordered)

    return rings


def write_jsonl(path: str | Path, records: Iterable[Dict[str, Any]]) -> int:
    """Write one JSON object per line and return number of lines written."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str))
            handle.write("\n")
            count += 1
    return count


def save_cycle_records_jsonl(
    path: str | Path,
    records: Iterable[Dict[str, Any]],
    ring_id_prefix: str,
    ring_type: str,
    source_approach: str,
    include_instances: bool = False,
    fraud_only: bool = False,
    min_fraud_score: float = 0.35,
) -> List[Dict[str, Any]]:
    rings = aggregate_cycle_records(
        records,
        ring_id_prefix=ring_id_prefix,
        ring_type=ring_type,
        source_approach=source_approach,
        include_instances=include_instances,
        fraud_only=fraud_only,
        min_fraud_score=min_fraud_score,
    )
    write_jsonl(path, rings)
    return rings
