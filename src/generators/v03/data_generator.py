"""v03 synthetic dataset generator.

It keeps v02's fraud-ring construction and replaces 90 of the 47,500 normal
transactions with two non-fraud, one-way background bridges per ring.
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

V03_DIR = Path(__file__).resolve().parent
V02_DIR = V03_DIR.parent / "v02"
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from account_generator import AccountGenerator  # noqa: E402
from fraud_ring_generator import FraudRingGenerator  # noqa: E402
from data_validator import DataValidator  # noqa: E402
from config_loader import ConfigLoader  # noqa: E402

# Load v03's transaction generator by path because v02 is placed on sys.path
# for the shared account/ring/validation classes.
import importlib.util  # noqa: E402

_transaction_spec = importlib.util.spec_from_file_location(
    "generator_v03_transaction", V03_DIR / "transaction_generator.py"
)
_transaction_module = importlib.util.module_from_spec(_transaction_spec)
assert _transaction_spec.loader is not None
_transaction_spec.loader.exec_module(_transaction_module)
TransactionGenerator = _transaction_module.TransactionGenerator


class SyntheticDataGeneratorV03:
    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path or V03_DIR / "config_d3.yaml")
        self.config = ConfigLoader(str(self.config_path)).load()
        self.seed = int(self.config["synthetic_data"].get("seed", 42))
        self.output = self.config["synthetic_data"]["output"]
        for key in ("raw_dir", "processed_dir", "ground_truth_dir"):
            Path(self.output[key]).mkdir(parents=True, exist_ok=True)

    def generate_all(self):
        np.random.seed(self.seed)
        account_gen = AccountGenerator(self.config)
        cfg_accounts = self.config["synthetic_data"]["accounts"]
        normal_accounts = account_gen.generate_normal_accounts(cfg_accounts["normal_account_count"])
        normal_accounts = normal_accounts.copy()
        normal_accounts["fraud_ring_member"] = False
        merchants = account_gen.generate_merchants(cfg_accounts["merchant_count"])

        fraudster_count = self._required_fraudster_account_count()
        fraudster_accounts = account_gen.generate_fraudster_accounts(fraudster_count)
        ring_gen = FraudRingGenerator(self.config, fraudster_accounts)
        fraud_rings, fraud_transactions = ring_gen.generate_all_rings()

        all_accounts = pd.concat([normal_accounts, fraudster_accounts], ignore_index=True)
        transaction_gen = TransactionGenerator(self.config, all_accounts)
        target_background = int(
            self.config["synthetic_data"]["total_transactions"]
            * self.config["synthetic_data"]["transactions"]["normal_transaction_ratio"]
        )
        normal_df, bridge_df = transaction_gen.generate_background_transactions(
            target_background, fraud_rings
        )
        if not bridge_df.empty:
            bridge_df = bridge_df.drop(columns=["background_ring_id"], errors="ignore")
        background_df = pd.concat([normal_df, bridge_df], ignore_index=True)

        fraud_df = pd.DataFrame(fraud_transactions)
        if not fraud_df.empty:
            fraud_df = fraud_df.copy()
            start_id = len(background_df) + 1
            fraud_df["transaction_id"] = [
                f"TXN_{start_id + index:09d}" for index in range(len(fraud_df))
            ]
            fraud_df["fraud_ring_id"] = fraud_df["ring_id"]
            fraud_df["amount_usd"] = fraud_df["amount"]
            fraud_df["original_amount"] = fraud_df["amount"]
            fraud_df["original_currency"] = "USD"
            timestamp = pd.to_datetime(fraud_df["timestamp"])
            fraud_df["date"] = timestamp.dt.strftime("%Y-%m-%d")
            fraud_df["hour"] = timestamp.dt.hour
            fraud_df["channel"] = "peer_to_peer"
            fraud_df["transaction_type"] = "fraud_ring"
            fraud_df = fraud_df.drop(columns=["amount", "ring_id"], errors="ignore")

        transactions = pd.concat([background_df, fraud_df], ignore_index=True)
        transactions = transactions.sample(frac=1, random_state=self.seed).reset_index(drop=True)
        DataValidator(self.config).validate(all_accounts, transactions, fraud_rings)
        self._save(all_accounts, merchants, transactions, fraud_rings)
        return all_accounts, merchants, transactions, fraud_rings

    def _required_fraudster_account_count(self) -> int:
        rings = self.config["synthetic_data"]["fraud_rings"]
        distribution = rings["ring_distribution"]
        characteristics = rings["ring_characteristics"]
        return sum(
            int(distribution[key]) * int(characteristics[profile]["participant_count"])
            for key, profile in (
                ("small_rings_3person", "small"),
                ("medium_rings_5person", "medium"),
                ("large_rings_8person", "large"),
            )
        )

    def _save(self, accounts, merchants, transactions, fraud_rings):
        accounts.to_csv(Path(self.output["raw_dir"]) / self.output["accounts_file"], index=False)
        merchants.to_csv(Path(self.output["raw_dir"]) / self.output["merchants_file"], index=False)
        transactions.to_csv(Path(self.output["raw_dir"]) / self.output["transactions_file"], index=False)
        ring_gen = FraudRingGenerator(self.config, accounts)
        ring_gen.fraud_rings = fraud_rings
        ring_gen.save_rings_to_json(
            str(Path(self.output["ground_truth_dir"]) / self.output["fraud_rings_file"])
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a v03 synthetic fraud-ring dataset")
    parser.add_argument(
        "--config",
        type=Path,
        default=V03_DIR / "config_d3.yaml",
        help="YAML configuration path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    SyntheticDataGeneratorV03(args.config).generate_all()
