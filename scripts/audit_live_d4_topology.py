import json, os
from collections import Counter
from pathlib import Path

import networkx as nx
from neo4j import GraphDatabase

root = Path("data/cycledetection")
run_pointer = root / (".current_d5_run" if (root / ".current_d5_run").exists() else ".current_d4_run")
run_id = run_pointer.read_text().strip()
run_dir = root / run_id

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)
database = os.environ.get("NEO4J_DATABASE", "neo4j")
with driver.session(database=database) as session:
    edges = [(r["src"], r["dst"]) for r in session.run(
        "MATCH (s:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(d:Account) "
        "RETURN DISTINCT s.account_id AS src, d.account_id AS dst"
    )]
    boundary = session.run(
        "MATCH (s:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(d:Account) "
        "WITH s,d,t, coalesce(s.fraud_ring_member,false) AS sf, coalesce(d.fraud_ring_member,false) AS df "
        "RETURN sum(CASE WHEN sf AND NOT df THEN 1 ELSE 0 END) AS ring_to_background, "
        "sum(CASE WHEN NOT sf AND df THEN 1 ELSE 0 END) AS background_to_ring, "
        "sum(CASE WHEN sf AND df AND s.fraud_ring_ids <> d.fraud_ring_ids THEN 1 ELSE 0 END) AS between_ring_members, "
        "sum(CASE WHEN coalesce(t.is_fraud,0) = 1 THEN 1 ELSE 0 END) AS fraud_transactions"
    ).single().data()
    amount_profile = session.run(
        "MATCH (t:Transaction) RETURN "
        "min(t.amount_usd) AS min_all, max(t.amount_usd) AS max_all, "
        "min(CASE WHEN coalesce(t.is_fraud,0) = 1 THEN t.amount_usd END) AS min_fraud, "
        "max(CASE WHEN coalesce(t.is_fraud,0) = 1 THEN t.amount_usd END) AS max_fraud, "
        "sum(CASE WHEN t.amount_usd = 9999 THEN 1 ELSE 0 END) AS exact_9999"
    ).single().data()
driver.close()

graph = nx.DiGraph()
graph.add_edges_from(edges)
sizes = sorted((len(component) for component in nx.strongly_connected_components(graph)), reverse=True)
output = {
    "logical_pairs": len(edges),
    "scc_count": len(sizes),
    "largest_scc_sizes": sizes[:10],
    "eligible_scc_3_12": sum(3 <= size <= 12 for size in sizes),
    "boundary": boundary,
    "amount_profile": amount_profile,
}
(run_dir / "post_detection_topology.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(output, ensure_ascii=False, indent=2))
