import json
import tempfile
import unittest
from pathlib import Path


class FraudCycleMetricsTests(unittest.TestCase):
    def test_fragment_count_metrics_use_min_counts_for_matched_rings(self):
        from src.evaluation.fraud_cycle_metrics import evaluate_cycle_fragments

        metrics = evaluate_cycle_fragments(
            predicted_rings=[
                {"ring_id": "P1", "participants": ["A", "B", "C"], "cycles": 5},
                {"ring_id": "P2", "participants": ["X", "Y", "Z"], "fragment_count": 2},
            ],
            ground_truth_rings=[
                {"ring_id": "G1", "participants": ["C", "B", "A"], "cycles": 3},
                {"ring_id": "G2", "participants": ["D", "E", "F"], "cycles": 4},
            ],
        )

        self.assertEqual(metrics["cycle_true_positives"], 3)
        self.assertEqual(metrics["cycle_false_positives"], 4)  # 2 extra on matched ring + 2 unmatched predicted fragments
        self.assertEqual(metrics["cycle_false_negatives"], 4)
        self.assertEqual(metrics["cycle_precision"], round(3 / 7, 6))
        self.assertEqual(metrics["cycle_recall"], round(3 / 7, 6))
        self.assertEqual(metrics["cycle_f1"], round(3 / 7, 6))
        self.assertEqual(metrics["matched_ring_count"], 1)

    def test_cycle_instances_are_counted_when_present(self):
        from src.evaluation.fraud_cycle_metrics import cycle_fragment_count

        self.assertEqual(
            cycle_fragment_count({"participants": ["A", "B", "C"], "cycles": 99, "cycle_instances": [{}, {}, {}]}),
            3,
        )

    def test_evaluate_cycle_fragment_file_reads_jsonl_and_ground_truth_json(self):
        from src.evaluation.fraud_cycle_metrics import evaluate_cycle_fragment_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            predictions_path = tmp / "predictions.jsonl"
            ground_truth_path = tmp / "ground_truth.json"
            predictions_path.write_text(
                json.dumps({"ring_id": "P1", "participants": ["A", "B", "C"], "cycles": 2, "is_fraud_ring": True}) + "\n"
                + json.dumps({"ring_id": "P2", "participants": ["X", "Y", "Z"], "cycles": 5, "is_fraud_ring": False}) + "\n",
                encoding="utf-8",
            )
            ground_truth_path.write_text(
                json.dumps({"rings": [{"ring_id": "G1", "participants": ["C", "B", "A"], "cycles": 3}]}),
                encoding="utf-8",
            )

            metrics = evaluate_cycle_fragment_file(predictions_path, ground_truth_path)

        self.assertEqual(metrics["cycle_true_positives"], 2)
        self.assertEqual(metrics["cycle_false_positives"], 0)
        self.assertEqual(metrics["cycle_false_negatives"], 1)
        self.assertEqual(metrics["predicted_cycle_fragments"], 2)
        self.assertEqual(metrics["ground_truth_cycle_fragments"], 3)


if __name__ == "__main__":
    unittest.main()
