import unittest
from pathlib import Path

from src.neo4jupdate.import_synthetic import SyntheticNeo4jImporter, _load_csv


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
            "accounts": 1,
            "transactions": 1,
            "merchants": 1,
            "sent_relationships": 1,
            "received_relationships": 1,
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


class FakeClearSession(FakeSessionContext):
    def __init__(self, deleted_counts):
        super().__init__()
        self.deleted_counts = list(deleted_counts)

    def run(self, query, **kwargs):
        self.calls.append((query, kwargs))
        deleted = self.deleted_counts.pop(0) if self.deleted_counts else 0
        return FakeResult({"deleted": deleted})


class FakeClearDriver(FakeDriver):
    def __init__(self, deleted_counts):
        self.session_obj = FakeClearSession(deleted_counts)


class ImportSyntheticTests(unittest.TestCase):
    def test_default_data_dir_matches_v2_layout_and_loads_new_files(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw")
        raw_dir = importer._resolve_raw_dir()

        self.assertEqual(raw_dir, Path("data/synthetic/v2/raw"))

        data = importer.load_data()
        self.assertGreater(len(data["accounts"]), 0)
        self.assertGreater(len(data["merchants"]), 0)
        self.assertGreater(len(data["transactions"]), 0)
        self.assertNotIn("fraud_rings", data)
        self.assertIn("fraud_ring_member", data["accounts"][0])
        self.assertIn("amount_usd", data["transactions"][0])

    def test_raw_dir_argument_is_supported(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw", data_dir="data/synthetic/v2/raw")
        raw_dir = importer._resolve_raw_dir()

        self.assertEqual(raw_dir, Path("data/synthetic/v2/raw"))

    def test_csv_loader_preserves_fraud_labels_and_boolean_membership(self):
        accounts = _load_csv(Path("data/synthetic/v2/raw/accounts.csv"))
        transactions = _load_csv(Path("data/synthetic/v2/raw/transactions.csv"))

        self.assertIsInstance(accounts[0]["fraud_ring_member"], bool)
        self.assertIn(transactions[0]["is_fraud"], {0, 1})

    def test_schema_does_not_create_fraud_ring_constraints_or_indexes(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw")
        importer.driver = FakeDriver()

        importer.prepare_schema()

        all_queries = "\n".join(query for query, _ in importer.driver.session_obj.calls)
        self.assertNotIn(":FraudRing", all_queries)
        self.assertNotIn("fraud_ring_id_unique", all_queries)
        self.assertIn("transaction_ring_idx", all_queries)

    def test_clear_database_deletes_in_limited_batches_to_avoid_memory_error(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw", clear_batch_size=2)
        importer.driver = FakeClearDriver([2, 2, 0])

        deleted = importer.clear_database()
        query = importer.driver.session_obj.calls[0][0]
        params = importer.driver.session_obj.calls[0][1]

        self.assertEqual(deleted, 4)
        self.assertIn("WITH n LIMIT $batch_size", query)
        self.assertIn("DETACH DELETE n", query)
        self.assertEqual(params["batch_size"], 2)
        self.assertEqual(len(importer.driver.session_obj.calls), 3)

    def test_transaction_import_uses_amount_usd_and_does_not_reset_fraud_fields(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw")
        session = FakeSession()

        importer._import_transactions(
            session,
            [
                {
                    "transaction_id": "TXN_1",
                    "source_account": "A",
                    "destination_account": "B",
                    "amount_usd": 123.4,
                    "is_fraud": 1,
                    "fraud_ring_id": "RING_1",
                }
            ],
        )

        query = session.calls[0][0]
        self.assertIn("coalesce(row.amount_usd, row.amount, row.original_amount, 0.0) AS amount", query)
        self.assertIn("sent.amount_usd = amount", query)
        self.assertNotIn("SET t.is_fraud = 0", query)
        self.assertNotIn("t.fraud_ring_id = null", query)
        self.assertIn("SET t += row", query)

    def test_importer_has_no_ground_truth_fraud_ring_node_import_path(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw")

        self.assertFalse(hasattr(importer, "_import_fraud_rings"))

    def test_verify_counts_does_not_query_fraud_ring_nodes_or_memberships(self):
        importer = SyntheticNeo4jImporter("bolt://unused", "neo4j", "pw")
        importer.driver = FakeDriver()

        counts = importer.verify_counts()
        query = importer.driver.session_obj.calls[0][0]

        self.assertEqual(counts["accounts"], 1)
        self.assertNotIn(":FraudRing", query)
        self.assertNotIn("MEMBER_OF", query)
        self.assertNotIn("PART_OF", query)


if __name__ == "__main__":
    unittest.main()
