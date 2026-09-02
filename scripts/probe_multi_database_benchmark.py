"""Freeze live fingerprints and min_pair=3 preprocessing diagnostics for benchmark DBs."""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from neo4j import GraphDatabase

DATABASES = ("d1-v03", "d2-v03", "d3-v03", "d4-v02", "d5-v02")

QUERIES = {
    "counts": """
      MATCH (a:Account) WITH count(a) AS accounts
      OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
      WITH accounts, count(DISTINCT t) AS transactions,
           count(DISTINCT [src.account_id,dst.account_id]) AS logical_pairs
      OPTIONAL MATCH ()-[r:TRANSFER_AGG]->()
      RETURN accounts, transactions, logical_pairs, count(r) AS transfer_agg
    """,
    "properties": """
      CALL { MATCH (a:Account) UNWIND keys(a) AS key RETURN collect(DISTINCT key) AS account_keys }
      CALL { MATCH (t:Transaction) UNWIND keys(t) AS key RETURN collect(DISTINCT key) AS transaction_keys }
      RETURN account_keys, transaction_keys
    """,
    "fraud_transactions": """
      MATCH (t:Transaction)
      WHERE t.is_fraud IN [true, 'true', 1, '1']
      RETURN count(t) AS count
    """,
    "gt_accounts": """
      MATCH (a:Account)
      WHERE a.fraud_ring_member IN [true, 'true', 1, '1']
         OR a.fraud_ring_id IS NOT NULL OR a.fraud_ring_ids IS NOT NULL
      RETURN count(DISTINCT a) AS count
    """,
    "gt_ring_sizes": """
      MATCH (a:Account)
      WITH a, coalesce(a.fraud_ring_id, a.fraud_ring_ids) AS ring
      WHERE ring IS NOT NULL
      WITH toString(ring) AS ring_id, count(DISTINCT a) AS size
      RETURN collect({ring_id:ring_id,size:size}) AS rings
    """,
    "min_pair_3": """
      MATCH (s:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(d:Account)
      WHERE s <> d
      WITH s,d,count(t) AS n
      WHERE n >= 3
      RETURN count(*) AS qualifying_pairs,
             count(DISTINCT s) + count(DISTINCT d) AS endpoint_count_with_double_count,
             collect(DISTINCT s.account_id) + collect(DISTINCT d.account_id) AS endpoints
    """,
    "gds": """
      SHOW PROCEDURES YIELD name
      WHERE name IN ['gds.graph.project.cypher','gds.scc.stream']
      RETURN collect(name) AS procedures
    """,
}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--databases', default=','.join(DATABASES))
    a=p.parse_args()
    uri=os.environ.get('NEO4J_URI','neo4j://127.0.0.1:7687')
    user=os.environ.get('NEO4J_USER','neo4j')
    password=os.environ['NEO4J_PASSWORD']
    result={"uri":uri,"databases":{},"captured_at":time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    with GraphDatabase.driver(uri,auth=(user,password)) as driver:
      for db in a.databases.split(','):
        db=db.strip(); started=time.perf_counter(); row={"database":db,"queries":{}}
        with driver.session(database=db) as session:
          for name,q in QUERIES.items():
            q0=time.perf_counter()
            try:
              rec=session.run(q).single()
              value=dict(rec) if rec else {}
              if name=='min_pair_3':
                endpoints=value.pop('endpoints',[]) or []
                value['distinct_endpoint_count']=len(set(endpoints))
              row['queries'][name]={"status":"SUCCESS","value":value,"elapsed_ms":round((time.perf_counter()-q0)*1000,3)}
            except Exception as exc:
              row['queries'][name]={"status":"ERROR","error":str(exc),"elapsed_ms":round((time.perf_counter()-q0)*1000,3)}
        row['elapsed_ms']=round((time.perf_counter()-started)*1000,3)
        result['databases'][db]=row
        print(json.dumps({db:row},ensure_ascii=False),flush=True)
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

if __name__=='__main__': main()
