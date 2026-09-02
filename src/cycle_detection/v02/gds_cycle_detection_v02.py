"""Label-blind Neo4j GDS SCC detector v02.

The detector projects every logical Account-to-Account transfer pair, runs SCC,
applies only component-size filters, enriches candidates with transaction amount
and topology metrics, and exports every candidate without answer-key scoring.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

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


class GDSCycleDetectorV02:
    """Detect bounded SCC candidates without reading answer-key properties."""

    GRAPH_NAME = "cycle_gds_v02_directed"

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        database: Optional[str] = None,
        driver: Any = None,
        logger=progress_log,
    ) -> None:
        self.driver = driver or GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.logger = logger
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
    def node_projection_query() -> str:
        return "MATCH (a:Account) RETURN id(a) AS id"

    @staticmethod
    def relationship_projection_query() -> str:
        return """
        MATCH (src:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(dst:Account)
        WITH DISTINCT src, dst
        RETURN id(src) AS source, id(dst) AS target
        """

    @staticmethod
    def scc_query(limit: int) -> str:
        limit_clause = "LIMIT $limit" if limit > 0 else ""
        return f"""
        CALL gds.scc.stream($graph_name)
        YIELD nodeId, componentId
        WITH componentId, collect(gds.util.asNode(nodeId).account_id) AS participants
        WHERE size(participants) >= $min_size
          AND size(participants) <= $max_size
        RETURN componentId,
               participants,
               size(participants) AS participant_count
        ORDER BY participant_count DESC, componentId
        {limit_clause}
        """

    @staticmethod
    def enrichment_query() -> str:
        return """
        UNWIND $groups AS group
        WITH group.idx AS idx, group.participants AS participants
        OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
        WHERE src.account_id IN participants
          AND dst.account_id IN participants
        WITH idx, participants,
             collect(DISTINCT t) AS txs,
             collect(DISTINCT [src.account_id, dst.account_id]) AS directed_edges
        RETURN idx,
               size(txs) AS transactions,
               reduce(total = 0.0, tx IN txs |
                   total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS total_amount,
               CASE WHEN size(participants) <= 1 THEN 0.0
                    ELSE toFloat(size([
                        edge IN directed_edges
                        WHERE edge[0] IS NOT NULL AND edge[1] IS NOT NULL
                    ])) / toFloat(size(participants) * (size(participants) - 1))
               END AS density
        """

    @staticmethod
    def interpret_version_error(message: str) -> Dict[str, Any]:
        if "versionless" in message.lower():
            return {"available": True, "version": "versionless"}
        return {"available": False, "version": None, "error": message}

    def verify_gds(self) -> Dict[str, Any]:
        with self._session() as session:
            try:
                record = session.run("RETURN gds.version() AS version").single()
                result = {
                    "available": bool(record and record["version"]),
                    "version": record["version"] if record else None,
                }
            except Neo4jError as exc:
                result = self.interpret_version_error(str(exc))
            procedure = session.run(
                """
                SHOW PROCEDURES YIELD name
                WHERE name = 'gds.graph.project.cypher'
                RETURN count(*) AS available
                """
            ).single()
        if not procedure or int(procedure["available"] or 0) == 0:
            result.update(
                {
                    "available": False,
                    "error": "Required procedure gds.graph.project.cypher is not installed in this database.",
                }
            )
        return result

    def graph_stats(self) -> Dict[str, int]:
        with self._session() as session:
            record = session.run(
                """
                MATCH (a:Account)
                WITH count(a) AS accounts
                OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
                RETURN accounts,
                       count(DISTINCT t) AS transactions,
                       count(DISTINCT [src.account_id, dst.account_id]) AS logical_pairs
                """
            ).single()
        return {
            "accounts": int(record["accounts"] or 0) if record else 0,
            "transactions": int(record["transactions"] or 0) if record else 0,
            "logical_pairs": int(record["logical_pairs"] or 0) if record else 0,
        }

    def drop_projection(self, graph_name: str = GRAPH_NAME) -> None:
        with self._session() as session:
            try:
                session.run(
                    "CALL gds.graph.drop($graph_name) YIELD graphName RETURN graphName",
                    graph_name=graph_name,
                ).consume()
            except Neo4jError:
                # Aura may reject gds.graph.exists without Aura API credentials;
                # an absent graph is safe to ignore during cleanup.
                pass

    def project_graph(self, graph_name: str = GRAPH_NAME) -> Dict[str, Any]:
        self.drop_projection(graph_name)
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
                node_query=self.node_projection_query(),
                relationship_query=self.relationship_projection_query(),
            ).single()
        return dict(record) if record else {}

    def run_scc(
        self,
        graph_name: str,
        min_size: int,
        max_size: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        with self._session() as session:
            records = session.run(
                self.scc_query(limit),
                graph_name=graph_name,
                min_size=min_size,
                max_size=max_size,
                limit=limit,
            )
            return [
                {
                    "component_id": record["componentId"],
                    "participants": sorted(record["participants"] or []),
                    "participant_count": int(record["participant_count"] or 0),
                    "cycle_size": int(record["participant_count"] or 0),
                    "method": "gds_scc_v02",
                }
                for record in records
            ]

    def enrich(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not groups:
            return groups
        payload = [
            {"idx": index, "participants": group["participants"]}
            for index, group in enumerate(groups)
        ]
        with self._session() as session:
            records = session.run(self.enrichment_query(), groups=payload)
            metrics = {int(record["idx"]): dict(record) for record in records}
        for index, group in enumerate(groups):
            row = metrics.get(index, {})
            group["transactions"] = int(row.get("transactions") or 0)
            group["total_amount"] = float(row.get("total_amount") or 0.0)
            group["density"] = float(row.get("density") or 0.0)
            group["cycles"] = 1
            group["metrics_are_group_level"] = True
        return groups

    def run(
        self,
        min_component_size: int = 3,
        max_component_size: int = 12,
        limit: int = 0,
        keep_projection: bool = False,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        self._log("GDS v02 detection started")
        try:
            gds = self.verify_gds()
            if not gds.get("available"):
                raise RuntimeError(f"GDS is unavailable: {gds.get('error')}")
            stats = self.graph_stats()
            self._log(
                f"source graph: accounts={stats['accounts']}, logical_pairs={stats['logical_pairs']}"
            )
            projection = self.project_graph(self.GRAPH_NAME)
            self._log(
                f"projection ready: nodes={projection.get('nodeCount', 0)}, "
                f"relationships={projection.get('relationshipCount', 0)}"
            )
            groups = self.run_scc(
                self.GRAPH_NAME,
                min_component_size,
                max_component_size,
                limit,
            )
            self._log(f"SCC filtering finished: candidates={len(groups)}")
            self.last_results = self.enrich(groups)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            self._log(f"GDS v02 detection finished ({elapsed_ms / 1000:.2f}s)")
            return {
                "approach": "neo4j_gds_scc_v02_label_blind",
                "parameters": {
                    "min_component_size": min_component_size,
                    "max_component_size": max_component_size,
                    "limit": limit,
                },
                "gds": gds,
                "graph_stats": stats,
                "projection": projection,
                "result_count": len(self.last_results),
                "elapsed_ms": elapsed_ms,
                "sample_results": self.last_results[:10],
            }
        finally:
            if not keep_projection:
                try:
                    self.drop_projection(self.GRAPH_NAME)
                except Exception:
                    pass

    @classmethod
    def dry_run_queries(cls) -> Dict[str, str]:
        return {
            "node_projection": cls.node_projection_query(),
            "relationship_projection": cls.relationship_projection_query(),
            "scc": cls.scc_query(limit=0),
            "enrichment": cls.enrichment_query(),
        }


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_jsonl(path: str | Path, groups: Iterable[Mapping[str, Any]]) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for count, group in enumerate(groups, 1):
            record = dict(group)
            record.setdefault("ring_id", f"GDS_{count - 1:04d}")
            record.setdefault("ring_type", "scc_candidate")
            record.setdefault("pattern", "strongly_connected_component")
            record.setdefault("source_approach", "neo4j_gds_scc_v02_label_blind")
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label-blind Neo4j GDS SCC detector v02")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--limit", type=int, default=0, help="0 returns all bounded SCC candidates")
    parser.add_argument("--min-component-size", type=int, default=3)
    parser.add_argument("--max-component-size", type=int, default=12)
    parser.add_argument("--keep-projection", action="store_true")
    parser.add_argument("--json-out", default="data/cycledetection/gds_v02/summary.json")
    parser.add_argument("--jsonl-out", default="data/cycledetection/gds_v02/candidates.jsonl")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        print(json.dumps(GDSCycleDetectorV02.dry_run_queries(), ensure_ascii=False, indent=2))
        return
    detector = GDSCycleDetectorV02(
        args.uri,
        args.user,
        args.password,
        database=args.database,
        logger=None if args.quiet else progress_log,
    )
    try:
        summary = detector.run(
            min_component_size=args.min_component_size,
            max_component_size=args.max_component_size,
            limit=args.limit,
            keep_projection=args.keep_projection,
        )
        write_json(args.json_out, summary)
        count = write_jsonl(args.jsonl_out, detector.last_results)
        summary["jsonl_count"] = count
        write_json(args.json_out, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    finally:
        detector.close()


if __name__ == "__main__":
    main()
