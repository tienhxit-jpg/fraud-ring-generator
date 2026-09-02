import importlib.util
from pathlib import Path


SCRIPT = Path("src/cycle_detection/v02/cypher_cycle_detection_v02.py").resolve()


def load_module():
    spec = importlib.util.spec_from_file_location("cypher_cycle_detection_v02", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v02_cypher_detector_contains_no_ground_truth_label_checks():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("is_fraud", "fraud_ring_member", "fraud_ring_id"):
        assert forbidden not in source


def test_v02_cypher_detector_has_no_anchored_mode_or_query():
    module = load_module()
    assert "anchored" not in module.CypherCycleDetectorV02.available_modes()
    assert not hasattr(module.CypherCycleDetectorV02, "build_fraud_anchored_cycle_query")


def test_v02_builds_fixed_queries_for_3_5_8_candidates():
    module = load_module()
    queries = module.CypherCycleDetectorV02.build_cycle_queries((3, 5, 8))
    assert set(queries) == {3, 5, 8}
    for size, query in queries.items():
        assert f"{size} AS cycle_size" in query
        assert "MATCH (a0:Account)" in query
        assert "LIMIT $limit" in query
        assert "fraud" not in query.lower()


def test_v02_business_filter_parameters_are_label_blind():
    module = load_module()
    query = module.CypherCycleDetectorV02.build_cycle_query(
        3, min_pair_transactions=2, min_pair_amount=1000.0
    )
    assert "$min_pair_transactions" in query
    assert "$min_pair_amount" in query
    assert "}}" not in query
    assert query.count("EXISTS {") == query.count("}") == 3
    assert "is_fraud" not in query
    assert "fraud_ring" not in query


def test_v02_limit_zero_removes_limit_clause_for_unbounded_run():
    module = load_module()

    class Result:
        def __iter__(self):
            return iter([])

    class Session:
        query = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **kwargs):
            self.query = query
            Session.query = query
            return Result()

    class Driver:
        def __init__(self):
            self.session_instance = Session()

        def session(self, **kwargs):
            return self.session_instance

        def close(self):
            pass

    detector = module.CypherCycleDetectorV02(driver=Driver())
    detector.run_query(3, 0, 0, 0.0, 0, 0.0)
    assert "LIMIT $limit" not in Session.query


def test_v02_emits_simple_progress_logs_for_each_cycle_query():
    module = load_module()
    messages = []

    class Result:
        def __iter__(self):
            return iter([{"participants": ["A", "B", "C"]}])

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **kwargs):
            return Result()

    class Driver:
        def session(self, **kwargs):
            return Session()

        def close(self):
            pass

    detector = module.CypherCycleDetectorV02(
        driver=Driver(), progress_callback=messages.append, progress_interval=0
    )
    detector.run_query(3, 10, 0, 0.0, 0, 0.0)

    assert any("cycle_size=3 started" in message for message in messages)
    assert any("cycle_size=3 finished" in message and "rows=1" in message for message in messages)


def test_prepare_aggregate_graph_batches_sources_without_amount_or_labels():
    module = load_module()

    class Result:
        def __init__(self, record=None):
            self.record = record

        def single(self):
            return self.record

        def consume(self):
            return None

    class Session:
        calls = []
        source_pages = [[1, 2], [3], []]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **kwargs):
            Session.calls.append((query, kwargs))
            if "RETURN id(src) AS source_id" in query:
                page = Session.source_pages.pop(0)
                return Result({"source_ids": page})
            if "RETURN count(r) AS aggregate_pairs" in query:
                return Result({"aggregate_pairs": len(kwargs["source_ids"]) * 10})
            return Result()

    class Driver:
        def session(self, **kwargs):
            return Session()

        def close(self):
            pass

    detector = module.CypherCycleDetectorV02(
        driver=Driver(), progress_callback=None, progress_interval=0
    )
    pairs = detector.prepare_aggregate_graph(rebuild=True, batch_size=2)

    assert pairs == 30
    aggregate_calls = [call for call in Session.calls if "RETURN count(r) AS aggregate_pairs" in call[0]]
    assert [call[1]["source_ids"] for call in aggregate_calls] == [[1, 2], [3]]
    aggregate_query = aggregate_calls[0][0].lower()
    assert "amount >=" not in aggregate_query
    assert "is_fraud" not in aggregate_query
    assert "fraud_ring" not in aggregate_query


def test_run_query_applies_configured_transaction_timeout():
    module = load_module()

    class Result:
        def __iter__(self):
            return iter([])

    class Session:
        submitted_query = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **kwargs):
            Session.submitted_query = query
            return Result()

    class Driver:
        def session(self, **kwargs):
            return Session()

        def close(self):
            pass

    detector = module.CypherCycleDetectorV02(
        driver=Driver(), progress_callback=None, progress_interval=0
    )
    detector.run_query(4, 0, 1, 0.0, 0, 0.0, query_timeout=12.5)

    assert Session.submitted_query.timeout == 12.5
