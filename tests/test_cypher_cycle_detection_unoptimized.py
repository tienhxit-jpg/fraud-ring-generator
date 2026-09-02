import importlib.util
from pathlib import Path


SCRIPT = Path("src/cycle_detection/v02/cypher_cycle_detection_unoptimized.py").resolve()


def load_module():
    spec = importlib.util.spec_from_file_location("cypher_unoptimized_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_query_has_no_optimization_clauses_or_answer_keys():
    module = load_module()
    query = module.UnoptimizedCypherBaseline.build_query(5)
    assert query.count(":Transaction") == 5
    for forbidden in (
        "TRANSFER_AGG",
        "DISTINCT",
        "ORDER BY",
        "LIMIT",
        "reduce(min_id",
        "min_pair_transactions",
        "is_fraud",
        "fraud_ring_member",
        "fraud_ring_id",
    ):
        assert forbidden not in query


def test_baseline_query_returns_transaction_path_rows():
    module = load_module()
    query = module.UnoptimizedCypherBaseline.build_query(3)
    assert "[t0.transaction_id, t1.transaction_id, t2.transaction_id]" in query
    assert "[a0.account_id, a1.account_id, a2.account_id]" in query


def test_cycle8_uses_shorter_timeout():
    module = load_module()
    baseline = module.UnoptimizedCypherBaseline(driver=None, logger=None)
    assert baseline.timeout_for_size(5, 900, 60) == 900
    assert baseline.timeout_for_size(8, 900, 60) == 60
