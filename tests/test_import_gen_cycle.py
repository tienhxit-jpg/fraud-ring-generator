import tempfile
import unittest
from pathlib import Path

from src.neo4jupdate.import_gen_cycle import (
    GenCycleNeo4jImporter,
    load_fraud_metadata,
    normalize_account,
    normalize_transaction,
)


class FakeResult:
    def __init__(self, record=None):
        self.record = record or {}

    def consume(self):
        return None

    def single(self):
        return self.record


class FakeSession:
    def __init__(self):
        self.calls = []

    def run(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return FakeResult({
            "accounts": 2,
            "transactions": 2,
            "sent_relationships": 2,
            "received_relationships": 2,
            "fraud_accounts": 2,
            "fraud_transactions": 2,
        })


class FakeSessionContext(FakeSession):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDriver:
    def __init__(self):
        self.session_obj = FakeSessionContext()

    def session(self, **kwargs):
        return self.session_obj

    def close(self):
        pass


class ImportGenCycleTests(unittest.TestCase):
    def write(self, root: Path, rel: str, text: str) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def make_dataset(self, root: Path) -> Path:
        data_dir = root / "genCycle"
        self.write(
            data_dir,
            "accounts/accounts_0_0.csv",
            "account_id,customer_name,balance,risk_score,creation_date\n"
            "acc_a,Alice,1000,0.91,2023-01-01\n"
            "acc_b,Bob,2000,0.82,2023-01-01\n",
        )
        self.write(
            data_dir,
            "transactions/transactions_0_0.csv",
            "tx_id,src_id,dst_id,amount,timestamp,description,embedding\n"
            "tx_1,acc_a,acc_b,12.5,2024-01-01T10:00:00,p2p,1|2|3\n",
        )
        self.write(
            data_dir,
            "fraud/fraud_cases.csv",
            "pattern_id,start_acc_id,pattern_type,depth,involved_accounts\n"
            "pat_1,acc_a,cycle,2,acc_a|acc_b\n",
        )
        self.write(
            data_dir,
            "fraud/transactions_fraud.csv",
            "tx_id,src_id,dst_id,amount,timestamp,description,embedding\n"
            "tx_f1,acc_a,acc_b,9999,2024-01-01T12:00:00,shell,4|5|6\n"
            "tx_f2,acc_b,acc_a,9999,2024-01-01T12:01:00,return,7|8|9\n",
        )
        return data_dir

    def test_fraud_metadata_derives_account_and_cycle_edge_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = self.make_dataset(Path(tmp))
            fraud = load_fraud_metadata(data_dir)

        self.assertEqual(fraud.account_to_ring_ids["acc_a"], ["pat_1"])
        self.assertEqual(fraud.edge_to_ring_ids[("acc_a", "acc_b")], ["pat_1"])
        self.assertEqual(fraud.edge_to_ring_ids[("acc_b", "acc_a")], ["pat_1"])
        self.assertEqual(fraud.ring_depth["pat_1"], 2)

    def test_normalize_account_matches_synthetic_importer_property_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = self.make_dataset(Path(tmp))
            fraud = load_fraud_metadata(data_dir)
            account = normalize_account(
                {"account_id": "acc_a", "customer_name": "Alice", "risk_score": 0.91},
                fraud,
            )

        self.assertEqual(account["customer_id"], "customer_acc_a")
        self.assertEqual(account["kyc_risk_score"], 0.91)
        self.assertTrue(account["fraud_ring_member"])
        self.assertEqual(account["fraud_ring_ids"], "pat_1")

    def test_normalize_transaction_maps_gencycle_columns_and_drops_embedding_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = self.make_dataset(Path(tmp))
            fraud = load_fraud_metadata(data_dir)
            tx = normalize_transaction(
                {
                    "tx_id": "tx_f1",
                    "src_id": "acc_a",
                    "dst_id": "acc_b",
                    "amount": 9999,
                    "timestamp": "2024-01-01T12:00:00",
                    "description": "shell",
                    "embedding": "1|2|3",
                },
                fraud,
                is_fraud_file=True,
            )

        self.assertEqual(tx["transaction_id"], "tx_f1")
        self.assertEqual(tx["source_account"], "acc_a")
        self.assertEqual(tx["destination_account"], "acc_b")
        self.assertEqual(tx["amount_usd"], 9999)
        self.assertEqual(tx["date"], "2024-01-01")
        self.assertEqual(tx["is_fraud"], 1)
        self.assertEqual(tx["fraud_ring_id"], "pat_1")
        self.assertNotIn("embedding", tx)

    def test_importer_streams_files_and_uses_synthetic_graph_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = self.make_dataset(Path(tmp))
            importer = GenCycleNeo4jImporter("bolt://unused", "neo4j", "pw", data_dir=data_dir, batch_size=2)
            importer.driver = FakeDriver()
            stats = importer.import_all(clear_first=False)

        self.assertEqual(stats.accounts, 2)
        self.assertEqual(stats.transactions, 3)
        self.assertEqual(stats.fraud_cases, 1)
        self.assertEqual(stats.fraud_transactions, 2)

        all_queries = "\n".join(query for query, _ in importer.driver.session_obj.calls)
        self.assertIn("MERGE (c:Customer {customer_id: row.customer_id})", all_queries)
        self.assertIn("MERGE (c)-[:OWNS]->(a)", all_queries)
        self.assertIn("MATCH (src:Account {account_id: row.source_account})", all_queries)
        self.assertIn("MERGE (src)-[sent:SENT]->(t)", all_queries)
        self.assertIn("MERGE (t)-[received:RECEIVED_BY]->(dst)", all_queries)
        self.assertNotIn(":FraudRing", all_queries)
        self.assertNotIn("MEMBER_OF", all_queries)
        self.assertNotIn("PART_OF", all_queries)

    def test_verify_counts_has_no_ground_truth_relationship_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = self.make_dataset(Path(tmp))
            importer = GenCycleNeo4jImporter("bolt://unused", "neo4j", "pw", data_dir=data_dir)
            importer.driver = FakeDriver()
            counts = importer.verify_counts()

        query = importer.driver.session_obj.calls[0][0]
        self.assertEqual(counts["accounts"], 2)
        self.assertNotIn(":FraudRing", query)
        self.assertNotIn("MEMBER_OF", query)
        self.assertNotIn("PART_OF", query)


if __name__ == "__main__":
    unittest.main()
