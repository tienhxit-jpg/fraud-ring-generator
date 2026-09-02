"""v03 background transaction generator.

The v02 generator kept fraud-ring accounts completely isolated from background
traffic. v03 replaces a small part of the normal-normal transaction budget with
one-way normal-ring bridge transactions. Every ring therefore participates in
background traffic, while one-way direction per ring prevents the bridge from
expanding that ring's strongly connected component or creating cross-boundary
cycles.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd


class TransactionGenerator:
    def __init__(self, config: Dict, accounts: pd.DataFrame):
        self.config = config
        self.accounts = accounts
        self.cfg_txn = config["synthetic_data"]["transactions"]
        self.cfg_normal = config["synthetic_data"]["normal_transaction_rules"]
        self.cfg_connectivity = config["synthetic_data"].get("background_connectivity", {})

    def _normal_account_ids(self) -> np.ndarray:
        flags = self.accounts.get("fraud_ring_member")
        if flags is None:
            return self.accounts["account_id"].values
        return self.accounts[~flags.fillna(False).astype(bool)]["account_id"].values

    def _random_timestamp(self) -> datetime:
        start = datetime.strptime(self.config["synthetic_data"]["start_date"], "%Y-%m-%d")
        end = datetime.strptime(self.config["synthetic_data"]["end_date"], "%Y-%m-%d")
        random_days = int(np.random.randint(0, max((end - start).days, 1)))
        if np.random.random() < self.cfg_normal["business_hours_probability"]:
            hour = int(np.random.choice(range(8, 18)))
        else:
            hour = int(np.random.choice(range(24)))
        return start + timedelta(days=random_days, hours=hour, minutes=int(np.random.randint(0, 60)))

    def _currency_and_amount(self) -> Tuple[str, float, float]:
        amount = np.random.lognormal(
            mean=np.log(self.cfg_normal["amount_mean"]),
            sigma=self.cfg_normal["amount_std"] / self.cfg_normal["amount_mean"],
        )
        amount = float(np.clip(amount, self.cfg_normal["amount_min"], self.cfg_normal["amount_max"]))
        currencies = list(self.cfg_txn["amounts"]["currency_distribution"].keys())
        probabilities = list(self.cfg_txn["amounts"]["currency_distribution"].values())
        currency = str(np.random.choice(currencies, p=probabilities))
        rates = self.cfg_txn["exchange_rates"]
        if currency == "VND":
            amount_usd = amount / rates["VND_to_USD"]
        elif currency == "EUR":
            amount_usd = amount * rates["EUR_to_USD"]
        elif currency == "GBP":
            amount_usd = amount * rates["GBP_to_USD"]
        else:
            amount_usd = amount
        return currency, amount, amount_usd

    @staticmethod
    def _transaction_record(
        transaction_id: str,
        source: str,
        destination: str,
        amount_usd: float,
        original_amount: float,
        currency: str,
        timestamp: datetime,
        channel: str,
        transaction_type: str,
    ) -> Dict:
        return {
            "transaction_id": transaction_id,
            "source_account": source,
            "destination_account": destination,
            "amount_usd": round(float(amount_usd), 2),
            "original_amount": round(float(original_amount), 2),
            "original_currency": currency,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "date": timestamp.strftime("%Y-%m-%d"),
            "hour": timestamp.hour,
            "channel": channel,
            "transaction_type": transaction_type,
            "is_fraud": 0,
            "fraud_ring_id": None,
        }

    def generate_normal_transactions(self, count: int) -> pd.DataFrame:
        normal_accounts = self._normal_account_ids()
        if len(normal_accounts) < 2 and count:
            raise ValueError("At least two normal accounts are required")
        channels = list(self.cfg_txn["channels"].keys())
        channel_probs = list(self.cfg_txn["channels"].values())
        records: List[Dict] = []
        for index in range(count):
            source = str(np.random.choice(normal_accounts))
            destination = str(np.random.choice(normal_accounts))
            while destination == source:
                destination = str(np.random.choice(normal_accounts))
            currency, amount, amount_usd = self._currency_and_amount()
            timestamp = self._random_timestamp()
            channel = str(np.random.choice(channels, p=channel_probs))
            records.append(
                self._transaction_record(
                    f"TXN_{index + 1:09d}", source, destination, amount_usd,
                    amount, currency, timestamp, channel, "p2p",
                )
            )
        return pd.DataFrame(records)

    def generate_background_bridge_transactions(self, fraud_rings: Sequence[Dict]) -> List[Dict]:
        """Create non-fraud one-way bridges between every ring and normal traffic.

        A ring uses exactly one direction for all of its bridges. With
        ``alternate_by_ring``, even-index rings send to normal accounts and
        odd-index rings receive from normal accounts. This adds realistic external
        activity without making the background and ring mutually reachable.
        """
        if not self.cfg_connectivity.get("enabled", False):
            return []
        bridges_per_ring = int(self.cfg_connectivity.get("bridges_per_ring", 1))
        if bridges_per_ring < 1:
            return []
        strategy = self.cfg_connectivity.get("direction_strategy", "alternate_by_ring")
        if strategy not in {"outbound", "inbound", "alternate_by_ring"}:
            raise ValueError(f"Unsupported bridge direction strategy: {strategy}")

        normal_accounts = self._normal_account_ids()
        bridge_channels = self.cfg_connectivity.get("channels", self.cfg_txn["channels"])
        channels = list(bridge_channels.keys())
        probabilities = list(bridge_channels.values())
        amount_min = float(self.cfg_connectivity.get("amount_min", self.cfg_normal["amount_min"]))
        amount_max = float(self.cfg_connectivity.get("amount_max", self.cfg_normal["amount_mean"]))
        records: List[Dict] = []

        for ring_index, ring in enumerate(fraud_rings):
            participants = [str(item) for item in ring.get("participants", [])]
            if not participants:
                raise ValueError(f"Ring {ring.get('ring_id', ring_index)} has no participants")
            direction = strategy
            if strategy == "alternate_by_ring":
                direction = "outbound" if ring_index % 2 == 0 else "inbound"
            for _ in range(bridges_per_ring):
                ring_account = str(np.random.choice(participants))
                normal_account = str(np.random.choice(normal_accounts))
                source, destination = (
                    (ring_account, normal_account) if direction == "outbound"
                    else (normal_account, ring_account)
                )
                amount = float(np.random.uniform(amount_min, amount_max))
                timestamp = self._random_timestamp()
                channel = str(np.random.choice(channels, p=probabilities))
                record = self._transaction_record(
                    "", source, destination, amount, amount, "USD",
                    timestamp, channel, "background_bridge",
                )
                # Generator-only provenance for validation. data_generator removes
                # this field before writing CSV so detectors cannot use ring ids.
                record["background_ring_id"] = str(ring.get("ring_id", ring_index))
                records.append(record)
        return records

    def generate_background_transactions(
        self, total_count: int, fraud_rings: Sequence[Dict]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        bridge_records = self.generate_background_bridge_transactions(fraud_rings)
        if len(bridge_records) > total_count:
            raise ValueError(
                f"Bridge budget ({len(bridge_records)}) exceeds background transaction budget ({total_count})"
            )
        core = self.generate_normal_transactions(total_count - len(bridge_records))
        for index, record in enumerate(bridge_records, start=len(core) + 1):
            record["transaction_id"] = f"TXN_{index:09d}"
        return core, pd.DataFrame(bridge_records)
