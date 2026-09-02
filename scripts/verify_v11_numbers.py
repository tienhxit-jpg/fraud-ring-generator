"""Verify v11 paper numbers against benchmark outputs."""
import json, sys

bg = json.load(open("results/background_scc_v12.json"))["databases"]
gds_topo = json.load(open("results/live_multidb_heap8g_20260814_104835/GDS_SCC_TOPOLOGY_AUDIT.json"))["databases"]
pattern_pp = json.load(open("results/live_multidb_heap8g_20260814_104835/PATTERN_EXTERNAL_POSTPROCESSING.json"))["databases"]

db_map = {"d1-v03": "D1", "d2-v03": "D2", "d3-v03": "D3", "d4-v02": "D4", "d5-v02": "D5"}

print("=" * 70)
print("VERIFICATION: Paper Bảng 2 (SCC trên đồ thị NỀN) vs benchmark")
print("=" * 70)
for db_key, name in db_map.items():
    bg_data = bg.get(db_key, {})
    gds = gds_topo.get(db_key, {})
    # Paper Bảng 2: SCC trên đồ thị NỀN
    V_bg = bg_data.get("V_bg", "?")
    largest_bg = bg_data.get("largest_scc_bg", "?")
    observed_cov = bg_data.get("observed_coverage", 0)
    rel_err = bg_data.get("relative_error")
    # Largest SCC trên full graph (cho Bảng 2 paper)
    largest_full = gds.get("largest_component_size", "?")
    bounded_3_12 = gds.get("bounded_component_count_3_12", "?")
    
    print(f"\n{name}:")
    print(f"  [Benchmark] Full graph largest SCC: {largest_full}")
    print(f"  [Benchmark] Bounded 3..12 SCC count: {bounded_3_12}")
    print(f"  [Paper Bảng 2] Background largest SCC: {largest_bg}, coverage={observed_cov:.4f}")
    if rel_err is not None:
        print(f"  [Paper Bảng 2] Relative error: {rel_err:+.6f}")

print()
print("=" * 70)
print("VERIFICATION: Paper Bảng 4a (Pattern output) vs benchmark")
print("=" * 70)
for db_key, name in [("d4-v02", "D4"), ("d5-v02", "D5")]:
    pp = pattern_pp.get(db_key, {})
    bm = pp.get("before_merge", {})
    am = pp.get("after_merge", {})
    completed = pp.get("completed_cycle_sizes", [])
    excluded = pp.get("excluded_incomplete_cycle_sizes", [])
    
    print(f"\n{name} Cypher Pattern:")
    print(f"  [Benchmark] Completed sizes: {completed}")
    print(f"  [Benchmark] Excluded incomplete: {excluded}")
    print(f"  [Benchmark] N_raw={pp.get('N_raw','?')}, N_unique={pp.get('N_unique','?')}, N_cluster={pp.get('N_cluster','?')}")
    print(f"  [Benchmark] FF_enum={pp.get('FF_enum','?')}, FF_merge={pp.get('FF_merge','?')}")
    print(f"  [Benchmark] Before-merge: TP={bm.get('true_positives',0)}, FP={bm.get('false_positives',0)}, FN={bm.get('false_negatives',0)}")
    print(f"  [Benchmark] After-merge:  TP={am.get('true_positives',0)}, FP={am.get('false_positives',0)}, FN={am.get('false_negatives',0)}")
    print(f"  [Paper Bảng 4a] Status: k=4 xong; k=5 timeout; k=6-7 OOM")

print()
print("=" * 70)
print("VERIFICATION: GDS SCC supplement results (Bảng 2 / Section 4.3)")
print("=" * 70)
for db_key, name in db_map.items():
    gds = gds_topo.get(db_key, {})
    bounded = gds.get("bounded_component_count_3_12", "?")
    largest = gds.get("largest_component_size", "?")
    hist = gds.get("component_size_histogram", {})
    print(f"\n{name}: largest_full_SCC={largest}, bounded_3_12={bounded}, hist={hist}")

print()
print("=" * 70)
print("VERIFICATION: Table 1 |E| values")
print("=" * 70)
for db_key, name in db_map.items():
    gds = gds_topo.get(db_key, {})
    pairs = gds.get("projection", {}).get("relationshipCount", "?")
    print(f"{name}: logical_pairs_in_full_projection = {pairs}")
