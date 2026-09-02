import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.neo4j_config import NEO4J_CONFIG
from neo4j import GraphDatabase

GRAPH = "fraud_cycle_gds_directed"

def run(session, title, query, **params):
    print(f"\n## {title}")
    try:
        rows = [dict(r) for r in session.run(query, **params)]
        for row in rows:
            print(row)
        if not rows:
            print("<no rows>")
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc))

with GraphDatabase.driver(NEO4J_CONFIG.uri, auth=(NEO4J_CONFIG.user, NEO4J_CONFIG.password)) as driver:
    driver.verify_connectivity()
    kwargs = {"database": NEO4J_CONFIG.database} if NEO4J_CONFIG.database else {}
    with driver.session(**kwargs) as session:
        run(session, "schema_counts", """
        MATCH (a:Account)
        WITH count(a) AS accounts
        MATCH (t:Transaction)
        WITH accounts, count(t) AS transactions
        MATCH ()-[s:SENT]->()
        WITH accounts, transactions, count(s) AS sent
        MATCH ()-[r:RECEIVED_BY]->()
        WITH accounts, transactions, sent, count(r) AS received_by
        MATCH (:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(:Account)
        RETURN accounts, transactions, sent, received_by, count(t) AS derived_edges
        """)
        run(session, "fraud_marker_counts", """
        MATCH (a:Account)
        WITH count { (a) WHERE coalesce(a.fraud_ring_member,false)=true } AS fraud_accounts,
             count { (a) WHERE a.fraud_ring_ids IS NOT NULL } AS accounts_with_ring_ids,
             count(a) AS accounts
        MATCH (t:Transaction)
        RETURN accounts, fraud_accounts, accounts_with_ring_ids,
               count(t) AS transactions,
               count { (t) WHERE coalesce(t.is_fraud,0)=1 } AS fraud_transactions,
               count { (t) WHERE t.fraud_ring_id IS NOT NULL } AS tx_with_ring_id
        """)
        run(session, "fraud_ring_id_distribution_accounts", """
        MATCH (a:Account)
        WHERE a.fraud_ring_ids IS NOT NULL AND a.fraud_ring_ids <> ''
        UNWIND split(toString(a.fraud_ring_ids), '|') AS ring_id
        RETURN ring_id, count(DISTINCT a) AS participants
        ORDER BY participants DESC, ring_id
        LIMIT 30
        """)
        run(session, "fraud_transaction_ring_distribution", """
        MATCH (t:Transaction)
        WHERE t.fraud_ring_id IS NOT NULL
        RETURN t.fraud_ring_id AS ring_id, count(t) AS txs,
               count(DISTINCT [(src:Account)-[:SENT]->(t) | src.account_id][0]) AS sources,
               count(DISTINCT [(t)-[:RECEIVED_BY]->(dst:Account) | dst.account_id][0]) AS destinations
        ORDER BY txs DESC, ring_id
        LIMIT 30
        """)
        run(session, "gds_version", "RETURN gds.version() AS version")
        exists = session.run("CALL gds.graph.exists($graph) YIELD exists RETURN exists", graph=GRAPH).single()["exists"]
        if exists:
            run(session, "drop_existing_projection", "CALL gds.graph.drop($graph) YIELD graphName RETURN graphName", graph=GRAPH)
        run(session, "project_account_transfer_graph", """
        CALL gds.graph.project.cypher(
          $graph,
          'MATCH (a:Account) RETURN id(a) AS id',
          'MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account) RETURN id(src) AS source, id(dst) AS target, coalesce(t.amount_usd, t.amount, 0.0) AS amount'
        )
        YIELD graphName, nodeCount, relationshipCount, projectMillis
        RETURN graphName, nodeCount, relationshipCount, projectMillis
        """, graph=GRAPH)
        run(session, "scc_histogram", """
        CALL gds.scc.stream($graph)
        YIELD nodeId, componentId
        WITH componentId, count(*) AS component_size
        RETURN component_size, count(*) AS component_count
        ORDER BY component_size DESC
        LIMIT 20
        """, graph=GRAPH)
        run(session, "scc_components_containing_fraud_accounts", """
        CALL gds.scc.stream($graph)
        YIELD nodeId, componentId
        WITH componentId, gds.util.asNode(nodeId) AS node
        WITH componentId,
             count(*) AS component_size,
             collect(CASE WHEN coalesce(node.fraud_ring_member,false)=true THEN node.account_id ELSE NULL END) AS maybe_fraud_accounts
        WITH componentId, component_size, [x IN maybe_fraud_accounts WHERE x IS NOT NULL] AS fraud_accounts
        WHERE size(fraud_accounts) > 0
        RETURN componentId, component_size, size(fraud_accounts) AS fraud_account_count, fraud_accounts[0..20] AS fraud_account_sample
        ORDER BY component_size DESC, fraud_account_count DESC
        LIMIT 20
        """, graph=GRAPH)
        run(session, "script_scc_filter_result_count", """
        CALL gds.scc.stream($graph)
        YIELD nodeId, componentId
        WITH componentId, collect(gds.util.asNode(nodeId).account_id) AS accounts
        WHERE size(accounts) >= 3 AND size(accounts) <= 6
        RETURN count(*) AS components_3_to_6, collect(size(accounts))[0..20] AS sample_sizes
        """, graph=GRAPH)
        run(session, "fraud_members_with_internal_cycle_edge_counts", """
        MATCH (a:Account)
        WHERE a.fraud_ring_ids IS NOT NULL AND a.fraud_ring_ids <> ''
        UNWIND split(toString(a.fraud_ring_ids), '|') AS ring_id
        WITH ring_id, collect(DISTINCT a.account_id) AS participants
        OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
        WHERE src.account_id IN participants AND dst.account_id IN participants
        RETURN ring_id, size(participants) AS participants, count(DISTINCT t) AS internal_txs,
               count(DISTINCT src.account_id) AS internal_sources, count(DISTINCT dst.account_id) AS internal_destinations
        ORDER BY ring_id
        LIMIT 30
        """)
        run(session, "drop_projection", "CALL gds.graph.drop($graph) YIELD graphName RETURN graphName", graph=GRAPH)
