import json
import tempfile
import unittest
from pathlib import Path


class CycleDetectionJsonlTests(unittest.TestCase):
    def test_aggregate_cycles_to_ground_truth_like_rings(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {"participants": ["ACC_B", "ACC_A", "ACC_C"], "cycle_size": 3, "total_amount": 100.5},
                {"participants": ["ACC_A", "ACC_C", "ACC_B"], "cycle_size": 3, "total_amount": 200.25},
            ],
            ring_id_prefix="TEST_RING",
            ring_type="detected_cycle",
            source_approach="unit_test",
            include_instances=True,
        )

        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0]["ring_id"], "TEST_RING_0000")
        self.assertEqual(rings[0]["ring_type"], "benign_cycle")
        self.assertEqual(rings[0]["participants"], ["ACC_A", "ACC_B", "ACC_C"])
        self.assertEqual(rings[0]["participant_count"], 3)
        self.assertEqual(rings[0]["transactions"], 6)
        self.assertEqual(rings[0]["total_amount"], 300.75)
        self.assertEqual(rings[0]["pattern"], "cycle_3")
        self.assertEqual(rings[0]["cycles"], 2)
        self.assertEqual(len(rings[0]["cycle_instances"]), 2)

    def test_jsonl_default_shape_has_single_participants_array_like_ground_truth(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {"participants": ["ACC_B", "ACC_A", "ACC_C"], "cycle_size": 3, "total_amount": 100.5},
                {"participants": ["ACC_A", "ACC_C", "ACC_B"], "cycle_size": 3, "total_amount": 200.25},
            ],
            ring_id_prefix="RING",
            ring_type="detected_cycle",
            source_approach="unit_test",
        )

        self.assertEqual(list(rings[0].keys())[:8], [
            "ring_id",
            "ring_type",
            "participants",
            "participant_count",
            "transactions",
            "total_amount",
            "pattern",
            "cycles",
        ])
        self.assertEqual(rings[0]["participants"], ["ACC_A", "ACC_B", "ACC_C"])
        self.assertNotIn("cycle_instances", rings[0])

    def test_fraud_filters_keep_multiple_participant_counts(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {"participants": ["A1", "A2", "A3"], "cycle_size": 3, "transactions": 9, "total_amount": 350000.0, "avg_kyc_risk_score": 0.55},
                {"participants": ["B1", "B2", "B3", "B4", "B5"], "cycle_size": 5, "transactions": 15, "total_amount": 750000.0, "avg_kyc_risk_score": 0.45},
                {"participants": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"], "cycle_size": 8, "transactions": 24, "total_amount": 450000.0, "avg_kyc_risk_score": 0.5, "density": 0.4},
            ],
            ring_id_prefix="RING",
            ring_type="detected_cycle",
            source_approach="unit_test",
            fraud_only=True,
            min_fraud_score=0.35,
        )

        participant_counts = sorted(ring["participant_count"] for ring in rings)
        self.assertEqual(participant_counts, [3, 5, 8])
        self.assertEqual({ring["pattern"] for ring in rings}, {"cycle_3", "cycle_5", "complex_network"})

    def test_group_level_metrics_do_not_inflate_when_multiple_cycle_paths_share_ring(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {"participants": ["A", "B", "C"], "cycle_size": 3, "total_amount": 100, "group_transactions": 4, "group_total_amount": 1000, "metrics_are_group_level": True},
                {"participants": ["B", "C", "A"], "cycle_size": 3, "total_amount": 200, "group_transactions": 4, "group_total_amount": 1000, "metrics_are_group_level": True},
            ],
            ring_id_prefix="RING",
            source_approach="unit_test",
        )

        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0]["cycles"], 2)
        self.assertEqual(rings[0]["transactions"], 4)
        self.assertEqual(rings[0]["total_amount"], 1000.0)

    def test_fraud_evidence_counts_are_preserved_in_aggregated_rings(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {
                    "participants": ["A", "B", "C"],
                    "cycle_size": 3,
                    "group_transactions": 6,
                    "group_total_amount": 10000,
                    "fraud_transaction_count": 3,
                    "fraud_member_count": 3,
                    "metrics_are_group_level": True,
                }
            ],
            ring_id_prefix="RING",
            source_approach="unit_test",
            fraud_only=True,
            min_fraud_score=0.2,
        )

        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0]["fraud_transaction_count"], 3)
        self.assertEqual(rings[0]["fraud_member_count"], 3)
        self.assertIn("contains_generated_fraud_transactions", rings[0]["fraud_signals"])
        self.assertIn("contains_generated_fraud_accounts", rings[0]["fraud_signals"])

    def test_write_jsonl_writes_one_ring_per_line(self):
        from src.cycle_detection.result_io import write_jsonl

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rings.jsonl"
            written = write_jsonl(
                path,
                [
                    {
                        "ring_id": "RING_0000",
                        "ring_type": "detected_cycle",
                        "participants": ["ACC_1", "ACC_2", "ACC_3"],
                        "participant_count": 3,
                        "transactions": 3,
                        "total_amount": 10.0,
                        "pattern": "cycle_3",
                        "cycles": 1,
                    }
                ],
            )

            self.assertEqual(written, 1)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["ring_id"], "RING_0000")

    def test_fraud_filters_classify_and_remove_benign_cycles(self):
        from src.cycle_detection.result_io import aggregate_cycle_records

        rings = aggregate_cycle_records(
            [
                {
                    "participants": ["ACC_1", "ACC_2", "ACC_3"],
                    "cycle_size": 3,
                    "transactions": 18,
                    "total_amount": 750000.0,
                    "avg_kyc_risk_score": 0.72,
                },
                {
                    "participants": ["ACC_4", "ACC_5", "ACC_6"],
                    "cycle_size": 3,
                    "transactions": 3,
                    "total_amount": 1500.0,
                    "avg_kyc_risk_score": 0.05,
                },
            ],
            ring_id_prefix="RING",
            ring_type="detected_cycle",
            source_approach="unit_test",
            fraud_only=True,
            min_fraud_score=0.45,
        )

        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0]["participants"], ["ACC_1", "ACC_2", "ACC_3"])
        self.assertTrue(rings[0]["is_fraud_ring"])
        self.assertGreaterEqual(rings[0]["fraud_score"], 0.45)
        self.assertEqual(rings[0]["ring_type"], "account_takeover")
        self.assertIn("fraud_signals", rings[0])


if __name__ == "__main__":
    unittest.main()
