import unittest

import networkx as nx


class HybridNetworkXCycleDetectionTests(unittest.TestCase):
    def test_detect_cycles_merges_overlapping_fragments_into_component_ring(self):
        from cycle_detection.v01.hybrid_networkx_cycle_detection import HybridNetworkXCycleDetector

        graph = nx.DiGraph()
        for account in ["A", "B", "C", "D", "E"]:
            graph.add_node(account, risk_score=0.7, monthly_transaction_count=20, fraud_ring_member=True)

        for source, destination in [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
            ("C", "D"),
            ("D", "E"),
            ("E", "C"),
        ]:
            graph.add_edge(
                source,
                destination,
                weight=100.0,
                amount=100.0,
                transaction_count=1,
                fraud_transaction_count=1,
            )

        detector = HybridNetworkXCycleDetector(driver=None)
        results = detector.detect_cycles(
            graph,
            max_cycle_length=3,
            limit=10,
            min_component_size=3,
            max_component_size=6,
            require_fraud_evidence=True,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["participants"], ["A", "B", "C", "D", "E"])
        self.assertEqual(results[0]["cycle_size"], 5)
        self.assertEqual(results[0]["candidate_cycle_sizes"], [3])
        self.assertEqual(results[0]["fragment_count"], 2)
        self.assertEqual(results[0]["cycles"], 2)
        self.assertEqual(results[0]["method"], "hybrid_networkx_component_merge")
        self.assertTrue(results[0]["metrics_are_group_level"])


if __name__ == "__main__":
    unittest.main()
