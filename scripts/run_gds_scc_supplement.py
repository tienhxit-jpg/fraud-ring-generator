"""Run the GDS SCC supplement for an existing multi-database benchmark."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

DATABASES=("d1-v03","d2-v03","d3-v03","d4-v02","d5-v02")

def main():
 p=argparse.ArgumentParser(); p.add_argument('--run',required=True); p.add_argument('--timeout',type=int,default=3600); a=p.parse_args()
 root=Path.cwd(); run=Path(a.run); py=str(root/'.venv/Scripts/python.exe')
 state={'supplement':'gds_scc_after_plugin_available','started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'databases':{}}
 for db in DATABASES:
  out=run/'benchmark'/db/'gds_scc_rerun'; out.mkdir(parents=True,exist_ok=True)
  cmd=[py,'src/cycle_detection/v02/gds_cycle_detection_v02.py','--database',db,'--limit','0','--min-component-size','3','--max-component-size','12','--json-out',str(out/'summary.json'),'--jsonl-out',str(out/'candidates.jsonl')]
  t=time.perf_counter()
  try:
   with (out/'run.log').open('w',encoding='utf-8') as h:
    r=subprocess.run(cmd,cwd=root,stdout=h,stderr=subprocess.STDOUT,text=True,timeout=a.timeout)
   status='SUCCESS' if r.returncode==0 else 'FAILED'
   row={'status':status,'returncode':r.returncode,'elapsed_ms':round((time.perf_counter()-t)*1000,3),'command':cmd}
  except subprocess.TimeoutExpired:
   row={'status':'TIMEOUT','elapsed_ms':round((time.perf_counter()-t)*1000,3),'timeout_seconds':a.timeout,'command':cmd}
  state['databases'][db]=row
  (run/'GDS_SCC_SUPPLEMENT_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
  print(db,row['status'],flush=True)
 state['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
 (run/'GDS_SCC_SUPPLEMENT_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(state,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
