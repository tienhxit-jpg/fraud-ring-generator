import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DETECTOR = ROOT / "src/cycle_detection/v02/cypher_cycle_detection_v02.py"
FF_SCRIPT = ROOT / "src/cycle_detection/v02/calculate_ff.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_aggregate_query_uses_only_logical_edges_and_canonicalizes():
    module = load(DETECTOR, "detector_aggregate_test")
    query = module.CypherCycleDetectorV02.build_aggregate_cycle_query(5, limit=0)
    assert "TRANSFER_AGG" in query
    assert "transaction_count" in query
    assert query.index("WHERE r0.transaction_count") < query.index("MATCH (a1:Account)-[r1:TRANSFER_AGG]")
    assert "a0.account_id = reduce" in query
    assert "LIMIT $limit" not in query
    assert "ORDER BY" not in query
    for forbidden in ("is_fraud", "fraud_ring_member", "fraud_ring_id"):
        assert forbidden not in query


def test_aggregate_query_can_limit_without_ordering_path_discovery():
    module = load(DETECTOR, "detector_aggregate_limit_test")
    query = module.CypherCycleDetectorV02.build_aggregate_cycle_query(8, limit=500)
    assert "LIMIT $limit" in query
    assert "RETURN DISTINCT" in query
    assert "ORDER BY" not in query


def test_ff_calculation_reports_three_levels():
    module = load(FF_SCRIPT, "ff_test")
    records = [
        {"cycle_size": 3, "participants": ["A", "B", "C"]},
        {"cycle_size": 3, "participants": ["A", "C", "D"]},
        {"cycle_size": 5, "participants": ["C", "D", "E", "F", "G"]},
    ]
    result = module.calculate_ff(records)
    assert result["total"]["raw_cycles"] == 3
    assert result["total"]["unique_sets"] == 3
    assert result["total"]["merged_clusters"] == 1
    assert result["total"]["ff_total"] == 3.0
    assert result["by_cycle_size"]["3"]["raw_cycles"] == 2
