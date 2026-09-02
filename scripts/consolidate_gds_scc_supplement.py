"""Freeze transaction-derived ground truth, evaluate GDS SCC, and augment a benchmark."""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from pathlib import Path
from neo4j import GraphDatabase
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings, load_rings

DBS=("d1-v03","d2-v03","d3-v03","d4-v02","d5-v02")
GT_QUERY="""
MATCH (s:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(d:Account)
WHERE t.is_fraud IN [true,'true',1,'1'] AND t.fraud_ring_id IS NOT NULL
WITH toString(t.fraud_ring_id) AS ring_id,
     collect(DISTINCT s.account_id) + collect(DISTINCT d.account_id) AS ids
UNWIND ids AS id
WITH ring_id, collect(DISTINCT id) AS participants
RETURN ring_id, participants ORDER BY ring_id
"""

def sha(path:Path)->str:
 h=hashlib.sha256();
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(); p.add_argument('--run',required=True); a=p.parse_args(); run=Path(a.run)
 base=json.loads((run/'BENCHMARK_SUMMARY.json').read_text(encoding='utf-8'))
 supplement=json.loads((run/'GDS_SCC_SUPPLEMENT_STATE.json').read_text(encoding='utf-8'))
 topology_path=run/'GDS_SCC_TOPOLOGY_AUDIT.json'
 topology=json.loads(topology_path.read_text(encoding='utf-8')) if topology_path.exists() else {'databases':{}}
 out={'run_dir':str(run),'source_benchmark_summary':'BENCHMARK_SUMMARY.json','gds_scc_supplement':{},'databases':base['databases'],'validation':base['validation'],'notes':list(base.get('notes',[]))}
 driver=GraphDatabase.driver(os.environ.get('NEO4J_URI','neo4j://127.0.0.1:7687'),auth=(os.environ.get('NEO4J_USER','neo4j'),os.environ['NEO4J_PASSWORD']))
 try:
  for db in DBS:
   with driver.session(database=db) as s: rows=s.run(GT_QUERY).data()
   rings=[{'ring_id':r['ring_id'],'participants':sorted(r['participants']),'participant_count':len(r['participants'])} for r in rows]
   gt={'database':db,'source':'live fraud Transaction.fraud_ring_id; evaluation only','total_rings':len(rings),'rings':rings}
   d=run/'benchmark'/db/'gds_scc_rerun'; gt_path=d/'ground_truth_frozen.json'; gt_path.write_text(json.dumps(gt,ensure_ascii=False,indent=2),encoding='utf-8')
   pred_path=d/'candidates.jsonl'; pred=load_rings(pred_path); metrics=evaluate_fraud_rings(pred,rings,min_jaccard=1.0)
   ev_path=d/'evaluation_exact.json'; ev_path.write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
   summary=json.loads((d/'summary.json').read_text(encoding='utf-8'))
   entry={'status':'SUCCESS_EMPTY' if summary['result_count']==0 else 'SUCCESS','gds_version':summary['gds']['version'],'node_count':summary['projection']['nodeCount'],'relationship_count':summary['projection']['relationshipCount'],'project_millis':summary['projection']['projectMillis'],'result_count':summary['result_count'],'elapsed_ms':summary['elapsed_ms'],'evaluation_exact':metrics,'artifacts':{'summary':str(d/'summary.json'),'candidates':str(pred_path),'ground_truth':str(gt_path),'evaluation':str(ev_path)}}
   entry['scc_topology']=topology['databases'].get(db)
   out['gds_scc_supplement'][db]=entry
   out['databases'][db]['methods']['gds_initial']=out['databases'][db]['methods'].pop('gds')
   out['databases'][db]['methods']['gds_scc']=entry
  out['notes'].append('GDS initial UNAVAILABLE status is preserved as gds_initial; gds_scc is the successful rerun after GDS 2026.06.0 became available.')
 finally: driver.close()
 dest=run/'BENCHMARK_SUMMARY_WITH_GDS.json'; dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 files=[dest,run/'GDS_SCC_SUPPLEMENT_STATE.json']
 if topology_path.exists(): files.append(topology_path)
 for db in DBS:
  d=run/'benchmark'/db/'gds_scc_rerun'; files += [d/'summary.json',d/'candidates.jsonl',d/'ground_truth_frozen.json',d/'evaluation_exact.json']
 (run/'SHA256SUMS_GDS_SUPPLEMENT.txt').write_text('\n'.join(f'{sha(x)}  {x.as_posix()}' for x in files)+'\n',encoding='utf-8')
 print(json.dumps(out['gds_scc_supplement'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
