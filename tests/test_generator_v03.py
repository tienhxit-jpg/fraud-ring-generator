import importlib.util
from pathlib import Path

import networkx as nx
import pandas as pd


def load_v03_transaction_generator():
    module_path = Path("src/generators/v03/transaction_generator.py").resolve()
    spec = importlib.util.spec_from_file_location("generator_v03_transaction", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.TransactionGenerator


def make_config(direction="alternate_by_ring", bridges_per_ring=2):
    return {
        "project": {"seed": 42},
        "synthetic_data": {
            "seed": 42,
            "start_date": "2025-10-01",
            "end_date": "2025-12-31",
            "transactions": {
                "channels": {"online": 1.0},
                "amounts": {"currency_distribution": {"USD": 1.0}},
                "exchange_rates": {"VND_to_USD": 25000, "EUR_to_USD": 1.08, "GBP_to_USD": 1.27},
            },
            "normal_transaction_rules": {
                "amount_mean": 100,
                "amount_std": 10,
                "amount_min": 10,
                "amount_max": 1000,
                "business_hours_probability": 1.0,
            },
            "background_connectivity": {
                "enabled": True,
                "bridges_per_ring": bridges_per_ring,
                "direction_strategy": direction,
                "amount_min": 10,
                "amount_max": 100,
                "channels": {"online": 1.0},
            },
        },
    }


def make_accounts():
    rows = []
    for index in range(12):
        rows.append({"account_id": f"N{index}", "fraud_ring_member": False})
    for account_id in ["F1", "F2", "F3", "F4", "F5", "F6"]:
        rows.append({"account_id": account_id, "fraud_ring_member": True})
    return pd.DataFrame(rows)


def make_rings():
    return [
        {"ring_id": "R1", "participants": ["F1", "F2", "F3"]},
        {"ring_id": "R2", "participants": ["F4", "F5", "F6"]},
    ]


def ring_edges():
    return [
        ("F1", "F2"), ("F2", "F3"), ("F3", "F1"),
        ("F4", "F5"), ("F5", "F6"), ("F6", "F4"),
    ]


def test_bridge_transactions_connect_each_ring_without_using_fraud_labels():
    TransactionGenerator = load_v03_transaction_generator()
    generator = TransactionGenerator(make_config(), make_accounts())

    bridges = generator.generate_background_bridge_transactions(make_rings())

    assert len(bridges) == 4
    assert {row["background_ring_id"] for row in bridges} == {"R1", "R2"}
    assert all(row["is_fraud"] == 0 for row in bridges)
    assert all(row["fraud_ring_id"] is None for row in bridges)
    assert all(row["transaction_type"] == "background_bridge" for row in bridges)


def test_each_ring_uses_only_one_bridge_direction_so_scc_does_not_expand():
    TransactionGenerator = load_v03_transaction_generator()
    generator = TransactionGenerator(make_config(), make_accounts())

    bridges = generator.generate_background_bridge_transactions(make_rings())
    normal_ids = {f"N{index}" for index in range(12)}
    directions_by_ring = {}
    for row in bridges:
        ring_id = row["background_ring_id"]
        direction = "outbound" if row["destination_account"] in normal_ids else "inbound"
        directions_by_ring.setdefault(ring_id, set()).add(direction)

    assert all(len(directions) == 1 for directions in directions_by_ring.values())

    graph = nx.DiGraph()
    graph.add_edges_from(ring_edges())
    graph.add_edges_from((row["source_account"], row["destination_account"]) for row in bridges)
    components = {frozenset(component) for component in nx.strongly_connected_components(graph) if len(component) >= 3}

    assert frozenset(["F1", "F2", "F3"]) in components
    assert frozenset(["F4", "F5", "F6"]) in components


def test_background_budget_replaces_core_transactions_instead_of_increasing_total():
    TransactionGenerator = load_v03_transaction_generator()
    generator = TransactionGenerator(make_config(bridges_per_ring=2), make_accounts())

    core, bridges = generator.generate_background_transactions(total_count=20, fraud_rings=make_rings())

    assert len(core) == 16
    assert len(bridges) == 4
    assert len(core) + len(bridges) == 20
