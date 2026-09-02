"""
Approach 1: Pure Cypher cycle detection on Neo4j.

This script implements the Cypher-only strategy described in
Cycle_Detection_Neo4j_Strategies.md:
- 3-node directed transfer cycles (triangles)
- 4-node directed cycles
- 5-node directed cycles

Output is printed as a research-friendly summary plus JSON so the result can be
copied directly into notes/reports.

Example:
    python src/cycle_detection/cypher_cycle_detection.py \
        --uri bolt://localhost:7687 --user neo4j --password password --limit 100

Environment variables are also supported:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

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


@dataclass(frozen=True)
class QuerySpec:
    name: str
    description: str
    cypher: str


class CypherCycleDetector:
    """Detect transfer cycles using only Cypher queries."""

    @staticmethod
    def query_with_optional_limit(query: str, limit: int) -> str:
        """Treat limit=0 as unlimited instead of Cypher's LIMIT 0."""
        if limit > 0:
            return query
        return "\n".join(line for line in query.splitlines() if "LIMIT $limit" not in line)

    TRIANGLE_QUERY = """
    MATCH (a:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(b:Account)
    MATCH (b)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(c:Account)
    MATCH (c)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a)
    WHERE a.account_id <> b.account_id
      AND a.account_id <> c.account_id
      AND b.account_id <> c.account_id
      AND a.account_id = reduce(min_id = a.account_id, id IN [b.account_id, c.account_id] | CASE WHEN id < min_id THEN id ELSE min_id END)
    WITH DISTINCT [a.account_id, b.account_id, c.account_id] AS participants,
         [a, b, c] AS account_nodes
    OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
    WHERE src.account_id IN participants
      AND dst.account_id IN participants
    WITH participants, account_nodes, collect(DISTINCT t) AS txs
    WITH participants, account_nodes, txs,
         size(txs) AS group_transactions,
         reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS group_total_amount,
         size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,
         size([account IN account_nodes WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count
    WHERE ($require_fraud_evidence = false OR fraud_transaction_count > 0 OR fraud_member_count > 0)
      AND group_transactions >= $min_internal_transactions
      AND group_total_amount >= $min_total_amount
    RETURN participants,
      3 AS cycle_size,
      group_total_amount AS total_amount,
      group_transactions,
      group_total_amount,
      fraud_transaction_count,
      fraud_member_count,
      reduce(risk_total = 0.0, account IN account_nodes | risk_total + coalesce(account.kyc_risk_score, 0.5)) / 3.0 AS avg_kyc_risk_score,
      true AS metrics_are_group_level,
      1 AS cycles
    ORDER BY fraud_transaction_count DESC, fraud_member_count DESC, group_total_amount DESC
    LIMIT $limit
    """

    UNION_FIXED_LENGTH_QUERY = """
    CALL {
      // 3-node account cycles via (:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)
      MATCH (a:Account)-[:SENT]->(t1:Transaction)-[:RECEIVED_BY]->(b:Account),
            (b)-[:SENT]->(t2:Transaction)-[:RECEIVED_BY]->(c:Account),
            (c)-[:SENT]->(t3:Transaction)-[:RECEIVED_BY]->(a)
      WHERE a.account_id < b.account_id AND b.account_id < c.account_id
      RETURN DISTINCT
        [a.account_id, b.account_id, c.account_id] AS participants,
        3 AS cycle_size,
        coalesce(t1.amount_usd, t1.amount, 0) + coalesce(t2.amount_usd, t2.amount, 0) + coalesce(t3.amount_usd, t3.amount, 0) AS total_amount,
        (coalesce(a.kyc_risk_score, 0.5) + coalesce(b.kyc_risk_score, 0.5) + coalesce(c.kyc_risk_score, 0.5)) / 3.0 AS avg_kyc_risk_score

      UNION

      // 4-node account cycles
      MATCH (a:Account)-[:SENT]->(t1:Transaction)-[:RECEIVED_BY]->(b:Account),
            (b)-[:SENT]->(t2:Transaction)-[:RECEIVED_BY]->(c:Account),
            (c)-[:SENT]->(t3:Transaction)-[:RECEIVED_BY]->(d:Account),
            (d)-[:SENT]->(t4:Transaction)-[:RECEIVED_BY]->(a)
      WHERE a.account_id < b.account_id
        AND b.account_id < c.account_id
        AND c.account_id < d.account_id
      RETURN DISTINCT
        [a.account_id, b.account_id, c.account_id, d.account_id] AS participants,
        4 AS cycle_size,
        coalesce(t1.amount_usd, t1.amount, 0) + coalesce(t2.amount_usd, t2.amount, 0) + coalesce(t3.amount_usd, t3.amount, 0) + coalesce(t4.amount_usd, t4.amount, 0) AS total_amount,
        (coalesce(a.kyc_risk_score, 0.5) + coalesce(b.kyc_risk_score, 0.5) + coalesce(c.kyc_risk_score, 0.5) + coalesce(d.kyc_risk_score, 0.5)) / 4.0 AS avg_kyc_risk_score

      UNION

      // 5-node account cycles
      MATCH (a:Account)-[:SENT]->(t1:Transaction)-[:RECEIVED_BY]->(b:Account),
            (b)-[:SENT]->(t2:Transaction)-[:RECEIVED_BY]->(c:Account),
            (c)-[:SENT]->(t3:Transaction)-[:RECEIVED_BY]->(d:Account),
            (d)-[:SENT]->(t4:Transaction)-[:RECEIVED_BY]->(e:Account),
            (e)-[:SENT]->(t5:Transaction)-[:RECEIVED_BY]->(a)
      WHERE a.account_id < b.account_id
        AND b.account_id < c.account_id
        AND c.account_id < d.account_id
        AND d.account_id < e.account_id
      RETURN DISTINCT
        [a.account_id, b.account_id, c.account_id, d.account_id, e.account_id] AS participants,
        5 AS cycle_size,
        coalesce(t1.amount_usd, t1.amount, 0) + coalesce(t2.amount_usd, t2.amount, 0) + coalesce(t3.amount_usd, t3.amount, 0) + coalesce(t4.amount_usd, t4.amount, 0) + coalesce(t5.amount_usd, t5.amount, 0) AS total_amount,
        (coalesce(a.kyc_risk_score, 0.5) + coalesce(b.kyc_risk_score, 0.5) + coalesce(c.kyc_risk_score, 0.5) + coalesce(d.kyc_risk_score, 0.5) + coalesce(e.kyc_risk_score, 0.5)) / 5.0 AS avg_kyc_risk_score
    }
    RETURN participants, cycle_size, total_amount, avg_kyc_risk_score
    ORDER BY cycle_size DESC, total_amount DESC
    LIMIT $limit
    """

    CYCLE_4_QUERY = """
    MATCH (a:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(b:Account)
    MATCH (b)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(c:Account)
    MATCH (c)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(d:Account)
    MATCH (d)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a)
    WHERE a.account_id <> b.account_id
      AND a.account_id <> c.account_id
      AND a.account_id <> d.account_id
      AND b.account_id <> c.account_id
      AND b.account_id <> d.account_id
      AND c.account_id <> d.account_id
      AND a.account_id = reduce(min_id = a.account_id, id IN [b.account_id, c.account_id, d.account_id] | CASE WHEN id < min_id THEN id ELSE min_id END)
    WITH DISTINCT [a.account_id, b.account_id, c.account_id, d.account_id] AS participants,
         [a, b, c, d] AS account_nodes
    OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
    WHERE src.account_id IN participants
      AND dst.account_id IN participants
    WITH participants, account_nodes, collect(DISTINCT t) AS txs
    WITH participants, account_nodes, txs,
         size(txs) AS group_transactions,
         reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS group_total_amount,
         size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,
         size([account IN account_nodes WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count
    WHERE ($require_fraud_evidence = false OR fraud_transaction_count > 0 OR fraud_member_count > 0)
      AND group_transactions >= $min_internal_transactions
      AND group_total_amount >= $min_total_amount
    RETURN participants,
      4 AS cycle_size,
      group_total_amount AS total_amount,
      group_transactions,
      group_total_amount,
      fraud_transaction_count,
      fraud_member_count,
      reduce(risk_total = 0.0, account IN account_nodes | risk_total + coalesce(account.kyc_risk_score, 0.5)) / 4.0 AS avg_kyc_risk_score,
      true AS metrics_are_group_level,
      1 AS cycles
    ORDER BY fraud_transaction_count DESC, fraud_member_count DESC, group_total_amount DESC
    LIMIT $limit
    """

    CYCLE_5_QUERY = """
    MATCH (a:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(b:Account)
    MATCH (b)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(c:Account)
    MATCH (c)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(d:Account)
    MATCH (d)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(e:Account)
    MATCH (e)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(a)
    WHERE a.account_id <> b.account_id
      AND a.account_id <> c.account_id
      AND a.account_id <> d.account_id
      AND a.account_id <> e.account_id
      AND b.account_id <> c.account_id
      AND b.account_id <> d.account_id
      AND b.account_id <> e.account_id
      AND c.account_id <> d.account_id
      AND c.account_id <> e.account_id
      AND d.account_id <> e.account_id
      AND a.account_id = reduce(min_id = a.account_id, id IN [b.account_id, c.account_id, d.account_id, e.account_id] | CASE WHEN id < min_id THEN id ELSE min_id END)
    WITH DISTINCT [a.account_id, b.account_id, c.account_id, d.account_id, e.account_id] AS participants,
         [a, b, c, d, e] AS account_nodes
    OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
    WHERE src.account_id IN participants
      AND dst.account_id IN participants
    WITH participants, account_nodes, collect(DISTINCT t) AS txs
    WITH participants, account_nodes, txs,
         size(txs) AS group_transactions,
         reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS group_total_amount,
         size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,
         size([account IN account_nodes WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count
    WHERE ($require_fraud_evidence = false OR fraud_transaction_count > 0 OR fraud_member_count > 0)
      AND group_transactions >= $min_internal_transactions
      AND group_total_amount >= $min_total_amount
    RETURN participants,
      5 AS cycle_size,
      group_total_amount AS total_amount,
      group_transactions,
      group_total_amount,
      fraud_transaction_count,
      fraud_member_count,
      reduce(risk_total = 0.0, account IN account_nodes | risk_total + coalesce(account.kyc_risk_score, 0.5)) / 5.0 AS avg_kyc_risk_score,
      true AS metrics_are_group_level,
      1 AS cycles
    ORDER BY fraud_transaction_count DESC, fraud_member_count DESC, group_total_amount DESC
    LIMIT $limit
    """

    FIXED_LENGTH_QUERIES = {
        3: TRIANGLE_QUERY,
        4: CYCLE_4_QUERY,
        5: CYCLE_5_QUERY,
    }

    @staticmethod
    def build_fraud_anchored_cycle_query(cycle_size: int) -> str:
        """Build a memory-bounded fixed-length query anchored on fraud accounts.

        The unanchored 3/4/5 fixed queries are useful on small/medium graphs,
        but on million-node graphs Neo4j may enumerate too many path
        combinations before LIMIT applies and hit dbms.memory.transaction limits.
        This query starts only from accounts already marked with generated fraud
        evidence (`fraud_ring_member=true`) and expands one bounded cycle length.
        It intentionally supports size 6 too because genCycle can emit 6-account
        rings.
        """
        if cycle_size < 3:
            raise ValueError("cycle_size must be >= 3")

        account_vars = [f"a{i}" for i in range(cycle_size)]
        match_lines = [
            "    MATCH (a0:Account)",
            "    WHERE a0.fraud_ring_member = true",
            "    WITH a0 ORDER BY a0.account_id LIMIT $anchor_limit",
        ]
        for index in range(cycle_size):
            source = account_vars[index]
            target = account_vars[(index + 1) % cycle_size]
            match_lines.append(
                f"    MATCH ({source})-[:SENT]->(t{index}:Transaction)-[:RECEIVED_BY]->({target}:Account)"
            )

        distinct_checks = []
        for left in range(cycle_size):
            for right in range(left + 1, cycle_size):
                distinct_checks.append(f"a{left}.account_id <> a{right}.account_id")

        participants = ", ".join(f"a{index}.account_id" for index in range(cycle_size))
        nodes = ", ".join(account_vars)
        min_reduce_ids = ", ".join(f"a{index}.account_id" for index in range(1, cycle_size))

        return "\n".join(
            match_lines
            + [
                "    WHERE " + "\n      AND ".join(distinct_checks),
                f"      AND a0.account_id = reduce(min_id = a0.account_id, id IN [{min_reduce_ids}] | CASE WHEN id < min_id THEN id ELSE min_id END)",
                f"    WITH DISTINCT [{participants}] AS participants,",
                f"         [{nodes}] AS account_nodes",
                "    OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)",
                "    WHERE src.account_id IN participants",
                "      AND dst.account_id IN participants",
                "    WITH participants, account_nodes, collect(DISTINCT t) AS txs",
                "    WITH participants, account_nodes, txs,",
                "         size(txs) AS group_transactions,",
                "         reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0.0)) AS group_total_amount,",
                "         size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,",
                "         size([account IN account_nodes WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count",
                "    WHERE ($require_fraud_evidence = false OR fraud_transaction_count > 0 OR fraud_member_count > 0)",
                "      AND group_transactions >= $min_internal_transactions",
                "      AND group_total_amount >= $min_total_amount",
                "    RETURN participants,",
                f"      {cycle_size} AS cycle_size,",
                "      group_total_amount AS total_amount,",
                "      group_transactions,",
                "      group_total_amount,",
                "      fraud_transaction_count,",
                "      fraud_member_count,",
                f"      reduce(risk_total = 0.0, account IN account_nodes | risk_total + coalesce(account.kyc_risk_score, 0.5)) / {float(cycle_size):.1f} AS avg_kyc_risk_score,",
                "      true AS metrics_are_group_level,",
                "      1 AS cycles",
                "    ORDER BY fraud_transaction_count DESC, fraud_member_count DESC, group_total_amount DESC",
                "    LIMIT $limit",
            ]
        )

    FRAUD_ANCHORED_CYCLE_SIZES = (3, 4, 5, 6)

    VARIABLE_LENGTH_QUERY = """
    MATCH path = (start:Account)-[:SENT|RECEIVED_BY*6..16]->(start)
    WHERE length(path) % 2 = 0
      AND all(i IN range(0, length(path) - 1) WHERE
        (i % 2 = 0 AND type(relationships(path)[i]) = 'SENT') OR
        (i % 2 = 1 AND type(relationships(path)[i]) = 'RECEIVED_BY')
      )
    WITH [n IN nodes(path) WHERE n:Account | n.account_id] AS participants,
         [n IN nodes(path) WHERE n:Account | n] AS account_nodes,
         [n IN nodes(path) WHERE n:Transaction | n] AS tx_nodes,
         length(path) / 2 AS cycle_size
    WHERE cycle_size >= 3 AND cycle_size <= 8
      AND size(apoc.coll.toSet(participants[0..cycle_size])) = cycle_size
    RETURN participants[0..cycle_size] AS participants,
           cycle_size,
           reduce(total = 0, t IN tx_nodes | total + coalesce(t.amount_usd, t.amount, 0)) AS total_amount,
           reduce(risk_total = 0.0, account_id IN participants[0..cycle_size] |
             risk_total + coalesce(head([n IN account_nodes WHERE n.account_id = account_id | n.kyc_risk_score]), 0.5)
           ) / cycle_size AS avg_kyc_risk_score
    ORDER BY cycle_size DESC, total_amount DESC
    LIMIT $limit
    """

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

    def find_triangles(
        self,
        limit: int = 100,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        return self._run_query(
            self.TRIANGLE_QUERY,
            limit,
            require_fraud_evidence=require_fraud_evidence,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
        )

    def find_fixed_length_cycles(
        self,
        limit: int = 500,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Run 3-, 4-, and 5-account cycle queries independently.

        The old UNION query sorted by cycle_size DESC before applying LIMIT,
        so when many 5-account cycles existed the final output contained only
        participant_count=5. Running a bounded query per size prevents that
        size-5 limit bias and keeps smaller rings visible.
        """
        results: List[Dict[str, Any]] = []
        for cycle_size in sorted(self.FIXED_LENGTH_QUERIES):
            size_results = self._run_query(
                self.FIXED_LENGTH_QUERIES[cycle_size],
                limit,
                require_fraud_evidence=require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
            )
            for item in size_results:
                item["candidate_cycle_size"] = cycle_size
            results.extend(size_results)
        results.sort(key=lambda item: (item.get("cycle_size", 0), item.get("total_amount", 0)), reverse=True)
        return results

    def find_fraud_anchored_cycles(
        self,
        limit: int = 500,
        anchor_limit: int = 10000,
        require_fraud_evidence: bool = True,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Run fixed cycle queries from fraud-labeled account anchors only.

        Use this mode for large graphs when unanchored Cypher expansion hits
        Neo4j transaction memory. It is label-preserving/evaluation mode: if all
        fraud labels are hidden/defaulted, this mode will intentionally return no
        anchors.
        """
        results: List[Dict[str, Any]] = []
        for cycle_size in self.FRAUD_ANCHORED_CYCLE_SIZES:
            size_results = self._run_query(
                self.build_fraud_anchored_cycle_query(cycle_size),
                limit,
                require_fraud_evidence=require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
                anchor_limit=anchor_limit,
            )
            for item in size_results:
                item["candidate_cycle_size"] = cycle_size
            results.extend(size_results)
        results.sort(
            key=lambda item: (
                item.get("fraud_transaction_count", 0),
                item.get("fraud_member_count", 0),
                item.get("cycle_size", 0),
                item.get("total_amount", 0),
            ),
            reverse=True,
        )
        return results

    @staticmethod
    def merge_overlapping_cycle_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge fragmented cycle rows into component-level ring candidates.

        Ground truth defines one fraud ring as one strongly connected account
        group. Fixed-length Cypher finds many 3/4/5-node sub-cycles inside the
        same group, which fragments one true ring into many predictions. This
        post-processing step treats cycle rows sharing at least one participant
        as evidence for the same component and returns one record per merged
        participant set.
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
            component_records.append(
                {
                    "component_id": f"CYPHER_COMPONENT_{component_index:04d}",
                    "participants": participants,
                    "cycle_size": len(participants),
                    "candidate_cycle_sizes": cycle_sizes,
                    "cycles": sum(int(record.get("cycles") or 1) for record in source_records),
                    "method": "pure_cypher_component_merge",
                    "fragment_count": len(source_records),
                }
            )

        component_records.sort(key=lambda item: (len(item["participants"]), item["cycles"]), reverse=True)
        return component_records

    def find_component_rings(
        self,
        limit: int = 500,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return component-level ring candidates from fixed Cypher cycles.

        This is the optimized/fair Cypher approach for comparison with GDS SCC:
        enumerate bounded explicit cycles, then merge overlapping sub-cycles
        before scoring/exporting so one fraud ring becomes one JSONL record.
        """

        cycle_rows = self.find_fixed_length_cycles(
            limit=limit,
            require_fraud_evidence=require_fraud_evidence,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
        )
        return self.merge_overlapping_cycle_records(cycle_rows)

    def find_fraud_anchored_component_rings(
        self,
        limit: int = 500,
        anchor_limit: int = 10000,
        require_fraud_evidence: bool = True,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
    ) -> List[Dict[str, Any]]:
        cycle_rows = self.find_fraud_anchored_cycles(
            limit=limit,
            anchor_limit=anchor_limit,
            require_fraud_evidence=require_fraud_evidence,
            min_internal_transactions=min_internal_transactions,
            min_total_amount=min_total_amount,
        )
        return self.merge_overlapping_cycle_records(cycle_rows)

    def find_variable_length_cycles_apoc(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Run variable length query. Requires APOC because it uses apoc.coll.toSet."""
        return self._run_query(self.VARIABLE_LENGTH_QUERY, limit)

    def _run_query(
        self,
        query: str,
        limit: int,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
        anchor_limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(
                self.query_with_optional_limit(query, limit),
                limit=limit,
                require_fraud_evidence=bool(require_fraud_evidence),
                min_internal_transactions=int(min_internal_transactions),
                min_total_amount=float(min_total_amount),
                anchor_limit=int(anchor_limit),
            )
            return [self._normalize_record(dict(record)) for record in result]

    @staticmethod
    def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(record)
        if "total_amount" in normalized and normalized["total_amount"] is not None:
            normalized["total_amount"] = float(normalized["total_amount"])
        return normalized

    def add_group_metrics_to_cycle_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add exact account-group transaction metrics for JSONL aggregation.

        A Cypher cycle row represents one transaction-path combination. If the
        same participant set has many parallel transactions, summing every path
        combination inflates transaction_count and total_amount. These group
        metrics count distinct Transaction nodes inside the participant set once.
        """
        if not records:
            return records

        cache: Dict[tuple, Dict[str, Any]] = {}
        with self._session() as session:
            for record in records:
                if record.get("metrics_are_group_level") and "group_transactions" in record and "group_total_amount" in record:
                    continue
                participants = tuple(sorted(str(item) for item in (record.get("participants") or []) if item is not None))
                if not participants:
                    continue
                if participants not in cache:
                    metrics = session.run(
                        """
                        MATCH (account:Account)
                        WHERE account.account_id IN $participants
                        WITH collect(account) AS accounts
                        OPTIONAL MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
                        WHERE src.account_id IN $participants
                          AND dst.account_id IN $participants
                        WITH accounts, collect(DISTINCT t) AS txs
                        RETURN size(txs) AS transactions,
                               reduce(total = 0.0, tx IN txs | total + coalesce(tx.amount_usd, tx.amount, 0)) AS total_amount,
                               size([tx IN txs WHERE coalesce(tx.is_fraud, 0) = 1]) AS fraud_transaction_count,
                               size([account IN accounts WHERE coalesce(account.fraud_ring_member, false) = true]) AS fraud_member_count,
                               reduce(risk_total = 0.0, account IN accounts | risk_total + coalesce(account.kyc_risk_score, 0.5)) / size(accounts) AS avg_source_risk
                        """,
                        participants=list(participants),
                    ).single()
                    cache[participants] = {
                        "group_transactions": int(metrics["transactions"] or 0) if metrics else 0,
                        "group_total_amount": float(metrics["total_amount"] or 0.0) if metrics else 0.0,
                        "fraud_transaction_count": int(metrics["fraud_transaction_count"] or 0) if metrics else 0,
                        "fraud_member_count": int(metrics["fraud_member_count"] or 0) if metrics else 0,
                        "avg_kyc_risk_score": float(metrics["avg_source_risk"] or 0.5) if metrics else record.get("avg_kyc_risk_score", 0.5),
                    }
                record.update(cache[participants])
                record["metrics_are_group_level"] = True
        return records

    @staticmethod
    def build_research_summary(
        approach: str,
        graph_stats: Dict[str, Any],
        result_count: int,
        elapsed_ms: float,
        sample_results: Iterable[Dict[str, Any]],
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "approach": approach,
            "graph_stats": graph_stats,
            "result_count": result_count,
            "elapsed_ms": round(elapsed_ms, 3),
            "sample_results": list(sample_results),
            "notes": notes or [],
        }

    def run(
        self,
        mode: str = "fixed",
        limit: int = 500,
        require_fraud_evidence: bool = False,
        min_internal_transactions: int = 0,
        min_total_amount: float = 0.0,
        anchor_limit: int = 10000,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        graph_stats = self.get_graph_stats()

        if mode == "triangles":
            results = self.find_triangles(
                limit=limit,
                require_fraud_evidence=require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
            )
            notes = ["Pure Cypher directed 3-node account-cycle query over distinct account edges."]
        elif mode == "component":
            results = self.find_component_rings(
                limit=limit,
                require_fraud_evidence=require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
            )
            notes = [
                "Optimized Cypher mode: fixed 3/4/5 cycle rows are merged into component-level ring candidates before scoring/export.",
                "This aligns Cypher output granularity with GDS SCC and ground truth, reducing one-ring-to-many-cycle fragmentation.",
            ]
        elif mode == "anchored":
            results = self.find_fraud_anchored_component_rings(
                limit=limit,
                anchor_limit=anchor_limit,
                require_fraud_evidence=True if not require_fraud_evidence else require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
            )
            notes = [
                "Memory-bounded Cypher mode: starts from Account.fraud_ring_member=true anchors, then expands explicit 3/4/5/6 cycles.",
                "Use this on million-node graphs when unanchored component/fixed mode hits Neo4j transaction memory limits.",
                f"Fraud anchor limit: {anchor_limit} accounts.",
            ]
        elif mode == "variable":
            results = self.find_variable_length_cycles_apoc(limit=limit)
            notes = [
                "Variable-length 3..8 cycles.",
                "Requires APOC and can be slow on large graphs; use for exploration only.",
            ]
        else:
            results = self.find_fixed_length_cycles(
                limit=limit,
                require_fraud_evidence=require_fraud_evidence,
                min_internal_transactions=min_internal_transactions,
                min_total_amount=min_total_amount,
            )
            notes = [
                "Legacy Cypher mode: explicit 3/4/5-node account-cycle patterns over distinct account edges.",
                "Group-level metrics are computed inside Cypher so parallel transactions do not create path-combination inflation.",
            ]
        if require_fraud_evidence:
            notes.append("Filtered to candidates with generated fraud evidence: fraud transaction or fraud_ring_member account property.")
        if min_internal_transactions:
            notes.append(f"Filtered to at least {min_internal_transactions} internal transactions per candidate group.")
        if min_total_amount:
            notes.append(f"Filtered to total internal amount >= {min_total_amount}.")

        self.last_results = self.add_group_metrics_to_cycle_records(results)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return self.build_research_summary(
            approach=f"pure_cypher_{mode}",
            graph_stats=graph_stats,
            result_count=len(results),
            elapsed_ms=elapsed_ms,
            sample_results=results[:10],
            notes=notes,
        )

    @staticmethod
    def dry_run_queries() -> List[QuerySpec]:
        specs = [
            QuerySpec(
                "component",
                "default optimized mode: run fixed 3/4/5 cycle queries, then merge overlapping participant sets into component-level rings",
                "POST-PROCESS fixed_3/fixed_4/fixed_5 results with merge_overlapping_cycle_records(...)",
            ),
            QuerySpec(
                "anchored",
                "memory-bounded mode: expand 3/4/5/6 cycles only from Account.fraud_ring_member=true anchors",
                CypherCycleDetector.build_fraud_anchored_cycle_query(3),
            ),
            QuerySpec("triangles", "3-node directed cycles", CypherCycleDetector.TRIANGLE_QUERY),
        ]
        specs.extend(
            QuerySpec(f"fixed_{size}", f"{size}-node directed cycles used by fixed mode", query)
            for size, query in CypherCycleDetector.FIXED_LENGTH_QUERIES.items()
        )
        specs.append(QuerySpec("variable", "APOC-assisted variable length cycles 3..8", CypherCycleDetector.VARIABLE_LENGTH_QUERY))
        return specs


def print_research_output(summary: Dict[str, Any]) -> None:
    print("=" * 78)
    print("APPROACH 1 - PURE CYPHER CYCLE DETECTION")
    print("=" * 78)
    print(f"Approach        : {summary['approach']}")
    print(f"Nodes / Edges   : {summary['graph_stats'].get('nodes', 0)} / {summary['graph_stats'].get('edges', 0)}")
    print(f"Cycles returned : {summary['result_count']}")
    print(f"Runtime         : {summary['elapsed_ms']} ms")
    print("Notes:")
    for note in summary.get("notes", []):
        print(f"  - {note}")
    print("\nTop sample results:")
    for idx, item in enumerate(summary.get("sample_results", []), start=1):
        print(f"  {idx:02d}. size={item.get('cycle_size')} amount={item.get('total_amount')} participants={item.get('participants')}")
    print("\nJSON_RESULT:")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure Cypher cycle detection for Neo4j Account-Transaction-Account graph")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name (Aura normally uses neo4j)")
    parser.add_argument("--mode", choices=["anchored", "component", "fixed", "triangles", "variable"], default="component")
    parser.add_argument("--limit", type=int, default=500, help="Maximum rows per cycle size; use 0 for unlimited (can be expensive)")
    parser.add_argument("--anchor-limit", type=int, default=10000, help="Maximum fraud-labeled Account anchors to expand in --mode anchored")
    parser.add_argument("--json-out", default=None, help="Optional path to save summary JSON")
    parser.add_argument(
        "--jsonl-out",
        default=None,
        help="Optional path to save full detected fraud rings as JSONL, one ground-truth-like ring per line",
    )
    parser.add_argument("--min-fraud-score", type=float, default=0.35, help="Minimum heuristic fraud score for JSONL fraud-ring output")
    parser.add_argument(
        "--require-fraud-evidence",
        action="store_true",
        help="Filter Cypher candidates to account groups with at least one generated fraud transaction or fraud_ring_member account property",
    )
    parser.add_argument("--min-internal-transactions", type=int, default=0, help="Minimum distinct internal transactions inside a candidate account group")
    parser.add_argument("--min-total-amount", type=float, default=0.0, help="Minimum total distinct internal transaction amount inside a candidate account group")
    parser.add_argument("--include-non-fraud", action="store_true", help="Include benign cycle rings in JSONL instead of filtering to fraud only")
    parser.add_argument("--dry-run", action="store_true", help="Print Cypher queries without connecting to Neo4j")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        for spec in CypherCycleDetector.dry_run_queries():
            print(f"\n--- {spec.name}: {spec.description} ---")
            print(spec.cypher.strip())
        return

    detector = CypherCycleDetector(args.uri, args.user, args.password, database=args.database)
    try:
        summary = detector.run(
            mode=args.mode,
            limit=args.limit,
            require_fraud_evidence=args.require_fraud_evidence,
            min_internal_transactions=args.min_internal_transactions,
            min_total_amount=args.min_total_amount,
            anchor_limit=args.anchor_limit,
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
