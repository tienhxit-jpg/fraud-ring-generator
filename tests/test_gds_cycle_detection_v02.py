import importlib.util
from pathlib import Path


SCRIPT = Path("src/cycle_detection/v02/gds_cycle_detection_v02.py").resolve()


def load_module():
    spec = importlib.util.spec_from_file_location("gds_v02_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gds_v02_source_has_no_answer_key_properties_or_result_filtering():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "is_fraud",
        "fraud_ring_member",
        "fraud_ring_id",
        "projection_scope",
        "fraud_only",
        "min_fraud_score",
        "result_io",
    ):
        assert forbidden not in source


def test_gds_v02_projection_uses_all_distinct_account_pairs():
    module = load_module()
    query = module.GDSCycleDetectorV02.relationship_projection_query()
    assert "WITH DISTINCT src, dst" in query
    assert "RETURN id(src) AS source" in query
    assert "WHERE" not in query.upper()


def test_gds_v02_limit_zero_removes_scc_limit():
    module = load_module()
    assert "LIMIT $limit" not in module.GDSCycleDetectorV02.scc_query(limit=0)
    assert "LIMIT $limit" in module.GDSCycleDetectorV02.scc_query(limit=100)


def test_gds_v02_enrichment_is_business_only():
    module = load_module()
    query = module.GDSCycleDetectorV02.enrichment_query().lower()
    assert "transactions" in query
    assert "total_amount" in query
    for forbidden in ("is_fraud", "fraud_ring_member", "fraud_ring_id"):
        assert forbidden not in query


def test_gds_v02_accepts_versionless_aura_graph_analytics():
    module = load_module()
    result = module.GDSCycleDetectorV02.interpret_version_error(
        "Aura Graph Analytics is versionless."
    )
    assert result["available"] is True
    assert result["version"] == "versionless"
