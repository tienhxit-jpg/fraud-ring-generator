"""Consolidate current multi-database benchmark artifacts and validate JSON/JSONL."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def load(p:Path):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return None

def lines(p:Path):
 if not p.exists(): return None
 n=0
 with p.open(encoding='utf-8') as h:
  for n,line in enumerate(h,1): json.loads(line)
 return n

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',required=True); a=ap.parse_args(); root=Path(a.run)
 state=load(root/'benchmark/BENCHMARK_RUN_STATE.json')
 fp_path=root/'fingerprint.json'
 if not fp_path.exists(): fp_path=root/'fingerprint_before.json'
 fp=load(fp_path)
 out={"run_dir":str(root),"databases":{},"validation":{},"notes":["GDS FAILED means UNAVAILABLE because gds.graph.project.cypher is absent.","Cypher Optimized uses current CLI default min_pair_transactions=3.","Cypher Pattern, Hybrid, and GDS use no pair-frequency business filter."]}
 for db,row in state['databases'].items():
  b=root/'benchmark'/db; q=fp['databases'][db]['queries']; d={"fingerprint":q['counts']['value'],"min_pair_3":q['min_pair_3']['value'],"methods":{}}
  hs=load(b/'hybrid/summary.json'); os=load(b/'optimized/summary.json'); ps=load(b/'pattern/summary.json')
  d['methods']['gds']={"status":"UNAVAILABLE" if row['methods']['gds_scc']['status']=='FAILED' else row['methods']['gds_scc']['status'],"elapsed_ms":row['methods']['gds_scc']['elapsed_ms']}
  d['methods']['hybrid']={"status":row['methods']['hybrid_networkx']['status'],"raw":hs.get('raw_result_count') if hs else None,"unique":hs.get('unique_participant_sets') if hs else None,"merged":hs.get('merged_result_count') if hs else None,"by_size":hs.get('results_by_cycle_size') if hs else None,"elapsed_ms":hs.get('elapsed_ms') if hs else row['methods']['hybrid_networkx']['elapsed_ms']}
  d['methods']['optimized']={"status":row['methods']['cypher_optimized']['status'],"raw":os.get('raw_result_count') if os else None,"merged":os.get('merged_result_count') if os else None,"by_size":os.get('results_by_cycle_size') if os else None,"elapsed_ms":os.get('elapsed_ms') if os else row['methods']['cypher_optimized']['elapsed_ms']}
  pres=[]
  if ps:
   for x in ps['results']:
    pres.append({k:x.get(k) for k in ('cycle_size','status','rows','elapsed_ms','error') if x.get(k) is not None})
  d['methods']['pattern']={"status":row['methods']['cypher_pattern']['status'],"sizes":pres,"elapsed_ms":ps.get('elapsed_ms') if ps else row['methods']['cypher_pattern']['elapsed_ms']}
  for rel in ('hybrid/raw.jsonl','hybrid/merged.jsonl','optimized/raw.jsonl','optimized/merged.jsonl'):
   p=b/rel
   try: out['validation'][f'{db}/{rel}']={"jsonl_lines":lines(p),"status":"VALID"}
   except Exception as e: out['validation'][f'{db}/{rel}']={"status":"INVALID","error":str(e)}
  out['databases'][db]=d
 dest=root/'BENCHMARK_SUMMARY.json'; dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 # checksums after summary is frozen
 files=[fp_path,root/'benchmark/BENCHMARK_RUN_STATE.json',dest,root/'HEAP_PROVENANCE.json']
 manifest=[]
 for p in files:
  manifest.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.as_posix()}")
 (root/'SHA256SUMS.txt').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
