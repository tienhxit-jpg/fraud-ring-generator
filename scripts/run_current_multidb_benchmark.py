"""Sequential benchmark of the current four pipeline implementations on all live DBs."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

DBS={
 "d1-v03":"3,5,8",
 "d2-v03":"3,5,8",
 "d3-v03":"3,5,8",
 "d4-v02":"4,5,6,7",
 "d5-v02":"4,5,6,7",
}

def run(cmd:list[str], cwd:Path, log:Path, timeout:float)->dict:
    started=time.perf_counter(); log.parent.mkdir(parents=True,exist_ok=True)
    try:
      with log.open('w',encoding='utf-8') as h:
        p=subprocess.run(cmd,cwd=cwd,stdout=h,stderr=subprocess.STDOUT,text=True,timeout=timeout)
      return {"status":"SUCCESS" if p.returncode==0 else "FAILED","returncode":p.returncode,
              "elapsed_ms":round((time.perf_counter()-started)*1000,3),"log":str(log)}
    except subprocess.TimeoutExpired:
      return {"status":"TIMEOUT","elapsed_ms":round((time.perf_counter()-started)*1000,3),"log":str(log),"timeout_seconds":timeout}
    except Exception as exc:
      return {"status":"ERROR","elapsed_ms":round((time.perf_counter()-started)*1000,3),"log":str(log),"error":str(exc)}

def main():
 p=argparse.ArgumentParser(); p.add_argument('--out',required=True); p.add_argument('--databases',default=','.join(DBS)); a=p.parse_args()
 root=Path.cwd(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 py=str(root/'.venv/Scripts/python.exe')
 result={"benchmark":"current_source_default_scope","started_at":time.strftime('%Y-%m-%dT%H:%M:%S%z'),"databases":{}}
 for db in a.databases.split(','):
  db=db.strip(); sizes=DBS[db]; d=out/db; d.mkdir(parents=True,exist_ok=True)
  row={"database":db,"cycle_sizes":[int(x) for x in sizes.split(',')],"methods":{}}
  print(f'[{time.strftime("%H:%M:%S")}] {db}: GDS',flush=True)
  row['methods']['gds_scc']=run([py,'src/cycle_detection/v02/gds_cycle_detection_v02.py','--database',db,'--limit','0','--min-component-size','3','--max-component-size','12','--json-out',str(d/'gds/summary.json'),'--jsonl-out',str(d/'gds/candidates.jsonl')],root,d/'gds/run.log',3600)
  print(f'[{time.strftime("%H:%M:%S")}] {db}: Hybrid',flush=True)
  row['methods']['hybrid_networkx']=run([py,'src/cycle_detection/v02/hybrid_networkx_cycle_detection_v02.py','--database',db,'--cycle-sizes',sizes,'--limit','0','--min-component-size','3','--max-component-size','12','--json-out',str(d/'hybrid/summary.json'),'--raw-jsonl-out',str(d/'hybrid/raw.jsonl'),'--merged-jsonl-out',str(d/'hybrid/merged.jsonl')],root,d/'hybrid/run.log',7200)
  print(f'[{time.strftime("%H:%M:%S")}] {db}: Cypher Optimized default min_pair=3',flush=True)
  row['methods']['cypher_optimized']=run([py,'src/cycle_detection/v02/cypher_cycle_detection_v02.py','--database',db,'--cycle-sizes',sizes,'--limit','0','--graph-mode','aggregate','--prepare-aggregates','--aggregate-batch-size','1000','--min-pair-transactions','3','--query-timeout','180','--raw-jsonl-out',str(d/'optimized/raw.jsonl'),'--merged-jsonl-out',str(d/'optimized/merged.jsonl'),'--json-out',str(d/'optimized/summary.json')],root,d/'optimized/run.log',10800)
  print(f'[{time.strftime("%H:%M:%S")}] {db}: Cypher Pattern no business predicates',flush=True)
  row['methods']['cypher_pattern']=run([py,'src/cycle_detection/v02/cypher_cycle_detection_unoptimized.py','--database',db,'--cycle-sizes',sizes,'--query-timeout','120','--cycle8-timeout','120','--heartbeat-seconds','30','--output-dir',str(d/'pattern')],root,d/'pattern/run.log',1800)
  result['databases'][db]=row
  (out/'BENCHMARK_RUN_STATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 result['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
 (out/'BENCHMARK_RUN_STATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__': main()
