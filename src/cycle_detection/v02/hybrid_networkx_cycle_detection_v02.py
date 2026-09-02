"""Hybrid Neo4j + NetworkX cycle detector v02.

This version pulls one logical directed edge per account pair, enumerates only
requested cycle sizes inside bounded SCCs, caches group metrics, applies the
result limit after overlap merging, and exports all candidates without answer
key properties or score-based output filtering.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import networkx as nx
from neo4j import GraphDatabase

try:
    from src.neo4j_config import NEO4J_CONFIG
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from src.neo4j_config import NEO4J_CONFIG


DEFAULT_URI = NEO4J_CONFIG.uri
DEFAULT_USER = NEO4J_CONFIG.user
DEFAULT_PASSWORD = NEO4J_CONFIG.password
DEFAULT_DATABASE = NEO4J_CONFIG.database


def progress_log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


class HybridNetworkXCycleDetectorV02:
    """Load an aggregated account graph and enumerate bounded NetworkX cycles."""

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        database: Optional[str] = None,
        driver: Any = "auto",
        logger=progress_log,
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password)) if driver == "auto" else driver
        self.database = database
        self.logger = logger
        self.metrics_cache: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.last_raw_results: List[Dict[str, Any]] = []
        self.last_results: List[Dict[str, Any]] = []

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)

    def _session(self):
        return self.driver.session(database=self.database) if self.database else self.driver.session()

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    @staticmethod
    def node_query() -> str:
        return """
        MATCH (a:Account)
        RETURN a.account_id AS account_id,
               coalesce(a.kyc_risk_score, 0.5) AS risk_score,
               coalesce(a.monthly_transaction_count, 0) AS monthly_transaction_count
        """

    @staticmethod
    def edge_query() -> str:
        return """
        MATCH (a:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(b:Account)
        WHERE a <> b
        WITH a, b,
             count(t) AS transaction_count,
             sum(coalesce(t.amount_usd, t.amount, 0.0)) AS total_amount,
             min(t.timestamp) AS first_timestamp,
             max(t.timestamp) AS last_timestamp
        RETURN a.account_id AS source,
               b.account_id AS destination,
               transaction_count,
               total_amount,
               first_timestamp,
               last_timestamp
        """

    def load_graph_from_neo4j(self) -> nx.DiGraph:
        if self.driver is None:
            raise RuntimeError("Neo4j driver is required to load graph data")
        graph = nx.DiGraph()
        with self._session() as session:
            for record in session.run(self.node_query()):
                graph.add_node(
                    record["account_id"],
                    risk_score=float(record["risk_score"] or 0.5),
                    monthly_transaction_count=float(record["monthly_transaction_count"] or 0),
                )
            for record in session.run(self.edge_query()):
                graph.add_edge(
                    record["source"],
                    record["destination"],
                    amount=float(record["total_amount"] or 0.0),
                    weight=float(record["total_amount"] or 0.0),
                    transaction_count=int(record["transaction_count"] or 0),
                    first_timestamp=record.get("first_timestamp"),
                    last_timestamp=record.get("last_timestamp"),
                )
        return graph

    @staticmethod
    def canonical_cycle(cycle: Sequence[str]) -> Tuple[str, ...]:
        values = tuple(str(item) for item in cycle)
        rotations = [values[index:] + values[:index] for index in range(len(values))]
        return min(rotations)

    def detect_cycles(
        self,
        graph: nx.DiGraph,
        cycle_sizes: Sequence[int] = (3, 5, 8),
        limit: int = 0,
        min_component_size: int = 3,
        max_component_size: int = 12,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        requested_sizes = {int(size) for size in cycle_sizes}
        if not requested_sizes or min(requested_sizes) < 2:
            raise ValueError("cycle_sizes must contain integers >= 2")
        self.metrics_cache.clear()
        raw_by_key: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        raw_by_size: Counter[str] = Counter()
        components = sorted(nx.strongly_connected_components(graph), key=len, reverse=True)
        eligible = [
            component
            for component in components
            if min_component_size <= len(component) <= max_component_size
        ]
        self._log(
            f"NetworkX: nodes={graph.number_of_nodes()}, edges={graph.number_of_edges()}, "
            f"eligible_scc={len(eligible)}"
        )
        for component_index, component in enumerate(eligible, 1):
            subgraph = graph.subgraph(component)
            component_cycles = 0
            for cycle in nx.simple_cycles(subgraph, length_bound=max(requested_sizes)):
                size = len(cycle)
                if size not in requested_sizes or size < min_component_size:
                    continue
                canonical = self.canonical_cycle(cycle)
                if canonical in raw_by_key:
                    continue
                description = self.describe_cycle(graph, canonical)
                if description["transactions"] < min_internal_transactions:
                    continue
                if description["total_amount"] < min_total_amount:
                    continue
                description["cycle_size"] = size
                raw_by_key[canonical] = description
                raw_by_size[str(size)] += 1
                component_cycles += 1
            self._log(
                f"SCC {component_index}/{len(eligible)} size={len(component)} "
                f"raw_cycles={component_cycles}"
            )
        raw = list(raw_by_key.values())
        merged = self.merge_overlapping_cycle_records(graph, raw)
        merged.sort(key=lambda item: (item["score"], item["total_amount"], item["participant_count"]), reverse=True)
        self.last_raw_results = raw
        self.last_results = merged[:limit] if limit > 0 else merged
        self.last_raw_by_size = dict(raw_by_size)
        self.last_unique_count = len(raw)
        return self.last_results

    def describe_cycle(self, graph: nx.DiGraph, cycle: Sequence[str]) -> Dict[str, Any]:
        participants = tuple(sorted(str(item) for item in cycle))
        metrics = self.group_metrics(graph, participants)
        return {
            "participants": list(participants),
            "participant_count": len(participants),
            "transactions": metrics["transactions"],
            "total_amount": round(metrics["total_amount"], 3),
            "density": round(metrics["density"], 4),
            "avg_kyc_risk_score": round(metrics["avg_risk"], 4),
            "avg_monthly_transaction_count": round(metrics["avg_activity"], 3),
            "score": round(self.score_metrics(metrics, len(participants)), 4),
            "cycles": 1,
            "method": "hybrid_networkx_simple_cycles_v02",
        }

    def group_metrics(self, graph: nx.DiGraph, participants: Sequence[str]) -> Dict[str, Any]:
        key = tuple(sorted(str(item) for item in participants))
        cached = self.metrics_cache.get(key)
        if cached is not None:
            return cached
        participant_set = set(key)
        total_amount = 0.0
        transactions = 0
        edges = 0
        for source, destination, data in graph.subgraph(participant_set).edges(data=True):
            del source, destination
            total_amount += self._safe_float(data.get("amount", 0.0), 0.0)
            transactions += int(data.get("transaction_count", 0) or 0)
            edges += 1
        denominator = len(key) * (len(key) - 1)
        risk = [self._safe_float(graph.nodes[node].get("risk_score", 0.5), 0.5) for node in key]
        activity = [self._safe_float(graph.nodes[node].get("monthly_transaction_count", 0), 0.0) for node in key]
        metrics = {
            "transactions": transactions,
            "total_amount": total_amount,
            "density": edges / denominator if denominator else 0.0,
            "avg_risk": sum(risk) / len(risk) if risk else 0.5,
            "avg_activity": sum(activity) / len(activity) if activity else 0.0,
        }
        self.metrics_cache[key] = metrics
        return metrics

    @staticmethod
    def score_metrics(metrics: Mapping[str, Any], participant_count: int) -> float:
        size_factor = min(participant_count / 10.0, 1.0)
        amount_factor = min(float(metrics["total_amount"]) / 1_000_000.0, 1.0)
        risk_factor = max(0.0, min(float(metrics["avg_risk"]), 1.0))
        density_factor = max(0.0, min(float(metrics["density"]), 1.0))
        activity_factor = min(float(metrics["avg_activity"]) / 100.0, 1.0)
        score = (
            size_factor * 0.15
            + amount_factor * 0.25
            + risk_factor * 0.25
            + density_factor * 0.15
            + activity_factor * 0.10
        )
        return max(0.0, min(score, 1.0))

    def merge_overlapping_cycle_records(
        self,
        graph: nx.DiGraph,
        records: Iterable[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows = [dict(record) for record in records if record.get("participants")]
        if not rows:
            return []
        parent = list(range(len(rows)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        owner: Dict[str, int] = {}
        sets: List[set[str]] = []
        for index, row in enumerate(rows):
            participants = {str(item) for item in row["participants"]}
            sets.append(participants)
            for participant in participants:
                if participant in owner:
                    union(index, owner[participant])
                else:
                    owner[participant] = index

        groups: Dict[int, List[int]] = {}
        for index in range(len(rows)):
            groups.setdefault(find(index), []).append(index)
        merged = []
        for group_index, indexes in enumerate(groups.values()):
            participants = sorted(set().union(*(sets[index] for index in indexes)))
            metrics = self.group_metrics(graph, participants)
            merged.append(
                {
                    "component_id": f"HYBRID_V02_COMPONENT_{group_index:04d}",
                    "participants": participants,
                    "participant_count": len(participants),
                    "cycle_size": len(participants),
                    "candidate_cycle_sizes": sorted({int(rows[index].get("cycle_size", 0)) for index in indexes}),
                    "fragment_count": len(indexes),
                    "cycles": sum(int(rows[index].get("cycles", 1)) for index in indexes),
                    "transactions": metrics["transactions"],
                    "total_amount": round(metrics["total_amount"], 3),
                    "density": round(metrics["density"], 4),
                    "avg_kyc_risk_score": round(metrics["avg_risk"], 4),
                    "avg_monthly_transaction_count": round(metrics["avg_activity"], 3),
                    "score": round(self.score_metrics(metrics, len(participants)), 4),
                    "metrics_are_group_level": True,
                    "method": "hybrid_networkx_component_merge_v02",
                }
            )
        return merged

    @staticmethod
    def build_summary(
        graph: nx.DiGraph,
        raw_count: int,
        unique_count: int,
        merged_count: int,
        results: Sequence[Mapping[str, Any]],
        cycle_sizes: Sequence[int],
        elapsed_ms: float,
        load_elapsed_ms: float,
        detect_elapsed_ms: float,
        raw_by_size: Mapping[str, int],
    ) -> Dict[str, Any]:
        return {
            "approach": "hybrid_neo4j_networkx_v02_label_blind",
            "graph_stats": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "density": round(nx.density(graph), 6) if graph.number_of_nodes() > 1 else 0.0,
            },
            "parameters": {"cycle_sizes": list(cycle_sizes)},
            "raw_result_count": raw_count,
            "unique_participant_sets": unique_count,
            "merged_result_count": merged_count,
            "results_by_cycle_size": dict(raw_by_size),
            "elapsed_ms": round(elapsed_ms, 3),
            "load_elapsed_ms": round(load_elapsed_ms, 3),
            "detect_elapsed_ms": round(detect_elapsed_ms, 3),
            "sample_results": list(results[:10]),
        }

    def run(
        self,
        cycle_sizes: Sequence[int] = (3, 5, 8),
        limit: int = 0,
        min_component_size: int = 3,
        max_component_size: int = 12,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        graph = self.load_graph_from_neo4j()
        load_elapsed_ms = (time.perf_counter() - started) * 1000
        detect_started = time.perf_counter()
        results = self.detect_cycles(
            graph,
            cycle_sizes=cycle_sizes,
            limit=limit,
            min_component_size=min_component_size,
            max_component_size=max_component_size,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
        )
        detect_elapsed_ms = (time.perf_counter() - detect_started) * 1000
        return self.build_summary(
            graph,
            len(self.last_raw_results),
            self.last_unique_count,
            len(self.merge_overlapping_cycle_records(graph, self.last_raw_results)),
            results,
            cycle_sizes,
            (time.perf_counter() - started) * 1000,
            load_elapsed_ms,
            detect_elapsed_ms,
            self.last_raw_by_size,
        )

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            result = float(value)
            return default if math.isnan(result) else result
        except (TypeError, ValueError):
            return default


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for count, record in enumerate(records, 1):
            row = dict(record)
            row.setdefault("ring_id", f"HYBRID_V02_{count - 1:04d}")
            row.setdefault("ring_type", "detected_cycle_component")
            row.setdefault("source_approach", "hybrid_neo4j_networkx_v02_label_blind")
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return count


def parse_cycle_sizes(value: str) -> Tuple[int, ...]:
    sizes = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    if not sizes or any(size < 2 for size in sizes):
        raise argparse.ArgumentTypeError("cycle sizes must be integers >= 2")
    return sizes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Neo4j + NetworkX detector v02")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--cycle-sizes", type=parse_cycle_sizes, default=(3, 5, 8))
    parser.add_argument("--limit", type=int, default=0, help="Limit after merge; 0 returns all merged candidates")
    parser.add_argument("--min-component-size", type=int, default=3)
    parser.add_argument("--max-component-size", type=int, default=12)
    parser.add_argument("--min-internal-transactions", type=int, default=0)
    parser.add_argument("--min-total-amount", type=float, default=0.0)
    parser.add_argument("--json-out", default="data/cycledetection/hybrid_v02/summary.json")
    parser.add_argument("--raw-jsonl-out", default="data/cycledetection/hybrid_v02/raw_candidates.jsonl")
    parser.add_argument("--merged-jsonl-out", default="data/cycledetection/hybrid_v02/merged_candidates.jsonl")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    detector = HybridNetworkXCycleDetectorV02(
        args.uri,
        args.user,
        args.password,
        database=args.database,
        logger=None if args.quiet else progress_log,
    )
    try:
        summary = detector.run(
            cycle_sizes=args.cycle_sizes,
            limit=args.limit,
            min_component_size=args.min_component_size,
            max_component_size=args.max_component_size,
            min_internal_transactions=args.min_internal_transactions,
            min_total_amount=args.min_total_amount,
        )
        raw_count = write_jsonl(args.raw_jsonl_out, detector.last_raw_results)
        merged_count = write_jsonl(args.merged_jsonl_out, detector.last_results)
        summary["raw_jsonl_count"] = raw_count
        summary["merged_jsonl_count"] = merged_count
        write_json(args.json_out, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    finally:
        detector.close()


if __name__ == "__main__":
    main()
