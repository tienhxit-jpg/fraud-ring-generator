import os, json
from neo4j import GraphDatabase

driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
database = os.environ.get("NEO4J_DATABASE", "neo4j")
queries = {
    "components": "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition",
    "labels": "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label",
    "rels": "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type",
    "fingerprint": "MATCH (a:Account) WITH count(a) AS accounts MATCH (t:Transaction) WITH accounts, count(t) AS transactions MATCH (:Account)-[:SENT]->(tx:Transaction)-[:RECEIVED_BY]->(:Account) WITH accounts, transactions, count(tx) AS logical_edges MATCH (s:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(d:Account) WITH accounts, transactions, logical_edges, count(DISTINCT [s.account_id,d.account_id]) AS logical_pairs OPTIONAL MATCH ()-[r:TRANSFER_AGG]->() RETURN accounts, transactions, logical_edges, logical_pairs, count(r) AS transfer_agg",
    "account_props": "MATCH (a:Account) UNWIND keys(a) AS k RETURN k, count(*) AS present ORDER BY k",
    "tx_props": "MATCH (t:Transaction) UNWIND keys(t) AS k RETURN k, count(*) AS present ORDER BY k",
    "gt": "MATCH (a:Account) WHERE a.fraud_ring_id IS NOT NULL RETURN a.fraud_ring_id AS ring_id, count(*) AS size ORDER BY ring_id",
    "gds_procs": "SHOW PROCEDURES YIELD name WHERE name IN ['gds.graph.project','gds.graph.project.cypher','gds.scc.stream','gds.wcc.stream','gds.version'] RETURN name ORDER BY name",
}
output = {}
with driver.session(database=database) as session:
    for name, query in queries.items():
        try:
            output[name] = [record.data() for record in session.run(query)]
        except Exception as exc:
            output[name] = {"error": str(exc)}
driver.close()
print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
