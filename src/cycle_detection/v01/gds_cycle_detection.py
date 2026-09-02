"""
Approach 2: Neo4j Graph Data Science (GDS) cycle/ring detection.

This script implements the GDS strategy from Cycle_Detection_Neo4j_Strategies.md:
- Strongly Connected Components (SCC): components with >= 2 nodes contain cycles
- Louvain communities: dense suspicious groups
- Triangle count: 3-account ring indicator
- Betweenness centrality: possible organizers/hubs

Example:
    python src/cycle_detection/gds_cycle_detection.py \
        --uri bolt://localhost:7687 --user neo4j --password password --limit 100

Requires the Neo4j GDS plugin installed on the database.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

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


class GDSCycleDetector:
    """Detect likely fraud rings with Neo4j GDS algorithms."""

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        database: Optional[str] = None,
        driver: Any = None,
    ) -> None:
        self.driver = driver or GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.last_results: List[Dict[str, Any]] = []

    def _session(self):
        return self.driver.session(database=self.database) if self.database else self.driver.session()

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def verify_gds_available(self) -> Dict[str, Any]:
        """Return GDS version without relying on procedure YIELD columns.

        Some GDS/Neo4j combinations reject the procedure/YIELD form of
        gds.version(), for example by raising "Unknown procedure output: version".
        The scalar function form is the most stable API across versions.
        """
        with self._session() as session:
            try:
                record = session.run("RETURN gds.version() AS version").single()
            except Neo4jError as exc:
                message = str(exc)
                if "Unknown function" in message or "There is no function" in message or "gds.version" in message:
                    return {
                        "gds_version": None,
                        "gds_available": False,
                        "error": "GDS plugin/function gds.version() is not available; verify Neo4j Graph Data Science is installed and enabled.",
                    }
                raise
        return {
            "gds_version": record["version"] if record else None,
            "gds_available": bool(record and record["version"]),
        }

    def get_graph_stats(self) -> Dict[str, int]:
        with self._session() as session:
            record = session.run(
                """
                MATCH (a:Account)
                WITH count(a) AS nodes
                OPTIONAL MATCH (:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(:Account)
                RETURN nodes, count(t) AS edges
                """
            ).single()
        if record is None:
            return {"nodes": 0, "edges": 0}
        return {"nodes": int(record["nodes"] or 0), "edges": int(record["edges"] or 0)}

    def project_graph(self, graph_name: str, orientation: str = "NATURAL", projection_scope: str = "all") -> Dict[str, Any]:
        """Project an Account-to-Account graph from Transaction nodes.

        Source schema:
            (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)

        GDS algorithms need direct source/target rows, so we use Cypher projection.
        For triangle counting we duplicate each edge in reverse to emulate an
        undirected account graph.

        projection_scope:
            all            -> every derived transfer edge
            fraud_evidence -> only edges/accounts carrying generated fraud markers
        """
        self.drop_graph_if_exists(graph_name)
        node_query = "MATCH (a:Account) RETURN id(a) AS id"
        scope_predicate = ""
        if projection_scope == "fraud_evidence":
            scope_predicate = """
            WHERE coalesce(t.is_fraud, 0) = 1
               OR t.fraud_ring_id IS NOT NULL
               OR coalesce(src.fraud_ring_member, false) = true
               OR coalesce(dst.fraud_ring_member, false) = true
            """
        elif projection_scope != "all":
            raise ValueError(f"Unsupported projection_scope: {projection_scope}")

        if orientation == "UNDIRECTED":
            relationship_query = f"""
            MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
            {scope_predicate}
            RETURN id(src) AS source, id(dst) AS target, coalesce(t.amount_usd, t.amount, 0.0) AS amount
            UNION ALL
            MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
            {scope_predicate}
            RETURN id(dst) AS source, id(src) AS target, coalesce(t.amount_usd, t.amount, 0.0) AS amount
            """
        else:
            relationship_query = f"""
            MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
            {scope_predicate}
            RETURN id(src) AS source, id(dst) AS target, coalesce(t.amount_usd, t.amount, 0.0) AS amount
            """

        with self._session() as session:
            record = session.run(
                """
                CALL gds.graph.project.cypher(
                    $graph_name,
                    $node_query,
                    $relationship_query
                )
                YIELD graphName, nodeCount, relationshipCount, projectMillis
                RETURN graphName, nodeCount, relationshipCount, projectMillis
                """,
                graph_name=graph_name,
                node_query=node_query,
                relationship_query=relationship_query,
            ).single()
        return dict(record) if record else {}

    def drop_graph_if_exists(self, graph_name: str) -> None:
        with self._session() as session:
            exists = session.run(
                "CALL gds.graph.exists($graph_name) YIELD exists RETURN exists",
                graph_name=graph_name,
            ).single()["exists"]
            if exists:
                session.run("CALL gds.graph.drop($graph_name) YIELD graphName RETURN graphName", graph_name=graph_name).consume()

    def run_scc(self, graph_name: str, limit: int = 100, min_size: int = 3, max_size: int = 12) -> List[Dict[str, Any]]:
        limit_clause = "LIMIT $limit" if limit > 0 else ""
        with self._session() as session:
            records = session.run(
                f"""
                CALL gds.scc.stream($graph_name)
                YIELD nodeId, componentId
                WITH componentId, collect(gds.util.asNode(nodeId).account_id) AS accounts
                WHERE size(accounts) >= $min_size AND size(accounts) <= $max_size
                RETURN componentId,
                       accounts AS accounts_in_cycle,
                       size(accounts) AS cycle_size
                ORDER BY cycle_size DESC, componentId
                {limit_clause}
                """,
                graph_name=graph_name,
                min_size=min_size,
                max_size=max_size,
                limit=limit,
            )
            return self.normalize_scc_records(dict(record) for record in records)

    @staticmethod
    def normalize_scc_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for record in records:
            normalized.append(
                {
                    "component_id": record.get("componentId"),
                    "participants": list(record.get("accounts_in_cycle") or []),
                    "cycle_size": int(record.get("cycle_size") or 0),
                    "method": "gds_scc",
                }
            )
        return normalized

    def run_louvain(self, graph_name: str, limit: int = 50, min_size: int = 3, max_size: int = 12) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(
                """
                CALL gds.louvain.stream($graph_name)
                YIELD nodeId, communityId
                WITH communityId, collect(gds.util.asNode(nodeId).account_id) AS members
                WHERE size(members) >= $min_size AND size(members) <= $max_size
                RETURN communityId,
                       members AS community_members,
                       size(members) AS community_size
                ORDER BY community_size DESC, communityId
                LIMIT $limit
                """,
                graph_name=graph_name,
                min_size=min_size,
                max_size=max_size,
                limit=limit,
            )
            return [
                {
                    "community_id": record["communityId"],
                    "participants": list(record["community_members"] or []),
                    "community_size": int(record["community_size"] or 0),
                    "method": "gds_louvain",
                }
                for record in result
            ]

    def run_triangle_count(self, graph_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(
                """
                CALL gds.triangleCount.stream($graph_name)
                YIELD nodeId, triangleCount
                WITH gds.util.asNode(nodeId) AS node, triangleCount
                WHERE triangleCount > 0
                RETURN node.account_id AS account_id,
                       triangleCount,
                       node.kyc_risk_score AS kyc_risk_score,
                       'gds_triangle_count' AS method
                ORDER BY triangleCount DESC
                LIMIT $limit
                """,
                graph_name=graph_name,
                limit=limit,
            )
            return [dict(record) for record in result]

    def run_triangle_count_cypher(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fallback triangle indicator that does not require an undirected GDS projection.

        GDS triangleCount refuses directed projections. Cypher projection by
        source/target rows can duplicate reverse edges but some GDS versions
        still mark the relationship type as directed, causing:
        "TriangleCount requires relationship projections to be UNDIRECTED".
        This fallback reports per-account directed 3-cycle participation using
        the same Account-Transaction-Account schema.
        """
        with self._session() as session:
            result = session.run(
                """
                MATCH (a:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(b:Account)
                MATCH (b)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(c:Account)
                MATCH (c)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a)
                WHERE a.account_id <> b.account_id
                  AND a.account_id <> c.account_id
                  AND b.account_id <> c.account_id
                  AND a.account_id = reduce(min_id = a.account_id, id IN [b.account_id, c.account_id] | CASE WHEN id < min_id THEN id ELSE min_id END)
                WITH DISTINCT [a.account_id, b.account_id, c.account_id] AS triangle,
                     [a, b, c] AS nodes
                UNWIND nodes AS node
                RETURN node.account_id AS account_id,
                       count(*) AS triangleCount,
                       node.kyc_risk_score AS kyc_risk_score,
                       'cypher_directed_triangle_fallback' AS method
                ORDER BY triangleCount DESC, account_id
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(record) for record in result]

    def run_betweenness(self, graph_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(
                """
                CALL gds.betweenness.stream($graph_name)
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS node, score
                WHERE score > 0
                RETURN node.account_id AS account_id,
                       score AS centrality_score,
                       node.kyc_risk_score AS kyc_risk_score,
                       node.monthly_transaction_count AS monthly_transaction_count
                ORDER BY centrality_score DESC
                LIMIT $limit
                """,
                graph_name=graph_name,
                limit=limit,
            )
            return [dict(record) for record in result]

    def add_transaction_metrics_to_groups(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add transaction count and amount for each Account group.

        GDS returns account sets. This enriches them so JSONL records are close
        to data/synthetic/v2/ground_truth/fraud_rings.json.

        The first implementation executed one Cypher query per component. That
        is acceptable for a handful of rings, but becomes slow when SCC/Louvain
        returns many candidate groups. This version sends all groups in one
        UNWIND query and joins the metrics back in Python.
        """
        if not groups:
            return groups

        group_payload = []
        for index, group in enumerate(groups):
            participants = sorted({str(item) for item in (group.get("participants") or []) if item is not None})
            group["participants"] = participants
            group_payload.append({"idx": index, "participants": participants})

        with self._session() as session:
            records = session.run(
                """
                UNWIND $groups AS group
                WITH group.idx AS idx, group.participants AS participants
                OPTIONAL MATCH (account:Account)
                WHERE account.account_id IN participants
                WITH idx, participants, collect(DISTINCT account) AS accounts
                OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
                WHERE src.account_id IN participants
                  AND dst.account_id IN participants
                WITH idx, participants, accounts, collect(DISTINCT t) AS txs,
                     collect(DISTINCT [src.account_id, dst.account_id]) AS directed_edges
                RETURN idx,
                       size(txs) AS transactions,
                       reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0)) AS total_amount,
                       size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,
                       size([account IN accounts WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count,
                       CASE WHEN size(accounts) = 0 THEN 0.5
                            ELSE reduce(risk_total = 0.0, account IN accounts | risk_total + coalesce(account.kyc_risk_score, 0.5)) / size(accounts)
                       END AS avg_source_risk,
                       CASE WHEN size(participants) <= 1 THEN 0.0
                            ELSE toFloat(size([edge IN directed_edges WHERE edge[0] IS NOT NULL AND edge[1] IS NOT NULL])) / toFloat(size(participants) * (size(participants) - 1))
                       END AS density
                """,
                groups=group_payload,
            )
            metrics_by_index = {int(record["idx"]): dict(record) for record in records}

        for index, group in enumerate(groups):
            record = metrics_by_index.get(index, {})
            group["transactions"] = int(record.get("transactions") or 0)
            group["total_amount"] = float(record.get("total_amount") or 0.0)
            group["fraud_transaction_count"] = int(record.get("fraud_transaction_count") or 0)
            group["fraud_member_count"] = int(record.get("fraud_member_count") or 0)
            group["avg_kyc_risk_score"] = float(record.get("avg_source_risk") or 0.5)
            group["density"] = float(record.get("density") or 0.0)
            group["cycles"] = int(group.get("cycles") or 1)
            group["metrics_are_group_level"] = True
        return groups

    @staticmethod
    def build_research_summary(
        graph_stats: Dict[str, Any],
        gds_info: Dict[str, Any],
        projection: Dict[str, Any],
        scc_results: List[Dict[str, Any]],
        louvain_results: List[Dict[str, Any]],
        triangle_results: List[Dict[str, Any]],
        centrality_results: List[Dict[str, Any]],
        elapsed_ms: float,
    ) -> Dict[str, Any]:
        return {
            "approach": "neo4j_gds",
            "graph_stats": graph_stats,
            "gds_info": gds_info,
            "projection": projection,
            "elapsed_ms": round(elapsed_ms, 3),
            "scc_cycle_components": {
                "count": len(scc_results),
                "sample_results": scc_results[:10],
            },
            "louvain_communities": {
                "count": len(louvain_results),
                "sample_results": louvain_results[:10],
            },
            "triangle_accounts": {
                "count": len(triangle_results),
                "sample_results": triangle_results[:10],
            },
            "ring_leader_candidates": {
                "count": len(centrality_results),
                "sample_results": centrality_results[:10],
            },
            "notes": [
                "SCC components with >=2 nodes contain at least one directed cycle.",
                "Louvain identifies dense communities that can represent fraud rings even when exact cycles are not enumerated.",
                "Triangle indicator uses GDS triangleCount when the projection is accepted as undirected; otherwise it falls back to a directed Cypher triangle count.",
            ],
        }

    def run(
        self,
        limit: int = 100,
        keep_projection: bool = False,
        min_component_size: int = 3,
        max_component_size: int = 12,
        algorithms: str = "scc",
        projection_scope: str = "all",
    ) -> Dict[str, Any]:
        graph_name = "fraud_cycle_gds_directed"
        triangle_graph_name = "fraud_cycle_gds_undirected"
        start = time.perf_counter()
        try:
            gds_info = self.verify_gds_available()
            graph_stats = self.get_graph_stats()
            projection = self.project_graph(graph_name, orientation="NATURAL", projection_scope=projection_scope)
            projection["projection_scope"] = projection_scope

            scc_results = self.run_scc(graph_name, limit=limit, min_size=min_component_size, max_size=max_component_size)
            scc_results = self.add_transaction_metrics_to_groups(scc_results)
            self.last_results = scc_results

            louvain_results: List[Dict[str, Any]] = []
            centrality_results: List[Dict[str, Any]] = []
            triangle_results: List[Dict[str, Any]] = []
            if algorithms == "all":
                louvain_results = self.run_louvain(graph_name, limit=limit, min_size=min_component_size, max_size=max_component_size)
                louvain_results = self.add_transaction_metrics_to_groups(louvain_results)
                centrality_results = self.run_betweenness(graph_name, limit=limit)

                triangle_projection = self.project_graph(triangle_graph_name, orientation="UNDIRECTED", projection_scope=projection_scope)
                projection["triangle_projection"] = triangle_projection
                try:
                    triangle_results = self.run_triangle_count(triangle_graph_name, limit=limit)
                except Neo4jError as exc:
                    message = str(exc)
                    if "TriangleCount requires relationship projections to be UNDIRECTED" not in message:
                        raise
                    projection["triangle_count_warning"] = (
                        "GDS triangleCount rejected the Cypher-projected graph as directed; "
                        "used directed Cypher triangle fallback instead."
                    )
                    triangle_results = self.run_triangle_count_cypher(limit=limit)
            else:
                projection["execution_mode"] = "scc_only"
                projection["skipped_algorithms"] = ["louvain", "triangle_count", "betweenness"]

            elapsed_ms = (time.perf_counter() - start) * 1000
            return self.build_research_summary(
                graph_stats=graph_stats,
                gds_info=gds_info,
                projection=projection,
                scc_results=scc_results,
                louvain_results=louvain_results,
                triangle_results=triangle_results,
                centrality_results=centrality_results,
                elapsed_ms=elapsed_ms,
            )
        finally:
            if not keep_projection:
                try:
                    self.drop_graph_if_exists(graph_name)
                    self.drop_graph_if_exists(triangle_graph_name)
                except Exception:
                    # Do not hide the primary detection error with cleanup failures.
                    pass

    @staticmethod
    def dry_run_queries() -> Dict[str, str]:
        return {
            "project": "CALL gds.graph.project.cypher(... Account nodes, account-to-account edges derived from (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account) ...)",
            "scc": "CALL gds.scc.stream('fraud_cycle_gds_directed') YIELD nodeId, componentId ...",
            "louvain": "CALL gds.louvain.stream('fraud_cycle_gds_directed') YIELD nodeId, communityId ...",
            "triangle_count": "CALL gds.triangleCount.stream('fraud_cycle_gds_undirected') YIELD nodeId, triangleCount ...; if GDS rejects the projection as directed, fall back to Cypher directed 3-cycle participation count",
            "betweenness": "CALL gds.betweenness.stream('fraud_cycle_gds_directed') YIELD nodeId, score ...",
        }


def print_research_output(summary: Dict[str, Any]) -> None:
    print("=" * 78)
    print("APPROACH 2 - NEO4J GRAPH DATA SCIENCE (GDS)")
    print("=" * 78)
    print(f"GDS version     : {summary['gds_info'].get('gds_version')}")
    print(f"Nodes / Edges   : {summary['graph_stats'].get('nodes', 0)} / {summary['graph_stats'].get('edges', 0)}")
    print(f"Runtime         : {summary['elapsed_ms']} ms")
    print(f"SCC components  : {summary['scc_cycle_components']['count']}")
    print(f"Communities     : {summary['louvain_communities']['count']}")
    print(f"Triangle nodes  : {summary['triangle_accounts']['count']}")
    print(f"Hub candidates  : {summary['ring_leader_candidates']['count']}")
    print("\nTop SCC cycle components:")
    for idx, item in enumerate(summary["scc_cycle_components"]["sample_results"], start=1):
        print(f"  {idx:02d}. component={item.get('component_id')} size={item.get('cycle_size')} participants={item.get('participants')}")
    print("\nTop ring leader candidates:")
    for idx, item in enumerate(summary["ring_leader_candidates"]["sample_results"], start=1):
        print(f"  {idx:02d}. account={item.get('account_id')} centrality={item.get('centrality_score')}")
    print("\nJSON_RESULT:")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neo4j GDS cycle/ring detection for Account-Transaction-Account graph")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name (Aura normally uses neo4j)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows per selected result; use 0 for unlimited")
    parser.add_argument("--algorithms", choices=["scc", "all"], default="scc", help="scc is the fast ring-only mode; all also runs Louvain, triangle count and betweenness")
    parser.add_argument("--projection-scope", choices=["all", "fraud_evidence"], default="all", help="Project all transfer edges or only edges/accounts with generated fraud evidence markers")
    parser.add_argument("--min-component-size", type=int, default=3, help="Minimum SCC/community size to consider as a fraud-ring candidate")
    parser.add_argument("--max-component-size", type=int, default=12, help="Maximum SCC/community size; filters giant random SCCs")
    parser.add_argument("--keep-projection", action="store_true", help="Keep GDS graph projections after execution")
    parser.add_argument("--json-out", default=None, help="Optional path to save summary JSON")
    parser.add_argument(
        "--jsonl-out",
        default=None,
        help="Optional path to save full SCC fraud-ring candidates as JSONL, one ground-truth-like ring per line",
    )
    parser.add_argument("--min-fraud-score", type=float, default=0.35, help="Minimum heuristic fraud score for JSONL fraud-ring output")
    parser.add_argument("--include-non-fraud", action="store_true", help="Include benign SCC/cycle candidates in JSONL instead of filtering to fraud only")
    parser.add_argument("--dry-run", action="store_true", help="Print GDS query plan without connecting to Neo4j")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        print(json.dumps(GDSCycleDetector.dry_run_queries(), indent=2))
        return

    detector = GDSCycleDetector(args.uri, args.user, args.password, database=args.database)
    try:
        summary = detector.run(
            limit=args.limit,
            keep_projection=args.keep_projection,
            min_component_size=args.min_component_size,
            max_component_size=args.max_component_size,
            algorithms=args.algorithms,
            projection_scope=args.projection_scope,
        )
        print_research_output(summary)
        if args.json_out:
            output_dir = os.path.dirname(args.json_out)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            print(f"\nSaved JSON summary to: {args.json_out}")
        if args.jsonl_out:
            rings = save_cycle_records_jsonl(
                args.jsonl_out,
                detector.last_results,
                ring_id_prefix="RING",
                ring_type="scc_candidate",
                source_approach=summary["approach"],
                include_instances=False,
                fraud_only=not args.include_non_fraud,
                min_fraud_score=args.min_fraud_score,
            )
            mode = "fraud-ring candidate" if not args.include_non_fraud else "SCC/cycle candidate"
            print(f"Saved {len(rings)} {mode} records to JSONL: {args.jsonl_out}")
    finally:
        detector.close()


if __name__ == "__main__":
    main()
