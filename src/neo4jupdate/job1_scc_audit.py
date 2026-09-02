#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 job1_scc_audit.py
 Cong cu do phan bo SCC va vi tri ring cho bai HTKH2026 (fraud ring detection)
-------------------------------------------------------------------------------
 Nguoi thuc hien : Hoang Xuan Tien
 Nguoi yeu cau   : Nguyen Thanh Tien
 Ngay            : 04/08/2026
-------------------------------------------------------------------------------
 SCRIPT NAY LAM GI
   - Ket noi Neo4j (hoac doc CSV), dung lai do thi account -> account
   - Do phan bo SCC cua tung tap D1..D5, o HAI trang thai:
        (a) day du   : chua ap bo loc amount, min_pair_transactions = 1
        (b) sau loc  : da ap dung bo loc amount + min_pair_transactions cua benchmark
   - Xac dinh moi ring trong ground truth nam o SCC nao (own / GIANT / split)
   - Do ti le canh noi bo ring bi bo loc cat mat
   - Tinh AUC cua bien 'amount' don le de kiem chung amount khong ro ri nhan
   - Thu thap tham so bo nho / phien ban Neo4j (Job 3)
   - Xuat toan bo ra 1 file Excel + 1 file JSON tho

 SCRIPT NAY KHONG LAM GI
   - Khong chay lai benchmark, khong sua bai bao, khong tinh lai Precision/Recall
   - Khong ghi bat cu thu gi vao Neo4j (chi doc)

-------------------------------------------------------------------------------
 CAI DAT
     pip install neo4j networkx pandas openpyxl

 CHAY
     python job1_scc_audit.py

 CHI SUA DUY NHAT KHOI "CONFIG" BEN DUOI. Khong sua phan con lai.
===============================================================================
"""

import os
import sys
import json
import math
import time
import traceback
from collections import defaultdict

# =============================================================================
#  CONFIG  --  TIEN CHI SUA TU DAY DEN DONG "HET CONFIG"
# =============================================================================

# --- 1. Ket noi Neo4j -------------------------------------------------------
# Dung ket noi truc tiep de tranh driver routing ve database mac dinh `neo4j`.
NEO4J_URI      = "bolt://127.0.0.1:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "NguyenCongTruA8!"

# Ten thuoc tinh dinh danh tai khoan tren node :Account
# (kiem tra bang: MATCH (a:Account) RETURN a LIMIT 1)
ACCOUNT_ID_PROP = "account_id"

# Ten thuoc tinh so tien tren node :Transaction
AMOUNT_PROP = "amount"

# Ten thuoc tinh nhan gian lan tren node :Transaction (de tinh AUC).
# Neu khong co thi de None -> script bo qua phan AUC.
FRAUD_FLAG_PROP = "is_fraud"

# --- 2. Khai bao 5 tap du lieu ---------------------------------------------
# Moi tap la 1 database rieng trong Neo4j, HOAC la 1 lan import rieng.
#
#   database        : ten database trong Neo4j. Neu tat ca nam chung 1 database
#                     thi de "neo4j" cho ca 5 tap va chay tung tap MOT LAN
#                     (sua ACTIVE_DATASETS ben duoi).
#   gt_file         : duong dan file ground truth
#   gt_format       : "jsonl" | "json" | "csv"
#   gt_field        : ten truong chua danh sach tai khoan cua ring
#                       - D1-D3 (JSON/JSONL): thuong la "participants" hoac "accounts"
#                       - D4-D5 (fraud_cases.csv): "involved_accounts"
#   min_pair        : min_pair_transactions dung khi chay benchmark
#   amount_min      : nguong duoi bo loc amount (None = khong loc)
#   amount_max      : nguong tren bo loc amount (None = khong loc)
#   scc_window      : (min, max) cua so kich thuoc SCC ung vien cua benchmark
#   expected_rings  : so ring theo bai bao, de script tu kiem tra doc dung file
#   expected_ring_edges : tong so canh noi bo ring theo bai bao (None neu khong biet)

DATASETS = {
    "D1": dict(
        database="d1-v03", gt_file=r"data/synthetic/v03/d1/ground_truth/fraud_rings.json", gt_format="jsonl",
        gt_field="participants", min_pair=1, amount_min=None, amount_max=None,
        scc_window=(3, 12), expected_rings=5, expected_ring_edges=24,
    ),
    "D2": dict(
        database="d2-v03", gt_file=r"data/synthetic/v03/d02/ground_truth/fraud_rings.json", gt_format="jsonl",
        gt_field="participants", min_pair=3, amount_min=None, amount_max=None,
        scc_window=(3, 12), expected_rings=45, expected_ring_edges=None,
    ),
    "D3": dict(
        database="d3-v03", gt_file=r"data/synthetic/v03/d3/ground_truth/fraud_rings.json", gt_format="jsonl",
        gt_field="participants", min_pair=3, amount_min=None, amount_max=None,
        scc_window=(3, 12), expected_rings=10, expected_ring_edges=None,
    ),
    "D4": dict(
        database="d4-v02", gt_file=r"data/synthetic/v03/d4/fraud/fraud_cases.csv", gt_format="csv",
        gt_field="involved_accounts", min_pair=1,
        amount_min=50,          # <-- DIEN DUNG NGUONG DA DUNG KHI CHAY BENCHMARK
        amount_max=100000,          # <-- DIEN DUNG NGUONG DA DUNG KHI CHAY BENCHMARK
        scc_window=(3, 12), expected_rings=10, expected_ring_edges=60,
    ),
    "D5": dict(
        database="d5-v02", gt_file=r"data/synthetic/v03/d5/fraud/fraud_cases.csv", gt_format="csv",
        gt_field="involved_accounts", min_pair=1,
        amount_min=None,          # <-- DIEN DUNG NGUONG DA DUNG KHI CHAY BENCHMARK
        amount_max=None,          # <-- DIEN DUNG NGUONG DA DUNG KHI CHAY BENCHMARK
        scc_window=(3, 12), expected_rings=10, expected_ring_edges=58,
    ),
}

# Tap nao chay lan nay. Neu 5 tap nam chung 1 database thi moi lan chi de 1 tap.
ACTIVE_DATASETS = ["D1", "D2", "D3", "D4", "D5"]

# --- 3. Tuy chon -----------------------------------------------------------
OUTPUT_XLSX = "JOB1_KETQUA_SCC.xlsx"
OUTPUT_JSON = "JOB1_KETQUA_SCC_raw.json"

# Tinh AUC cua amount (Nhom 8 trong yeu cau). Tat neu tap qua lon hoac cham.
DO_AMOUNT_AUC = True
AUC_MAX_ROWS  = 2_000_000

# =============================================================================
#  HET CONFIG  --  KHONG SUA TU DAY TRO XUONG
# =============================================================================

try:
    import networkx as nx
except ImportError:
    sys.exit("[LOI] Thieu networkx. Chay: pip install networkx")

try:
    import pandas as pd
except ImportError:
    sys.exit("[LOI] Thieu pandas. Chay: pip install pandas openpyxl")

try:
    from neo4j import GraphDatabase
except ImportError:
    sys.exit("[LOI] Thieu neo4j driver. Chay: pip install neo4j")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# -----------------------------------------------------------------------------
#  LAY CANH account -> account TU NEO4J
# -----------------------------------------------------------------------------

CYPHER_EDGES = """
MATCH (a:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(b:Account)
WHERE ($amin IS NULL OR t.`{amt}` >= $amin)
  AND ($amax IS NULL OR t.`{amt}` <= $amax)
WITH a.`{aid}` AS src, b.`{aid}` AS dst, count(*) AS n
WHERE n >= $minpair
RETURN src, dst, n
"""

CYPHER_AMOUNTS = """
MATCH (t:Transaction)
RETURN t.`{amt}` AS amount, t.`{flag}` AS is_fraud
"""


def fetch_edges(driver, database, amin, amax, minpair):
    """Tra ve list[(src, dst, n_transactions)] da khu trung cap co huong."""
    q = CYPHER_EDGES.format(amt=AMOUNT_PROP, aid=ACCOUNT_ID_PROP)
    edges = []
    with driver.session(database=database) as s:
        for r in s.run(q, amin=amin, amax=amax, minpair=minpair):
            if r["src"] is None or r["dst"] is None:
                continue
            edges.append((str(r["src"]), str(r["dst"]), int(r["n"])))
    return edges


def fetch_amounts(driver, database):
    """Tra ve list[(amount, is_fraud_bool)] de tinh AUC."""
    if not FRAUD_FLAG_PROP:
        return []
    q = CYPHER_AMOUNTS.format(amt=AMOUNT_PROP, flag=FRAUD_FLAG_PROP)
    rows = []
    with driver.session(database=database) as s:
        for r in s.run(q):
            a, f = r["amount"], r["is_fraud"]
            if a is None or f is None:
                continue
            rows.append((float(a), bool(f)))
            if len(rows) >= AUC_MAX_ROWS:
                break
    return rows


# -----------------------------------------------------------------------------
#  DOC GROUND TRUTH
# -----------------------------------------------------------------------------

def _split_accounts(value):
    """Chuyen mot o ground truth thanh list account_id (dang str)."""
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            return [str(v).strip() for v in json.loads(s)]
        except Exception:
            s = s[1:-1]
    for sep in (";", "|", ","):
        if sep in s:
            return [p.strip().strip("'\"") for p in s.split(sep) if p.strip()]
    return [s]


def load_ground_truth(path, fmt, field):
    """Tra ve list[frozenset[str]] - moi phan tu la participant-set cua 1 ring."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Khong tim thay file ground truth: {path}")
    rings = []

    def append_from_objects(data):
        if isinstance(data, dict):
            for key in ("rings", "fraud_rings", "ground_truth", "cases", "data"):
                if key in data:
                    data = data[key]
                    break
        for obj in data:
            rings.append(frozenset(_split_accounts(obj[field])))

    if fmt == "jsonl":
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    rings.append(frozenset(_split_accounts(obj[field])))
            else:
                append_from_objects(data)

    elif fmt == "json":
        with open(path, encoding="utf-8") as f:
            append_from_objects(json.load(f))

    elif fmt == "csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if field not in df.columns:
            raise KeyError(
                f"Cot '{field}' khong co trong {path}. Cac cot dang co: {list(df.columns)}"
            )
        for v in df[field]:
            s = frozenset(_split_accounts(v))
            if s:
                rings.append(s)
    else:
        raise ValueError(f"gt_format khong hop le: {fmt}")

    return [r for r in rings if r]


# -----------------------------------------------------------------------------
#  DO CAU TRUC SCC
# -----------------------------------------------------------------------------

def analyse_scc(edges, rings, scc_window):
    """Tinh toan bo chi so SCC cho mot do thi + vi tri cua tung ring."""
    G = nx.DiGraph()
    G.add_edges_from((s, d) for s, d, _ in edges)

    n = G.number_of_nodes()
    m = G.number_of_edges()
    c = (m / n) if n else 0.0

    comps = sorted(nx.strongly_connected_components(G), key=len, reverse=True)
    sizes = [len(x) for x in comps]
    node2scc = {v: i for i, comp in enumerate(comps) for v in comp}

    lo, hi = scc_window
    pred_giant = ((1 - math.exp(-c)) ** 2) * n if c > 0 else 0.0

    stats = dict(
        V=n, E=m, deg_avg=round(c, 4),
        total_scc=len(comps),
        S1=sizes[0] if sizes else 0,
        S2=sizes[1] if len(sizes) > 1 else 0,
        S3=sizes[2] if len(sizes) > 2 else 0,
        S1_ratio=round(sizes[0] / n, 6) if n else 0.0,
        pred_giant=round(pred_giant, 1),
        pred_vs_obs_pct=(round(100 * (sizes[0] - pred_giant) / pred_giant, 2)
                         if pred_giant > 0 else None),
        scc_ge3=sum(1 for s in sizes if s >= 3),
        scc_in_window=sum(1 for s in sizes if lo <= s <= hi),
    )

    # --- vi tri tung ring ---
    ring_rows = []
    tally = defaultdict(int)
    for i, ring in enumerate(rings):
        ids = set()
        missing = 0
        for a in ring:
            if a in node2scc:
                ids.add(node2scc[a])
            else:
                missing += 1

        if missing == len(ring):
            verdict, sid, ssize = "absent", None, 0
        elif len(ids) > 1:
            verdict, sid, ssize = "split", None, 0
        else:
            sid = next(iter(ids))
            ssize = sizes[sid]
            # Giant = SCC lon nhat VA thuc su lon hon ring rat nhieu
            if sid == 0 and ssize > len(ring):
                verdict = "GIANT"
            else:
                verdict = "own"

        if missing and verdict != "absent":
            verdict += "+missing"

        tally[verdict.split("+")[0]] += 1
        ring_rows.append(dict(
            ring_index=i, ring_size=len(ring),
            scc_id=sid, scc_size=ssize,
            is_largest_scc=(sid == 0) if sid is not None else False,
            accounts_missing=missing,
            verdict=verdict,
        ))

    summary = dict(
        rings_total=len(rings),
        rings_own=tally.get("own", 0),
        rings_giant=tally.get("GIANT", 0),
        rings_split=tally.get("split", 0),
        rings_absent=tally.get("absent", 0),
    )
    return stats, ring_rows, summary


def ring_edge_survival(edges, rings):
    """Dem canh noi bo ring con song sot trong tap canh nay."""
    members = set()
    for r in rings:
        members |= set(r)
    ring_of = {}
    for i, r in enumerate(rings):
        for a in r:
            ring_of[a] = i
    kept = 0
    for s, d, _ in edges:
        if s in members and d in members and ring_of.get(s) == ring_of.get(d):
            kept += 1
    return kept


def auc_amount(rows):
    """AUC cua bo phan loai mot bien 'amount' (Mann-Whitney, xu ly hang bang)."""
    if not rows:
        return None, None, None
    vals = sorted(rows, key=lambda x: x[0])
    n = len(vals)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[j + 1][0] == vals[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    n_pos = sum(1 for _, f in vals if f)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None, n_pos, n_neg
    r_pos = sum(ranks[k] for k in range(n) if vals[k][1])
    auc = (r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return round(auc, 4), n_pos, n_neg


def quantiles(xs):
    if not xs:
        return {}
    xs = sorted(xs)
    def q(p):
        k = (len(xs) - 1) * p
        f, cl = math.floor(k), math.ceil(k)
        return xs[int(k)] if f == cl else xs[f] * (cl - k) + xs[cl] * (k - f)
    return dict(min=round(xs[0], 2), q1=round(q(.25), 2), median=round(q(.5), 2),
                q3=round(q(.75), 2), max=round(xs[-1], 2))


# -----------------------------------------------------------------------------
#  JOB 3 - THAM SO MOI TRUONG
# -----------------------------------------------------------------------------

def collect_env(driver):
    rows = []
    try:
        with driver.session(database="system") as s:
            for r in s.run("CALL dbms.components() YIELD name, versions, edition "
                           "RETURN name, versions, edition"):
                rows.append(dict(name=f"{r['name']} ({r['edition']})",
                                 value=", ".join(r["versions"])))
    except Exception as e:
        rows.append(dict(name="dbms.components", value=f"LOI: {e}"))

    try:
        # dbms.listConfig() is a DBMS-level procedure; run it on system to avoid
        # falling back to the user's default database (neo4j).
        with driver.session(database="system") as s:
            q = ("CALL dbms.listConfig() YIELD name, value "
                 "WHERE name CONTAINS 'memory' OR name CONTAINS 'heap' "
                 "OR name CONTAINS 'pagecache' RETURN name, value ORDER BY name")
            for r in s.run(q):
                rows.append(dict(name=r["name"], value=str(r["value"])))
    except Exception as e:
        rows.append(dict(name="dbms.listConfig", value=f"LOI: {e}"))

    rows.append(dict(name="python", value=sys.version.split()[0]))
    rows.append(dict(name="networkx", value=nx.__version__))
    rows.append(dict(name="thoi_diem_chay", value=time.strftime("%Y-%m-%d %H:%M:%S")))
    return rows


# -----------------------------------------------------------------------------
#  MAIN
# -----------------------------------------------------------------------------

def main():
    log("Ket noi Neo4j ...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log("Ket noi OK.")

    t_scc, t_ring, t_sum, t_amt, t_warn = [], [], [], [], []
    raw = {}

    for name in ACTIVE_DATASETS:
        cfg = DATASETS[name]
        log(f"===== {name} =====")
        raw[name] = {}

        # ---- ground truth ----
        try:
            rings = load_ground_truth(cfg["gt_file"], cfg["gt_format"], cfg["gt_field"])
        except Exception as e:
            log(f"  [BO QUA] loi doc ground truth: {e}")
            t_warn.append(dict(dataset=name, muc="ground_truth", canh_bao=str(e)))
            continue

        log(f"  ground truth: {len(rings)} ring, "
            f"{sum(len(r) for r in rings)} tai khoan")
        if cfg["expected_rings"] and len(rings) != cfg["expected_rings"]:
            w = (f"So ring doc duoc = {len(rings)} nhung bai bao ghi "
                 f"{cfg['expected_rings']}. Kiem tra lai gt_file / gt_field.")
            log(f"  [CANH BAO] {w}")
            t_warn.append(dict(dataset=name, muc="so_ring", canh_bao=w))

        # ---- hai trang thai ----
        for state, amin, amax, minpair in (
            ("(a) day du", None, None, 1),
            ("(b) sau loc", cfg["amount_min"], cfg["amount_max"], cfg["min_pair"]),
        ):
            log(f"  {state}: dang lay canh ...")
            t0 = time.time()
            try:
                edges = fetch_edges(driver, cfg["database"], amin, amax, minpair)
            except Exception as e:
                log(f"    [LOI] {e}")
                t_warn.append(dict(dataset=name, muc=f"fetch_edges {state}",
                                   canh_bao=str(e)))
                continue
            log(f"    {len(edges):,} cap co huong ({time.time()-t0:.1f}s), dang tinh SCC ...")

            stats, ring_rows, summ = analyse_scc(edges, rings, cfg["scc_window"])
            kept = ring_edge_survival(edges, rings)

            t_scc.append(dict(dataset=name, trang_thai=state, **stats,
                              canh_ring_con_lai=kept,
                              canh_ring_theo_bai=cfg["expected_ring_edges"]))
            for r in ring_rows:
                t_ring.append(dict(dataset=name, trang_thai=state, **r))
            t_sum.append(dict(dataset=name, trang_thai=state, **summ,
                              canh_ring_con_lai=kept))

            raw[name][state] = dict(stats=stats, summary=summ, rings=ring_rows,
                                    ring_edges_kept=kept)

            log(f"    |V|={stats['V']:,} |E|={stats['E']:,} bacTB={stats['deg_avg']} "
                f"S1={stats['S1']:,} ({stats['S1_ratio']:.1%}) "
                f"duDoanLyThuyet={stats['pred_giant']:,.0f}")
            log(f"    ring: own={summ['rings_own']} GIANT={summ['rings_giant']} "
                f"split={summ['rings_split']} absent={summ['rings_absent']}")

            if state.startswith("(b)") and cfg["expected_ring_edges"]:
                if kept < cfg["expected_ring_edges"]:
                    w = (f"Bo loc cat mat {cfg['expected_ring_edges'] - kept}/"
                         f"{cfg['expected_ring_edges']} canh noi bo ring.")
                    log(f"    [CANH BAO] {w}")
                    t_warn.append(dict(dataset=name, muc="canh_ring_bi_cat",
                                       canh_bao=w))

        # ---- AUC amount ----
        if DO_AMOUNT_AUC and FRAUD_FLAG_PROP:
            try:
                rows = fetch_amounts(driver, cfg["database"])
                auc, npos, nneg = auc_amount(rows)
                qf = quantiles([a for a, f in rows if f])
                qb = quantiles([a for a, f in rows if not f])
                t_amt.append(dict(dataset=name, auc_amount=auc,
                                  n_fraud=npos, n_background=nneg,
                                  **{f"fraud_{k}": v for k, v in qf.items()},
                                  **{f"nen_{k}": v for k, v in qb.items()}))
                log(f"  AUC(amount) = {auc}")
                if auc is not None and (auc > 0.70 or auc < 0.30):
                    w = (f"AUC(amount) = {auc}, lech xa 0,50. Amount van co the "
                         f"suy ra nhan gian lan - mau thuan voi Muc 3.6 cua bai.")
                    log(f"  [CANH BAO] {w}")
                    t_warn.append(dict(dataset=name, muc="auc_amount", canh_bao=w))
            except Exception as e:
                log(f"  [BO QUA AUC] {e}")
                t_warn.append(dict(dataset=name, muc="auc_amount", canh_bao=str(e)))

    log("Thu thap tham so moi truong (Job 3) ...")
    t_env = collect_env(driver)
    driver.close()

    # ---- xuat Excel ----
    log(f"Ghi {OUTPUT_XLSX} ...")
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as xw:
        pd.DataFrame(t_scc).to_excel(xw, sheet_name="Bang1_CauTrucSCC", index=False)
        pd.DataFrame(t_ring).to_excel(xw, sheet_name="Bang2_ViTriRing", index=False)
        pd.DataFrame(t_sum).to_excel(xw, sheet_name="Bang3_TongHop", index=False)
        if t_amt:
            pd.DataFrame(t_amt).to_excel(xw, sheet_name="Bang6_AmountAUC", index=False)
        pd.DataFrame(t_env).to_excel(xw, sheet_name="Job3_MoiTruong", index=False)
        pd.DataFrame(t_warn if t_warn else [dict(dataset="", muc="", canh_bao="khong co")]
                     ).to_excel(xw, sheet_name="CanhBao", index=False)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    log(f"XONG. Nop 2 file: {OUTPUT_XLSX} va {OUTPUT_JSON}")
    if t_warn:
        log(f"Co {len(t_warn)} canh bao - xem sheet 'CanhBao'.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
