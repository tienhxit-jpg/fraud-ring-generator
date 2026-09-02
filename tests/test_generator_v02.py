import unittest

import pandas as pd


class GeneratorV02Tests(unittest.TestCase):
    def _config(self):
        return {
            "project": {"seed": 42},
            "synthetic_data": {
                "seed": 42,
                "start_date": "2025-10-01",
                "fraud_rings": {
                    "total_ring_count": 3,
                    "ring_distribution": {
                        "small_rings_3person": 1,
                        "medium_rings_5person": 1,
                        "large_rings_8person": 1,
                    },
                    "ring_characteristics": {
                        "small": {"cycles_per_ring_min": 1, "cycles_per_ring_max": 1, "total_amount_min": 300, "total_amount_max": 300},
                        "medium": {"cycles_per_ring_min": 1, "cycles_per_ring_max": 1, "total_amount_min": 500, "total_amount_max": 500},
                        "large": {"cycles_per_ring_min": 1, "cycles_per_ring_max": 1, "total_amount_min": 800, "total_amount_max": 800, "transactions_per_cycle_min": 8, "transactions_per_cycle_max": 8},
                    },
                    "ring_types": {"money_laundering": 1},
                    "amount_patterns": {"escalating": False, "escalation_factor": 0.0},
                    "activity_patterns": {"typical_hours": [8]},
                },
            },
        }

    def test_fraud_ring_generator_uses_fraudster_pool_without_orphans(self):
        import sys
        from pathlib import Path

        generator_dir = Path("src/generators/v02").resolve()
        if str(generator_dir) not in sys.path:
            sys.path.insert(0, str(generator_dir))
        from fraud_ring_generator import FraudRingGenerator

        fraudster_accounts = pd.DataFrame({"account_id": [f"ACC_F{i:03d}" for i in range(16)]})
        normal_accounts = pd.DataFrame({"account_id": [f"ACC_N{i:03d}" for i in range(20)]})

        generator = FraudRingGenerator(self._config(), fraudster_accounts)
        rings, txns = generator.generate_all_rings()

        ring_participants = {account for ring in rings for account in ring["participants"]}
        self.assertEqual(len(ring_participants), 16)
        self.assertTrue(ring_participants.issubset(set(fraudster_accounts["account_id"])))
        self.assertTrue(ring_participants.isdisjoint(set(normal_accounts["account_id"])))
        self.assertEqual({txn["source_account"] for txn in txns} | {txn["destination_account"] for txn in txns}, ring_participants)


if __name__ == "__main__":
    unittest.main()
