import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cycle_detection.v02.cypher_cycle_detection_v02 import CypherCycleDetectorV02, write_jsonl
from src.evaluation.fraud_ring_metrics import evaluate_fraud_rings, load_rings

root = Path("data/cycledetection")
run_id = (root / ".current_d5_run").read_text().strip()
run_dir = root / run_id
truth = load_rings(run_dir / "ground_truth.json")

def load_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def load_jsonl(path):
    p=Path(path)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
def save(path,obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def consolidate(directory, raw_files):
    raw=[]
    for f in raw_files: raw.extend(load_jsonl(directory/f))
    unique={tuple(sorted(set(x.get("participants") or []))):x for x in raw if x.get("participants")}
    merged=CypherCycleDetectorV02.merge_overlapping_cycle_records(unique.values())
    write_jsonl(directory/"combined_completed_raw.jsonl",raw); write_jsonl(directory/"combined_completed_unique.jsonl",unique.values()); write_jsonl(directory/"combined_completed_merged.jsonl",merged)
    ff={"raw_cycles":len(raw),"unique_sets":len(unique),"merged_clusters":len(merged),"ff_enumeration":len(raw)/len(unique) if unique else None,"ff_fragmentation":len(unique)/len(merged) if merged else None,"ff_total":len(raw)/len(merged) if merged else None}
    ev=evaluate_fraud_rings(merged,truth,min_jaccard=1.0); save(directory/"ff_completed.json",ff); save(directory/"evaluation_completed.json",ev); return ff,ev

opt=run_dir/"cypher_optimized"; opt4=load_json(opt/"summary_4.json"); optff, optev=consolidate(opt,["raw_4.jsonl"])
prep_txt=(opt/"run_4_clean.log").read_text(encoding="utf-8",errors="replace"); m=re.search(r"aggregate preparation finished \(([0-9.]+)s, batches=(\d+), pairs=(\d+)\)",prep_txt)
preparation={"status":"SUCCESS","elapsed_ms":float(m.group(1))*1000,"batches":int(m.group(2)),"aggregate_pairs":int(m.group(3)),"batch_size":1000,"amount_filter":None,"label_blind":True} if m else {"status":"UNKNOWN"}
opt_status={str(k):("SUCCESS" if k==4 else "OOM") for k in (4,5,6,7)}
pattern=run_dir/"cypher_pattern_clean"; patsum=load_json(pattern/"summary.json"); patstatus={str(x["cycle_size"]):("OOM" if "MemoryPoolOutOfMemory" in x.get("error","") else "TIMEOUT_OR_RESOURCE_LIMIT") for x in patsum["results"]}; patff,patev=consolidate(pattern,[])
hyb=load_json(run_dir/"hybrid/summary.json"); hybev=evaluate_fraud_rings(load_jsonl(run_dir/"hybrid/merged_candidates.jsonl"),truth); save(run_dir/"hybrid/evaluation.json",hybev)
gds=load_json(run_dir/"gds/summary.json"); gdsev=load_json(run_dir/"gds/evaluation.json") if (run_dir/"gds/evaluation.json").exists() else evaluate_fraud_rings([],truth); save(run_dir/"gds/evaluation.json",gdsev)
fp=load_json(run_dir/"fingerprint.json")["fingerprint"][0]; topo=load_json(run_dir/"post_detection_topology.json"); sizes=Counter(str(x["participant_count"]) for x in truth)
summary={"benchmark_id":run_id,"mode":"structural_label_blind","graph_fingerprint":{"accounts":fp["accounts"],"transactions":fp["transactions"],"logical_edges":fp["logical_edges"],"logical_pairs":fp["logical_pairs"],"ground_truth_rings":len(truth),"fraud_transactions":topo["boundary"]["fraud_transactions"],"ring_size_distribution":dict(sorted(sizes.items())),"largest_scc":topo["largest_scc_sizes"][0],"eligible_scc_3_12":topo["eligible_scc_3_12"],"exact_amount_9999_transactions":topo["amount_profile"]["exact_9999"]},"parameters":{"cycle_sizes":[4,5,6,7],"min_pair_transactions":1,"min_pair_amount":0.0,"min_total_amount":0.0,"limit":0,"scc_window":"3..12","query_timeout_seconds":300.0,"label_blind":True},"methods":{"gds_scc":{"status":"SUCCESS_EMPTY","summary":gds,"evaluation":gdsev},"hybrid_networkx":{"status":"SUCCESS_EMPTY","summary":hyb,"evaluation":hybev},"cypher_optimized":{"status_by_cycle_size":opt_status,"preparation":preparation,"completed_summaries":{"4":opt4},"ff_completed":optff,"evaluation_completed":optev},"cypher_pattern":{"status_by_cycle_size":patstatus,"summary":patsum,"ff_completed":patff,"evaluation_completed":patev}},"topology_audit":topo,"integrity_notes":["All detector amount thresholds were zero.","Ground truth was read only after detector outputs were frozen.","D5 live snapshot fingerprint is 100000 accounts, 900058 transactions, and 830028 logical pairs.","Cypher Pattern was rerun after aggregate preparation completed; k=4..7 all hit transaction-memory OOM."]}
save(run_dir/"BENCHMARK_SUMMARY.json",summary)
print(json.dumps({"run_id":run_id,"fingerprint":summary["graph_fingerprint"],"gds":{"status":"SUCCESS_EMPTY","elapsed_ms":gds["elapsed_ms"],"projection_ms":gds["projection"]["projectMillis"]},"hybrid":{"status":"SUCCESS_EMPTY","elapsed_ms":hyb["elapsed_ms"]},"optimized":{"status":opt_status,"ff":optff,"evaluation":optev},"pattern":{"status":patstatus}},ensure_ascii=False,indent=2))
