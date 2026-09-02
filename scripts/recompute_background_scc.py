"""Recompute background-only directed graph metrics from live Neo4j databases."""
from __future__ import annotations
import json, os, time, math
from pathlib import Path
import networkx as nx
from neo4j import GraphDatabase

DBS=("d1-v03","d2-v03","d3-v03","d4-v02","d5-v02")
OUT=Path("results/background_scc_v12.json")

def solve_s(c:float)->float:
    if c <= 1: return 0.0
    s=1-1e-8
    for _ in range(10000):
        n=1-math.exp(-c*s)
        if abs(n-s)<1e-14: return n
        s=n
    return s

def main():
    uri=os.getenv("NEO4J_URI","neo4j://127.0.0.1:7687")
    auth=(os.getenv("NEO4J_USER","neo4j"),os.environ["NEO4J_PASSWORD"])
    out={"definition":"Background graph induced by active non-ground-truth Account endpoints; distinct directed logical pairs.","databases":{}}
    with GraphDatabase.driver(uri,auth=auth) as driver:
      for db in DBS:
        started=time.perf_counter(); g=nx.DiGraph()
        q_nodes="""
        MATCH (a:Account)
        WHERE NOT (a.fraud_ring_member IN [true,'true',1,'1'] OR a.fraud_ring_id IS NOT NULL OR a.fraud_ring_ids IS NOT NULL)
        RETURN a.account_id AS account_id
        """
        q="""
        MATCH (s:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(d:Account)
        WHERE s <> d
          AND NOT (s.fraud_ring_member IN [true,'true',1,'1'] OR s.fraud_ring_id IS NOT NULL OR s.fraud_ring_ids IS NOT NULL)
          AND NOT (d.fraud_ring_member IN [true,'true',1,'1'] OR d.fraud_ring_id IS NOT NULL OR d.fraud_ring_ids IS NOT NULL)
        RETURN DISTINCT s.account_id AS source, d.account_id AS target
        """
        with driver.session(database=db) as session:
          for r in session.run(q_nodes): g.add_node(str(r['account_id']))
          for r in session.run(q): g.add_edge(str(r['source']),str(r['target']))
        sizes=sorted((len(x) for x in nx.strongly_connected_components(g)),reverse=True)
        v=g.number_of_nodes(); e=g.number_of_edges(); c=e/v if v else 0; s=solve_s(c)
        out['databases'][db]={"V_bg":v,"E_bg":e,"c_bg":c,"total_scc_bg":len(sizes),"largest_scc_bg":sizes[0] if sizes else 0,"second_scc_bg":sizes[1] if len(sizes)>1 else 0,"observed_coverage":(sizes[0]/v if v else 0),"null_S":s,"predicted_coverage_S2":s*s,"predicted_largest_S2V":s*s*v,"relative_error":((sizes[0]-s*s*v)/(s*s*v) if s*s*v>=1 else None),"elapsed_s":time.perf_counter()-started}
        print(db,json.dumps(out['databases'][db]),flush=True)
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
if __name__=='__main__': main()
