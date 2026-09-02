"""Audit complete GDS SCC size distributions for the five live databases."""
from __future__ import annotations
import argparse,json,os,sys,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.cycle_detection.v02.gds_cycle_detection_v02 import GDSCycleDetectorV02

DBS=("d1-v03","d2-v03","d3-v03","d4-v02","d5-v02")
QUERY="""
CALL gds.scc.stream($graph_name)
YIELD componentId
WITH componentId, count(*) AS size
RETURN size ORDER BY size DESC
"""
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out={'captured_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'gds_version':'2026.06.0','databases':{}}
 for db in DBS:
  det=GDSCycleDetectorV02(uri=os.environ.get('NEO4J_URI','neo4j://127.0.0.1:7687'),user=os.environ.get('NEO4J_USER','neo4j'),password=os.environ['NEO4J_PASSWORD'],database=db,logger=None)
  name=f'cycle_gds_scc_audit_{db.replace("-","_")}'
  t=time.perf_counter()
  try:
   proj=det.project_graph(name)
   with det._session() as s: sizes=[int(r['size']) for r in s.run(QUERY,graph_name=name)]
   hist=Counter(sizes)
   out['databases'][db]={'projection':proj,'component_count':len(sizes),'largest_component_size':sizes[0] if sizes else 0,'bounded_component_count_3_12':sum(n for z,n in hist.items() if 3<=z<=12),'singleton_count':hist.get(1,0),'component_size_histogram':{str(z):hist[z] for z in sorted(hist)},'elapsed_ms':round((time.perf_counter()-t)*1000,3)}
  finally:
   det.drop_projection(name);det.close()
 Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
