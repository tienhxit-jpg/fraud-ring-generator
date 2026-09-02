import json
import tempfile
import unittest
from pathlib import Path


class FraudRingMetricsTests(unittest.TestCase):
    def test_exact_participant_set_metrics(self):
        from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings

        metrics = evaluate_fraud_rings(
            predicted_rings=[
                {"ring_id": "P1", "participants": ["B", "A", "C"], "ring_type": "phishing"},
                {"ring_id": "P2", "participants": ["X", "Y", "Z"], "ring_type": "collusion"},
            ],
            ground_truth_rings=[
                {"ring_id": "G1", "participants": ["A", "B", "C"], "ring_type": "phishing"},
                {"ring_id": "G2", "participants": ["D", "E", "F"], "ring_type": "money_laundering"},
            ],
        )

        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 1)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(metrics["f1"], 0.5)
        self.assertEqual(metrics["ring_type_accuracy_on_matches"], 1.0)

    def test_filter_predicted_rings_uses_is_fraud_ring_when_present(self):
        from src.evaluation.fraud_ring_metrics import filter_predicted_rings

        filtered = filter_predicted_rings(
            [
                {"ring_id": "P1", "participants": ["A"], "is_fraud_ring": True},
                {"ring_id": "P2", "participants": ["B"], "is_fraud_ring": False},
                {"ring_id": "P3", "participants": ["C"]},
            ]
        )

        self.assertEqual([ring["ring_id"] for ring in filtered], ["P1", "P3"])

    def test_partial_overlap_matching_can_be_enabled(self):
        from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings

        exact_metrics = evaluate_fraud_rings(
            predicted_rings=[{"ring_id": "P1", "participants": ["A", "B", "C", "D"]}],
            ground_truth_rings=[{"ring_id": "G1", "participants": ["A", "B", "C"]}],
            min_jaccard=1.0,
        )
        overlap_metrics = evaluate_fraud_rings(
            predicted_rings=[{"ring_id": "P1", "participants": ["A", "B", "C", "D"]}],
            ground_truth_rings=[{"ring_id": "G1", "participants": ["A", "B", "C"]}],
            min_jaccard=0.75,
        )

        self.assertEqual(exact_metrics["true_positives"], 0)
        self.assertEqual(overlap_metrics["true_positives"], 1)
        self.assertEqual(overlap_metrics["precision"], 1.0)
        self.assertEqual(overlap_metrics["recall"], 1.0)
        self.assertEqual(overlap_metrics["mean_match_jaccard"], 0.75)

    def test_evaluate_fraud_ring_file_reads_jsonl_and_ground_truth_json(self):
        from src.evaluation.fraud_ring_metrics import evaluate_fraud_ring_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            predictions_path = tmp / "predictions.jsonl"
            ground_truth_path = tmp / "fraud_rings.json"
            predictions_path.write_text(
                json.dumps({"ring_id": "P1", "participants": ["A", "B", "C"], "is_fraud_ring": True}) + "\n"
                + json.dumps({"ring_id": "P2", "participants": ["X", "Y", "Z"], "is_fraud_ring": False}) + "\n",
                encoding="utf-8",
            )
            ground_truth_path.write_text(
                json.dumps({"rings": [{"ring_id": "G1", "participants": ["C", "B", "A"]}]}),
                encoding="utf-8",
            )

            metrics = evaluate_fraud_ring_file(predictions_path, ground_truth_path)

        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_positives"], 0)
        self.assertEqual(metrics["false_negatives"], 0)
        self.assertEqual(metrics["f1"], 1.0)

    def test_project_gds_cycle_v01_matches_ground_truth_exactly(self):
        from src.evaluation.fraud_ring_metrics import evaluate_fraud_ring_file

        metrics = evaluate_fraud_ring_file(
            "data/cycledetection/gds_cycle/v01.jsonl",
            "data/synthetic/v2/ground_truth/fraud_rings.json",
        )

        self.assertEqual(metrics["predicted_count"], 45)
        self.assertEqual(metrics["ground_truth_count"], 45)
        self.assertEqual(metrics["true_positives"], 45)
        self.assertEqual(metrics["false_positives"], 0)
        self.assertEqual(metrics["false_negatives"], 0)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
