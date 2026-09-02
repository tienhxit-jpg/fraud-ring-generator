"""
Approach 3: Hybrid Neo4j pull + Python NetworkX cycle detection.

This script implements the Hybrid strategy from Cycle_Detection_Neo4j_Strategies.md:
- Pull Account nodes and logical account-to-account edges from Neo4j via
  (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)
- Build a NetworkX directed graph locally
- Enumerate simple cycles with an explicit length limit
- Score cycles using size, amount, participant risk, density, and activity
- Export ground-truth-like JSONL without writing answer-key FraudRing nodes back to Neo4j

Example:
    python src/cycle_detection/hybrid_networkx_cycle_detection.py \
        --uri bolt://localhost:7687 --user neo4j --password password \
        --max-cycle-length 8 --limit 100 --jsonl-out data/cycledetection/hybrid_cycle/v03.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx
from neo4j import GraphDatabase

try:
    from src.neo4j_config import NEO4J_CONFIG
except ModuleNotFoundError:
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.neo4j_config import NEO4J_CONFIG

try:
    from src.cycle_detection.result_io import save_cycle_records_jsonl
except ModuleNotFoundError:  # Allows direct execution from src/cycle_detection
    from result_io import save_cycle_records_jsonl


DEFAULT_URI = NEO4J_CONFIG.uri
DEFAULT_USER = NEO4J_CONFIG.user
DEFAULT_PASSWORD = NEO4J_CONFIG.password
DEFAULT_DATABASE = NEO4J_CONFIG.database


class HybridNetworkXCycleDetector:
    """Load Neo4j graph into NetworkX and perform flexible local analysis."""

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        database: Optional[str] = None,
        driver: Any = "auto",
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password)) if driver == "auto" else driver
        self.database = database
        self.last_results: List[Dict[str, Any]] = []

    def _session(self):
        return self.driver.session(database=self.database) if self.database else self.driver.session()

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def load_graph_from_neo4j(self) -> nx.DiGraph:
        if self.driver is None:
            raise RuntimeError("Neo4j driver is required to load graph data")

        graph = nx.DiGraph()
        with self._session() as session:
            node_result = session.run(
                """
                MATCH (a:Account)
                RETURN a.account_id AS account_id,
                       coalesce(a.kyc_risk_score, 0.5) AS risk_score,
                       coalesce(a.monthly_transaction_count, 0) AS monthly_transaction_count,
                       coalesce(a.fraud_ring_member, false) AS fraud_ring_member
                """
            )
            for record in node_result:
                graph.add_node(
                    record["account_id"],
                    risk_score=float(record["risk_score"] or 0.5),
                    monthly_transaction_count=float(record["monthly_transaction_count"] or 0),
                    fraud_ring_member=bool(record["fraud_ring_member"]),
                )

            edge_result = session.run(
                """
                MATCH (a:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(b:Account)
                RETURN a.account_id AS source,
                       b.account_id AS destination,
                       t.transaction_id AS transaction_id,
                       coalesce(t.amount_usd, t.amount, 0) AS amount,
                       coalesce(t.is_fraud, 0) AS is_fraud,
                       t.fraud_ring_id AS fraud_ring_id,
                       t.cycle_num AS cycle_num,
                       toString(t.timestamp) AS timestamp
                """
            )
            for record in edge_result:
                amount = float(record["amount"] or 0)
                source = record["source"]
                destination = record["destination"]
                is_fraud = int(record["is_fraud"] or 0)
                transaction_id = record.get("transaction_id")
                fraud_ring_id = record.get("fraud_ring_id")
                cycle_num = record.get("cycle_num")
                if graph.has_edge(source, destination):
                    edge = graph[source][destination]
                    edge["weight"] += amount
                    edge["amount"] += amount
                    edge["transaction_count"] += 1
                    edge["fraud_transaction_count"] += is_fraud
                    if transaction_id is not None:
                        edge["transaction_ids"].append(transaction_id)
                    if fraud_ring_id is not None:
                        edge["fraud_ring_ids"].add(str(fraud_ring_id))
                    if cycle_num is not None:
                        edge["cycle_nums"].add(str(cycle_num))
                else:
                    graph.add_edge(
                        source,
                        destination,
                        weight=amount,
                        amount=amount,
                        timestamp=record["timestamp"],
                        transaction_count=1,
                        fraud_transaction_count=is_fraud,
                        transaction_ids=[transaction_id] if transaction_id is not None else [],
                        fraud_ring_ids={str(fraud_ring_id)} if fraud_ring_id is not None else set(),
                        cycle_nums={str(cycle_num)} if cycle_num is not None else set(),
                    )

        return graph

    def detect_cycles(
        self,
        graph: nx.DiGraph,
        max_cycle_length: int = 10,
        limit: int = 500,
        min_component_size: int = 2,
        max_component_size: int = 12,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Find simple directed cycles and merge overlapping fragments into rings.

        NetworkX returns one row per simple cycle/path fragment. A single fraud
        ring, especially a dense or multi-cycle SCC, can therefore appear as
        many overlapping cycle rows. For ring-level evaluation we first dedupe
        exact participant sets, then merge records that share at least one
        participant into one component-level ring candidate.
        """
        scored_by_group: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        components = sorted(nx.strongly_connected_components(graph), key=len, reverse=True)
        for component in components:
            if len(component) < min_component_size or len(component) > max_component_size:
                continue
            subgraph = graph.subgraph(component).copy()
            for cycle in nx.simple_cycles(subgraph, length_bound=max_cycle_length):
                if len(cycle) < min_component_size:
                    continue
                described = self.describe_cycle(graph, cycle)
                if require_fraud_evidence and described.get("fraud_transaction_count", 0) <= 0 and described.get("fraud_member_count", 0) <= 0:
                    continue
                if described.get("group_transactions", described.get("transactions", 0)) < min_internal_transactions:
                    continue
                if described.get("group_total_amount", described.get("total_amount", 0.0)) < min_total_amount:
                    continue
                key = tuple(sorted(str(item) for item in described["participants"]))
                if key in scored_by_group:
                    existing = scored_by_group[key]
                    existing["cycles"] = int(existing.get("cycles", 1)) + 1
                    if described.get("score", 0) > existing.get("score", 0):
                        described["cycles"] = existing["cycles"]
                        scored_by_group[key] = described
                else:
                    scored_by_group[key] = described
                if limit > 0 and len(scored_by_group) >= limit * 5:
                    break
            if limit > 0 and len(scored_by_group) >= limit * 5:
                break

        scored = self.merge_overlapping_cycle_records(graph, scored_by_group.values())
        scored.sort(key=lambda item: (item["score"], item["total_amount"], item["cycle_size"]), reverse=True)
        return scored[:limit] if limit > 0 else scored

    def merge_overlapping_cycle_records(
        self,
        graph: nx.DiGraph,
        records: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Merge overlapping NetworkX cycle fragments into component-level rings.

        Records sharing any participant are treated as fragments of the same
        account group. The merged record recomputes amount, transaction, risk,
        density, and score over the full union of participants so exported JSONL
        has one row per ring/component rather than one row per cycle path.
        """

        cycle_records = [dict(record) for record in records if record.get("participants")]
        if not cycle_records:
            return []

        parent = list(range(len(cycle_records)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        participant_owner: Dict[str, int] = {}
        participant_sets: List[set[str]] = []
        for index, record in enumerate(cycle_records):
            participants = {str(item) for item in (record.get("participants") or []) if item is not None}
            participant_sets.append(participants)
            for participant in participants:
                if participant in participant_owner:
                    union(index, participant_owner[participant])
                else:
                    participant_owner[participant] = index

        grouped: Dict[int, List[int]] = {}
        for index in range(len(cycle_records)):
            grouped.setdefault(find(index), []).append(index)

        component_records: List[Dict[str, Any]] = []
        for component_index, member_indexes in enumerate(grouped.values()):
            participants = sorted(set().union(*(participant_sets[index] for index in member_indexes)))
            source_records = [cycle_records[index] for index in member_indexes]
            cycle_sizes = sorted({int(record.get("cycle_size") or len(record.get("participants") or [])) for record in source_records})
            total_amount = self.get_internal_group_amount(graph, participants)
            group_transactions = self.get_internal_group_transaction_count(graph, participants)
            fraud_transaction_count = self.get_internal_group_fraud_transaction_count(graph, participants)
            fraud_member_count = sum(1 for node in participants if graph.nodes[node].get("fraud_ring_member"))
            risk_values = [self._safe_float(graph.nodes[node].get("risk_score", 0.5), 0.5) for node in participants]
            activity_values = [self._safe_float(graph.nodes[node].get("monthly_transaction_count", 0), 0) for node in participants]
            avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0.5
            avg_activity = sum(activity_values) / len(activity_values) if activity_values else 0.0
            density = self.calculate_cycle_density(graph, participants)
            score = self.score_cycle(graph, participants)

            component_records.append(
                {
                    "component_id": f"HYBRID_COMPONENT_{component_index:04d}",
                    "participants": participants,
                    "cycle_size": len(participants),
                    "transactions": group_transactions,
                    "total_amount": round(total_amount, 3),
                    "group_transactions": group_transactions,
                    "group_total_amount": round(total_amount, 3),
                    "fraud_transaction_count": fraud_transaction_count,
                    "fraud_member_count": fraud_member_count,
                    "metrics_are_group_level": True,
                    "cycles": sum(int(record.get("cycles") or 1) for record in source_records),
                    "candidate_cycle_sizes": cycle_sizes,
                    "fragment_count": len(source_records),
                    "avg_kyc_risk_score": round(avg_risk, 4),
                    "avg_monthly_transaction_count": round(avg_activity, 3),
                    "density": round(density, 4),
                    "score": round(score, 4),
                    "method": "hybrid_networkx_component_merge",
                }
            )

        return component_records

    def describe_cycle(self, graph: nx.DiGraph, cycle: Sequence[str]) -> Dict[str, Any]:
        total_amount = self.get_internal_group_amount(graph, cycle)
        density = self.calculate_cycle_density(graph, cycle)
        risk_values = [self._safe_float(graph.nodes[node].get("risk_score", 0.5), 0.5) for node in cycle]
        activity_values = [self._safe_float(graph.nodes[node].get("monthly_transaction_count", 0), 0) for node in cycle]
        avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0.5
        avg_activity = sum(activity_values) / len(activity_values) if activity_values else 0.0
        score = self.score_cycle(graph, cycle)
        group_transactions = self.get_internal_group_transaction_count(graph, cycle)
        fraud_transaction_count = self.get_internal_group_fraud_transaction_count(graph, cycle)
        fraud_member_count = sum(1 for node in cycle if graph.nodes[node].get("fraud_ring_member"))

        return {
            "participants": list(cycle),
            "cycle_size": len(cycle),
            "transactions": group_transactions,
            "total_amount": round(total_amount, 3),
            "group_transactions": group_transactions,
            "group_total_amount": round(total_amount, 3),
            "fraud_transaction_count": fraud_transaction_count,
            "fraud_member_count": fraud_member_count,
            "metrics_are_group_level": True,
            "cycles": 1,
            "avg_kyc_risk_score": round(avg_risk, 4),
            "avg_monthly_transaction_count": round(avg_activity, 3),
            "density": round(density, 4),
            "score": round(score, 4),
            "method": "hybrid_networkx_simple_cycles",
        }

    def score_cycle(self, graph: nx.DiGraph, cycle: Sequence[str]) -> float:
        """
        Score fraud likelihood in [0, 1].

        Higher values mean the cycle is more suspicious. The formula follows the
        markdown idea and keeps every factor bounded so the result is stable for
        research comparison:
        - size factor: larger rings up to 10 nodes
        - amount factor: saturates at 100,000
        - risk factor: low KYC score is interpreted as higher risk, matching the
          source markdown's inverted risk example
        - density factor: extra internal transfers among participants
        - activity factor: saturates at 100 monthly transactions
        """
        if not cycle:
            return 0.0

        total_amount = self.get_internal_group_amount(graph, cycle)
        density = self.calculate_cycle_density(graph, cycle)
        avg_risk = self._average(graph.nodes[node].get("risk_score", 0.5) for node in cycle)
        avg_activity = self._average(graph.nodes[node].get("monthly_transaction_count", 0) for node in cycle)
        fraud_transaction_count = self.get_internal_group_fraud_transaction_count(graph, cycle)
        fraud_member_count = sum(1 for node in cycle if graph.nodes[node].get("fraud_ring_member"))

        size_factor = min(len(cycle) / 10.0, 1.0)
        amount_factor = min(total_amount / 1_000_000.0, 1.0)
        risk_factor = max(0.0, min(1.0, avg_risk))
        activity_factor = min(avg_activity / 100.0, 1.0)
        fraud_evidence_factor = 1.0 if fraud_transaction_count > 0 or fraud_member_count > 0 else 0.0

        score = (
            size_factor * 0.15
            + amount_factor * 0.25
            + risk_factor * 0.25
            + density * 0.15
            + activity_factor * 0.10
            + fraud_evidence_factor * 0.10
        )
        return max(0.0, min(score, 1.0))

    def get_cycle_amount(self, graph: nx.DiGraph, cycle: Sequence[str]) -> float:
        total = 0.0
        for source, destination in self._cycle_edges(cycle):
            if graph.has_edge(source, destination):
                total += self._safe_float(graph[source][destination].get("weight", 0), 0.0)
        return total

    def get_cycle_transaction_count(self, graph: nx.DiGraph, cycle: Sequence[str]) -> int:
        total = 0
        for source, destination in self._cycle_edges(cycle):
            if graph.has_edge(source, destination):
                total += int(graph[source][destination].get("transaction_count", 1))
        return total

    def get_internal_group_amount(self, graph: nx.DiGraph, participants: Sequence[str]) -> float:
        participant_set = set(participants)
        total = 0.0
        for source, destination, data in graph.subgraph(participant_set).edges(data=True):
            total += self._safe_float(data.get("amount", data.get("weight", 0)), 0.0)
        return total

    def get_internal_group_transaction_count(self, graph: nx.DiGraph, participants: Sequence[str]) -> int:
        participant_set = set(participants)
        total = 0
        for _, _, data in graph.subgraph(participant_set).edges(data=True):
            total += int(data.get("transaction_count", 0) or 0)
        return total

    def get_internal_group_fraud_transaction_count(self, graph: nx.DiGraph, participants: Sequence[str]) -> int:
        participant_set = set(participants)
        total = 0
        for _, _, data in graph.subgraph(participant_set).edges(data=True):
            total += int(data.get("fraud_transaction_count", 0) or 0)
        return total

    def calculate_cycle_density(self, graph: nx.DiGraph, cycle: Sequence[str]) -> float:
        if len(cycle) <= 1:
            return 0.0
        subgraph = graph.subgraph(cycle)
        max_edges = len(cycle) * (len(cycle) - 1)
        return subgraph.number_of_edges() / max_edges if max_edges else 0.0

    def save_results_to_neo4j(self, cycles: Sequence[Dict[str, Any]], max_save: int = 500) -> int:
        """Disabled: do not write detected answer-key-like FraudRing nodes into the detection graph."""
        raise RuntimeError(
            "Saving Hybrid results to Neo4j is disabled to avoid leaking detected/answer-key FraudRing nodes "
            "back into the graph. Use --jsonl-out for evaluation artifacts instead."
        )

    def run(
        self,
        max_cycle_length: int = 10,
        limit: int = 500,
        min_component_size: int = 2,
        max_component_size: int = 12,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
        save: bool = False,
        max_save: int = 500,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        graph = self.load_graph_from_neo4j()
        load_elapsed_ms = (time.perf_counter() - start) * 1000

        detect_start = time.perf_counter()
        cycles = self.detect_cycles(
            graph,
            max_cycle_length=max_cycle_length,
            limit=limit,
            min_component_size=min_component_size,
            max_component_size=max_component_size,
            require_fraud_evidence=require_fraud_evidence,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
        )
        self.last_results = cycles
        detect_elapsed_ms = (time.perf_counter() - detect_start) * 1000

        saved_count = self.save_results_to_neo4j(cycles, max_save=max_save) if save else 0
        elapsed_ms = (time.perf_counter() - start) * 1000

        return self.build_research_summary(
            graph=graph,
            cycles=cycles,
            max_cycle_length=max_cycle_length,
            min_component_size=min_component_size,
            max_component_size=max_component_size,
            require_fraud_evidence=require_fraud_evidence,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
            elapsed_ms=elapsed_ms,
            load_elapsed_ms=load_elapsed_ms,
            detect_elapsed_ms=detect_elapsed_ms,
            saved_count=saved_count,
        )

    @staticmethod
    def build_research_summary(
        graph: nx.DiGraph,
        cycles: Sequence[Dict[str, Any]],
        max_cycle_length: int,
        min_component_size: int,
        max_component_size: int,
        require_fraud_evidence: bool,
        min_internal_transactions: int,
        min_total_amount: float,
        elapsed_ms: float,
        load_elapsed_ms: float,
        detect_elapsed_ms: float,
        saved_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "approach": "hybrid_neo4j_networkx",
            "graph_stats": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "density": round(nx.density(graph), 6) if graph.number_of_nodes() > 1 else 0,
            },
            "parameters": {
                "max_cycle_length": max_cycle_length,
                "min_component_size": min_component_size,
                "max_component_size": max_component_size,
                "require_fraud_evidence": require_fraud_evidence,
                "min_internal_transactions": min_internal_transactions,
                "min_total_amount": min_total_amount,
            },
            "result_count": len(cycles),
            "saved_to_neo4j_count": saved_count,
            "elapsed_ms": round(elapsed_ms, 3),
            "load_elapsed_ms": round(load_elapsed_ms, 3),
            "detect_elapsed_ms": round(detect_elapsed_ms, 3),
            "sample_results": list(cycles[:10]),
            "notes": [
                "NetworkX simple_cycles enumerates directed cycle fragments within bounded SCCs and the selected length bound.",
                "Overlapping cycle fragments are merged into component-level ring candidates and enriched with group-level internal transaction metrics.",
                "Generated fraud evidence can be used as an optional evaluation/debug filter without importing FraudRing nodes.",
                "Saving results back to Neo4j is disabled; use --jsonl-out to avoid leaking answer-key-like FraudRing nodes into the detection graph.",
            ],
        }

    @staticmethod
    def _cycle_edges(cycle: Sequence[str]) -> Iterable[Tuple[str, str]]:
        for index, source in enumerate(cycle):
            yield source, cycle[(index + 1) % len(cycle)]

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            result = float(value)
            return default if math.isnan(result) else result
        except (TypeError, ValueError):
            return default

    @classmethod
    def _average(cls, values: Iterable[Any]) -> float:
        cleaned = [cls._safe_float(value, 0.0) for value in values]
        return sum(cleaned) / len(cleaned) if cleaned else 0.0


def print_research_output(summary: Dict[str, Any]) -> None:
    print("=" * 78)
    print("APPROACH 3 - HYBRID NEO4J + PYTHON NETWORKX")
    print("=" * 78)
    print(f"Nodes / Edges       : {summary['graph_stats'].get('nodes', 0)} / {summary['graph_stats'].get('edges', 0)}")
    print(f"Graph density       : {summary['graph_stats'].get('density', 0)}")
    print(f"Max cycle length    : {summary['parameters'].get('max_cycle_length')}")
    print(f"SCC size bounds     : {summary['parameters'].get('min_component_size')}..{summary['parameters'].get('max_component_size')}")
    print(f"Require fraud ev.   : {summary['parameters'].get('require_fraud_evidence')}")
    print(f"Min tx / amount     : {summary['parameters'].get('min_internal_transactions')} / {summary['parameters'].get('min_total_amount')}")
    print(f"Rings returned      : {summary['result_count']}")
    print(f"Saved to Neo4j      : {summary['saved_to_neo4j_count']}")
    print(f"Load runtime        : {summary['load_elapsed_ms']} ms")
    print(f"Detection runtime   : {summary['detect_elapsed_ms']} ms")
    print(f"Total runtime       : {summary['elapsed_ms']} ms")
    print("\nTop scored cycles:")
    for idx, item in enumerate(summary.get("sample_results", []), start=1):
        print(
            f"  {idx:02d}. score={item.get('score')} size={item.get('cycle_size')} "
            f"amount={item.get('total_amount')} density={item.get('density')} "
            f"participants={item.get('participants')}"
        )
    print("\nJSON_RESULT:")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Neo4j + NetworkX cycle detection for Account-Transaction-Account graph")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name (Aura normally uses neo4j)")
    parser.add_argument("--max-cycle-length", type=int, default=10, help="Bound for NetworkX simple cycle enumeration")
    parser.add_argument("--min-component-size", type=int, default=2, help="Minimum SCC size to enumerate")
    parser.add_argument("--max-component-size", type=int, default=12, help="Maximum SCC size; skips giant random SCCs")
    parser.add_argument("--limit", type=int, default=500, help="Maximum component rings to return; use 0 for all rings")
    parser.add_argument("--require-fraud-evidence", action="store_true", help="Keep only candidates with generated fraud evidence: fraud transaction or fraud_ring_member account")
    parser.add_argument("--min-internal-transactions", type=int, default=0, help="Minimum distinct internal transactions in the candidate account group")
    parser.add_argument("--min-total-amount", type=float, default=0.0, help="Minimum total internal amount in the candidate account group")
    parser.add_argument("--save", action="store_true", help="Disabled: kept only for backwards compatibility; use --jsonl-out instead")
    parser.add_argument("--max-save", type=int, default=500, help="Maximum rings to save when --save is enabled")
    parser.add_argument("--json-out", default=None, help="Optional path to save summary JSON")
    parser.add_argument(
        "--jsonl-out",
        default=None,
        help="Optional path to save full detected fraud rings as JSONL, one ground-truth-like ring per line",
    )
    parser.add_argument("--min-fraud-score", type=float, default=0.35, help="Minimum heuristic fraud score for JSONL fraud-ring output")
    parser.add_argument("--include-non-fraud", action="store_true", help="Include benign cycle rings in JSONL instead of filtering to fraud only")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    detector = HybridNetworkXCycleDetector(args.uri, args.user, args.password, database=args.database)
    try:
        summary = detector.run(
            max_cycle_length=args.max_cycle_length,
            limit=args.limit,
            min_component_size=args.min_component_size,
            max_component_size=args.max_component_size,
            require_fraud_evidence=args.require_fraud_evidence,
            min_internal_transactions=args.min_internal_transactions,
            min_total_amount=args.min_total_amount,
            save=args.save,
            max_save=args.max_save,
        )
        print_research_output(summary)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            print(f"\nSaved JSON summary to: {args.json_out}")
        if args.jsonl_out:
            rings = save_cycle_records_jsonl(
                args.jsonl_out,
                detector.last_results,
                ring_id_prefix="RING",
                ring_type="detected_cycle",
                source_approach=summary["approach"],
                include_instances=False,
                fraud_only=not args.include_non_fraud,
                min_fraud_score=args.min_fraud_score,
            )
            mode = "fraud-ring" if not args.include_non_fraud else "cycle/ring"
            print(f"Saved {len(rings)} {mode} records to JSONL: {args.jsonl_out}")
    finally:
        detector.close()


if __name__ == "__main__":
    main()
