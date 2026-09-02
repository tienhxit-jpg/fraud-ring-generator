import importlib.util
from pathlib import Path


SCRIPT = Path("src/cycle_detection/v02/hybrid_networkx_cycle_detection_v02.py").resolve()


def load_module():
    spec = importlib.util.spec_from_file_location("hybrid_v02_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hybrid_v02_source_is_label_blind_and_has_no_legacy_filtering():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "is_fraud",
        "fraud_ring_member",
        "fraud_ring_id",
        "require_fraud_evidence",
        "fraud_only",
        "min_fraud_score",
        "result_io",
    ):
        assert forbidden not in source


def test_hybrid_v02_edge_query_aggregates_logical_pairs():
    module = load_module()
    query = module.HybridNetworkXCycleDetectorV02.edge_query()
    assert "count(t) AS transaction_count" in query
    assert "sum(coalesce(t.amount_usd, t.amount, 0.0))" in query
    assert "WITH a, b" in query


def test_hybrid_v02_cycle_sizes_are_exact_and_canonicalized():
    module = load_module()
    graph = module.nx.DiGraph()
    graph.add_edges_from(
        [("A", "B"), ("B", "C"), ("C", "A"),
         ("A", "D"), ("D", "E"), ("E", "A"),
         ("A", "F"), ("F", "G"), ("G", "H"), ("H", "A")]
    )
    detector = module.HybridNetworkXCycleDetectorV02(driver=None, logger=None)
    detector.detect_cycles(
        graph, cycle_sizes=(3, 5, 8), max_component_size=12, limit=0
    )
    sizes = {item["cycle_size"] for item in detector.last_raw_results}
    assert sizes == {3}
    assert all(item["participants"] == sorted(item["participants"]) for item in detector.last_raw_results)


def test_hybrid_v02_limit_is_applied_after_overlap_merge():
    module = load_module()
    graph = module.nx.DiGraph()
    graph.add_edges_from(
        [("A", "B"), ("B", "C"), ("C", "A"),
         ("C", "D"), ("D", "E"), ("E", "C"),
         ("X", "Y"), ("Y", "Z"), ("Z", "X")]
    )
    detector = module.HybridNetworkXCycleDetectorV02(driver=None, logger=None)
    results = detector.detect_cycles(graph, cycle_sizes=(3,), limit=1)
    assert len(results) == 1
    assert results[0]["participant_count"] >= 3


def test_hybrid_v02_summary_has_per_size_counts():
    module = load_module()
    summary = module.HybridNetworkXCycleDetectorV02.build_summary(
        graph=module.nx.DiGraph(),
        raw_count=4,
        unique_count=3,
        merged_count=2,
        results=[],
        cycle_sizes=(3, 5, 8),
        elapsed_ms=1.0,
        load_elapsed_ms=0.5,
        detect_elapsed_ms=0.5,
        raw_by_size={"3": 2, "5": 1, "8": 1},
    )
    assert summary["raw_result_count"] == 4
    assert summary["results_by_cycle_size"]["8"] == 1
