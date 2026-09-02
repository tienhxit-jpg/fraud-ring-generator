import unittest


class CycleDetectionScriptSmokeTests(unittest.TestCase):
    def test_cypher_detector_builds_research_summary(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        summary = CypherCycleDetector.build_research_summary(
            approach="cypher",
            graph_stats={"nodes": 3, "edges": 3},
            result_count=1,
            elapsed_ms=12.5,
            sample_results=[{"participants": ["A", "B", "C"], "cycle_size": 3}],
            notes=["unit-test"],
        )

        self.assertEqual(summary["approach"], "cypher")
        self.assertEqual(summary["graph_stats"]["nodes"], 3)
        self.assertEqual(summary["result_count"], 1)
        self.assertEqual(summary["sample_results"][0]["cycle_size"], 3)

    def test_cypher_fixed_query_uses_per_size_queries_to_avoid_size5_limit_bias(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        self.assertEqual(set(CypherCycleDetector.FIXED_LENGTH_QUERIES), {3, 4, 5})
        for size, query in CypherCycleDetector.FIXED_LENGTH_QUERIES.items():
            self.assertIn(f"{size} AS cycle_size", query)
            self.assertIn("LIMIT $limit", query)
            self.assertIn("collect(DISTINCT t) AS txs", query)
            self.assertIn("fraud_transaction_count", query)
            self.assertIn("$require_fraud_evidence", query)
            self.assertNotIn("t1:Transaction", query)

    def test_cypher_run_query_passes_candidate_filter_parameters(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter([])

        class FakeSession:
            last_params = None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_params = kwargs
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = CypherCycleDetector(driver=FakeDriver())
        detector.find_triangles(limit=12, require_fraud_evidence=True, min_internal_transactions=5, min_total_amount=1000.0)

        self.assertEqual(FakeSession.last_params["limit"], 12)
        self.assertTrue(FakeSession.last_params["require_fraud_evidence"])
        self.assertEqual(FakeSession.last_params["min_internal_transactions"], 5)
        self.assertEqual(FakeSession.last_params["min_total_amount"], 1000.0)
        self.assertEqual(FakeSession.last_params["anchor_limit"], 10000)

    def test_cypher_anchored_query_limits_start_accounts_for_large_graphs(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        query = CypherCycleDetector.build_fraud_anchored_cycle_query(6)

        self.assertIn("a0.fraud_ring_member = true", query)
        self.assertIn("LIMIT $anchor_limit", query)
        self.assertIn("6 AS cycle_size", query)
        self.assertIn("MATCH (a5)-[:SENT]->(t5:Transaction)-[:RECEIVED_BY]->(a0:Account)", query)
        self.assertIn("collect(DISTINCT t) AS txs", query)

    def test_cypher_anchored_mode_passes_anchor_limit(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter([])

        class FakeSession:
            params = []
            queries = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.queries.append(query)
                FakeSession.params.append(kwargs)
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = CypherCycleDetector(driver=FakeDriver())
        rows = detector.find_fraud_anchored_cycles(limit=7, anchor_limit=49, min_internal_transactions=3)

        self.assertEqual(rows, [])
        self.assertEqual(len(FakeSession.params), 4)
        self.assertTrue(all(params["anchor_limit"] == 49 for params in FakeSession.params))
        self.assertTrue(all(params["limit"] == 7 for params in FakeSession.params))
        self.assertTrue(all(params["require_fraud_evidence"] for params in FakeSession.params))

    def test_cypher_component_mode_merges_overlapping_cycle_fragments(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        merged = CypherCycleDetector.merge_overlapping_cycle_records(
            [
                {"participants": ["A", "B", "C"], "cycle_size": 3, "cycles": 1},
                {"participants": ["C", "D", "E"], "cycle_size": 3, "cycles": 2},
                {"participants": ["X", "Y", "Z"], "cycle_size": 3, "cycles": 1},
            ]
        )

        participant_sets = {tuple(item["participants"]): item for item in merged}
        self.assertIn(("A", "B", "C", "D", "E"), participant_sets)
        self.assertIn(("X", "Y", "Z"), participant_sets)
        self.assertEqual(participant_sets[("A", "B", "C", "D", "E")]["fragment_count"], 2)
        self.assertEqual(participant_sets[("A", "B", "C", "D", "E")]["cycles"], 3)
        self.assertEqual(participant_sets[("A", "B", "C", "D", "E")]["method"], "pure_cypher_component_merge")

    def test_cypher_graph_stats_handles_empty_database_result(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        class FakeResult:
            def single(self):
                return None

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, *args, **kwargs):
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = CypherCycleDetector(driver=FakeDriver())
        self.assertEqual(detector.get_graph_stats(), {"nodes": 0, "edges": 0})

    def test_gds_detector_normalizes_scc_results(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        normalized = GDSCycleDetector.normalize_scc_records([
            {"componentId": 7, "accounts_in_cycle": ["A", "B", "C"], "cycle_size": 3}
        ])

        self.assertEqual(normalized[0]["component_id"], 7)
        self.assertEqual(normalized[0]["participants"], ["A", "B", "C"])
        self.assertEqual(normalized[0]["cycle_size"], 3)

    def test_gds_version_check_uses_scalar_function_not_yield_version(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def single(self):
                return {"version": "2.5.0"}

        class FakeSession:
            last_query = ""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_query = query
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver())
        info = detector.verify_gds_available()

        self.assertEqual(info["gds_version"], "2.5.0")
        self.assertTrue(info["gds_available"])
        self.assertIn("RETURN gds.version() AS version", FakeSession.last_query)
        self.assertNotIn("YIELD version", FakeSession.last_query)

    def test_gds_triangle_count_has_cypher_fallback_for_directed_projection_error(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter([
                    {"account_id": "A", "triangleCount": 1, "kyc_risk_score": 0.7, "method": "cypher_directed_triangle_fallback"}
                ])

        class FakeSession:
            last_query = ""
            last_params = {}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_query = query
                FakeSession.last_params = kwargs
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver())
        rows = detector.run_triangle_count_cypher(limit=10)

        self.assertEqual(rows[0]["method"], "cypher_directed_triangle_fallback")
        self.assertIn("MATCH (a:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(b:Account)", FakeSession.last_query)
        self.assertIn("WITH DISTINCT [a.account_id, b.account_id, c.account_id] AS triangle", FakeSession.last_query)
        self.assertEqual(FakeSession.last_params["limit"], 10)

    def test_gds_scc_query_has_upper_bound_to_skip_giant_components(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter([])

        class FakeSession:
            last_query = ""
            last_params = {}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_query = query
                FakeSession.last_params = kwargs
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver())
        detector.run_scc("g", min_size=3, max_size=12)

        self.assertIn("size(accounts) <= $max_size", FakeSession.last_query)
        self.assertEqual(FakeSession.last_params["max_size"], 12)

    def test_gds_group_metrics_are_batched_with_unwind(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter(
                    [
                        {
                            "idx": 0,
                            "transactions": 7,
                            "total_amount": 650.0,
                            "fraud_transaction_count": 3,
                            "fraud_member_count": 3,
                            "avg_source_risk": 0.8,
                            "density": 0.5,
                        },
                        {
                            "idx": 1,
                            "transactions": 4,
                            "total_amount": 120.0,
                            "fraud_transaction_count": 0,
                            "fraud_member_count": 0,
                            "avg_source_risk": 0.2,
                            "density": 0.333333,
                        },
                    ]
                )

        class FakeSession:
            last_query = ""
            last_params = {}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_query = query
                FakeSession.last_params = kwargs
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver())
        groups = detector.add_transaction_metrics_to_groups([
            {"participants": ["C", "A", "B"]},
            {"participants": ["X", "Y", "Z"]},
        ])

        self.assertIn("UNWIND $groups AS group", FakeSession.last_query)
        self.assertEqual(len(FakeSession.last_params["groups"]), 2)
        self.assertEqual(groups[0]["participants"], ["A", "B", "C"])
        self.assertEqual(groups[0]["transactions"], 7)
        self.assertEqual(groups[0]["fraud_transaction_count"], 3)
        self.assertEqual(groups[0]["fraud_member_count"], 3)
        self.assertTrue(groups[0]["metrics_are_group_level"])

    def test_gds_fraud_evidence_projection_filters_giant_background_graph(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def single(self):
                return {"graphName": "g", "nodeCount": 3, "relationshipCount": 3, "projectMillis": 1}

            def __iter__(self):
                return iter([])

        class FakeSession:
            queries = []
            params = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.queries.append(query)
                FakeSession.params.append(kwargs)
                if "gds.graph.exists" in query:
                    return type("ExistsResult", (), {"single": lambda self: {"exists": False}})()
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver())
        detector.project_graph("g", projection_scope="fraud_evidence")
        projection_query = FakeSession.queries[-1]
        relationship_query = FakeSession.params[-1]["relationship_query"]

        self.assertIn("gds.graph.project.cypher", projection_query)
        self.assertIn("coalesce(t.is_fraud, 0) = 1", relationship_query)
        self.assertIn("t.fraud_ring_id IS NOT NULL", relationship_query)
        self.assertIn("coalesce(src.fraud_ring_member, false) = true", relationship_query)

    def test_hybrid_cycle_detection_skips_giant_sccs(self):
        import networkx as nx
        from src.cycle_detection.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        graph = nx.DiGraph()
        for node in ["A", "B", "C", "D", "E"]:
            graph.add_node(node, risk_score=0.5, monthly_transaction_count=1)
        graph.add_edge("A", "B", weight=1, transaction_count=1)
        graph.add_edge("B", "C", weight=1, transaction_count=1)
        graph.add_edge("C", "A", weight=1, transaction_count=1)
        graph.add_edge("D", "E", weight=1, transaction_count=1)
        graph.add_edge("E", "D", weight=1, transaction_count=1)

        detector = HybridNetworkXCycleDetector(driver=None)
        cycles = detector.detect_cycles(graph, max_cycle_length=3, limit=10, min_component_size=2, max_component_size=2)

        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]["participants"]), {"D", "E"})

    def test_hybrid_cycle_detection_filters_by_fraud_evidence_and_group_metrics(self):
        import networkx as nx
        from src.cycle_detection.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        graph = nx.DiGraph()
        for node in ["A", "B", "C", "X", "Y", "Z"]:
            graph.add_node(node, risk_score=0.8 if node in {"A", "B", "C"} else 0.1, monthly_transaction_count=5, fraud_ring_member=node in {"A", "B", "C"})
        graph.add_edge("A", "B", weight=100, amount=100, transaction_count=2, fraud_transaction_count=1)
        graph.add_edge("B", "C", weight=200, amount=200, transaction_count=2, fraud_transaction_count=1)
        graph.add_edge("C", "A", weight=300, amount=300, transaction_count=2, fraud_transaction_count=1)
        graph.add_edge("A", "C", weight=50, amount=50, transaction_count=1, fraud_transaction_count=0)
        graph.add_edge("X", "Y", weight=10000, amount=10000, transaction_count=1, fraud_transaction_count=0)
        graph.add_edge("Y", "Z", weight=10000, amount=10000, transaction_count=1, fraud_transaction_count=0)
        graph.add_edge("Z", "X", weight=10000, amount=10000, transaction_count=1, fraud_transaction_count=0)

        detector = HybridNetworkXCycleDetector(driver=None)
        cycles = detector.detect_cycles(
            graph,
            max_cycle_length=3,
            limit=10,
            min_component_size=3,
            max_component_size=3,
            require_fraud_evidence=True,
            min_internal_transactions=4,
        )

        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]["participants"]), {"A", "B", "C"})
        self.assertEqual(cycles[0]["group_transactions"], 7)
        self.assertEqual(cycles[0]["group_total_amount"], 650)
        self.assertEqual(cycles[0]["fraud_transaction_count"], 3)
        self.assertEqual(cycles[0]["fraud_member_count"], 3)
        self.assertTrue(cycles[0]["metrics_are_group_level"])

    def test_hybrid_save_to_neo4j_is_disabled_to_avoid_answer_key_leakage(self):
        from src.cycle_detection.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        detector = HybridNetworkXCycleDetector(driver=None)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            detector.save_results_to_neo4j([])

    def test_hybrid_cycle_scoring_is_deterministic(self):
        import networkx as nx
        from src.cycle_detection.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        graph = nx.DiGraph()
        graph.add_node("A", risk_score=0.2, monthly_transaction_count=40)
        graph.add_node("B", risk_score=0.4, monthly_transaction_count=20)
        graph.add_node("C", risk_score=0.3, monthly_transaction_count=30)
        graph.add_edge("A", "B", weight=1000)
        graph.add_edge("B", "C", weight=2000)
        graph.add_edge("C", "A", weight=3000)

        detector = HybridNetworkXCycleDetector(driver=None)
        try:
            score = detector.score_cycle(graph, ["A", "B", "C"])
            amount = detector.get_cycle_amount(graph, ["A", "B", "C"])
        finally:
            detector.close()

        self.assertEqual(amount, 6000)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)


class CycleDetectionScalabilityRegressionTests(unittest.TestCase):
    def test_detector_session_uses_aura_database_when_configured(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeDriver:
            kwargs = None

            def session(self, **kwargs):
                FakeDriver.kwargs = kwargs
                return object()

            def close(self):
                pass

        detector = GDSCycleDetector(driver=FakeDriver(), database="neo4j")
        detector._session()
        self.assertEqual(FakeDriver.kwargs, {"database": "neo4j"})

    def test_aura_uri_is_preserved_by_shared_config(self):
        from src.neo4j_config import load_neo4j_config

        config = load_neo4j_config(
            path="missing.env",
            environ={
                "NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "secret",
                "NEO4J_DATABASE": "neo4j",
            },
        )
        self.assertEqual(config.uri, "neo4j+s://example.databases.neo4j.io")
        self.assertEqual(config.database, "neo4j")

    def test_shared_neo4j_config_loads_values_from_config_file(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from src.neo4j_config import load_neo4j_config

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "neo4j.env"
            config_path.write_text(
                "NEO4J_URI=bolt://db.example:7687\n"
                "NEO4J_USER=researcher\n"
                "NEO4J_PASSWORD=secret-once\n"
                "NEO4J_DATABASE=fraud\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_neo4j_config(config_path)

        self.assertEqual(config.uri, "bolt://db.example:7687")
        self.assertEqual(config.user, "researcher")
        self.assertEqual(config.password, "secret-once")
        self.assertEqual(config.database, "fraud")

    def test_cypher_limit_zero_removes_query_limit_instead_of_returning_zero_rows(self):
        from src.cycle_detection.cypher_cycle_detection import CypherCycleDetector

        query = CypherCycleDetector.query_with_optional_limit("RETURN 1 AS value\nLIMIT $limit", 0)
        self.assertNotIn("LIMIT $limit", query)

    def test_gds_scc_limit_zero_omits_limit_clause(self):
        from src.cycle_detection.gds_cycle_detection import GDSCycleDetector

        class FakeResult:
            def __iter__(self):
                return iter([])

        class FakeSession:
            last_query = ""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def run(self, query, **kwargs):
                FakeSession.last_query = query
                return FakeResult()

        class FakeDriver:
            def session(self):
                return FakeSession()

            def close(self):
                pass

        GDSCycleDetector(driver=FakeDriver()).run_scc("g", limit=0, min_size=3, max_size=6)
        self.assertNotIn("LIMIT $limit", FakeSession.last_query)

    def test_hybrid_limit_zero_returns_all_component_rings(self):
        import networkx as nx
        from src.cycle_detection.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        graph = nx.DiGraph()
        for prefix in ("A", "X"):
            nodes = [prefix + str(index) for index in range(3)]
            for node in nodes:
                graph.add_node(node, risk_score=0.5, monthly_transaction_count=1)
            for index, source in enumerate(nodes):
                graph.add_edge(
                    source,
                    nodes[(index + 1) % 3],
                    weight=1,
                    amount=1,
                    transaction_count=1,
                    fraud_transaction_count=0,
                )

        detector = HybridNetworkXCycleDetector(driver=None)
        rings = detector.detect_cycles(graph, max_cycle_length=3, limit=0, min_component_size=3, max_component_size=3)
        self.assertEqual(len(rings), 2)


if __name__ == "__main__":
    unittest.main()
