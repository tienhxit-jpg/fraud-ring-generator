"""External evaluation normalization for completed Cypher Pattern outputs only."""
from __future__ import annotations
import argparse,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings

class UF:
 def __init__(self,n): self.p=list(range(n));self.r=[0]*n
 def find(self,x):
  while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a==b:return
  if self.r[a]<self.r[b]:a,b=b,a
  self.p[b]=a
  if self.r[a]==self.r[b]:self.r[a]+=1

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run=Path(a.run);out={'scope':'external evaluation only; detector output is unchanged','databases':{}}
 for db in ('d4-v02','d5-v02'):
  d=run/'benchmark'/db/'pattern'; summary=json.loads((d/'summary.json').read_text())
  completed=[r for r in summary['results'] if r['status']=='completed']
  records=[]
  for row in completed:
   with Path(row['output']).open(encoding='utf-8') as f: records.extend(json.loads(line) for line in f if line.strip())
  by_key={tuple(sorted(set(r['participants']))):r for r in records}; keys=list(by_key); uf=UF(len(keys)); owner={}
  for i,k in enumerate(keys):
   for v in k:
    if v in owner:uf.union(i,owner[v])
    else:owner[v]=i
  groups=defaultdict(set)
  for i,k in enumerate(keys):groups[uf.find(i)].update(k)
  unique=[{'ring_id':f'PATTERN_UNIQUE_{i:06d}','participants':list(k)} for i,k in enumerate(keys)]
  merged=[{'ring_id':f'PATTERN_CLUSTER_{i:06d}','participants':sorted(v)} for i,v in enumerate(groups.values())]
  gt=json.loads((run/'benchmark'/db/'gds_scc_rerun'/'ground_truth_frozen.json').read_text())['rings']
  before=evaluate_fraud_rings(unique,gt,min_jaccard=1.0);after=evaluate_fraud_rings(merged,gt,min_jaccard=1.0)
  out['databases'][db]={'completed_cycle_sizes':[r['cycle_size'] for r in completed],'excluded_incomplete_cycle_sizes':[r['cycle_size'] for r in summary['results'] if r['status']!='completed'],'N_raw':len(records),'N_unique':len(unique),'N_cluster':len(merged),'FF_enum':len(records)/len(unique) if unique else None,'FF_merge':len(unique)/len(merged) if merged else None,'before_merge':before,'after_merge':after}
 dest=run/'PATTERN_EXTERNAL_POSTPROCESSING.json';dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
