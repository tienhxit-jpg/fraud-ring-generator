# Fraud Ring Detection - Cycle Detection Approaches

This repository contains three different approaches to detect fraud rings (cycles) in Neo4j graphs as described in the `Cycle_Detection_Neo4j_Strategies.md` document.

## Approaches Implemented

### 1. Cypher-Based Approach (`src/cypher_approach.py`)
Pure Cypher queries for cycle detection:
- 3-node cycle detection (triangles)
- Variable-length cycle detection (3-8 nodes)
- Union-pattern approach for specific cycle sizes

**Best for**: Small to medium graphs (<100k nodes), simple cycle patterns

### 2. Neo4j GDS Approach (`src/gds_approach.py`)
Uses Neo4j Graph Data Science library:
- Strongly Connected Components (SCC) for cycle detection
- Louvain community detection
- Triangle counting
- Betweenness centrality for identifying key nodes

**Best for**: Large graphs, production environments, real-time analytics

### 3. Hybrid Approach (`src/hybrid_approach.py`)
Combines Neo4j GDS and NetworkX:
- Fast initial filtering with GDS SCC
- Detailed cycle analysis with NetworkX
- Custom scoring algorithms
- Results saved back to Neo4j as FraudRing nodes

**Best for**: Complex analysis, custom algorithms, combining multiple methods

## Requirements

- Python 3.7+
- Neo4j database with appropriate plugins (APOC for Cypher approach, GDS for GDS/Hybrid approaches)
- Python packages:
  - neo4j
  - networkx
  - pandas
  - numpy

Install requirements with:
```bash
pip install neo4j networkx pandas numpy
```

## Usage

Before running any script, ensure your Neo4j database is running and accessible. Update the connection details in each script:

```python
detector = CypherCycleDetector("bolt://localhost:7687", "neo4j", "password")
```

Run each approach:

```bash
python src/cypher_approach.py
python src/gds_approach.py
python src/hybrid_approach.py
```

## Expected Output

Each script will:
1. Connect to Neo4j
2. Execute the respective cycle detection approach
3. Measure performance
4. Display results summary
5. Show sample detected cycles/rings

The Hybrid approach additionally:
1. Saves detected rings to Neo4j as FraudRing nodes
2. Creates MEMBER_OF relationships between Accounts and FraudRings

## Performance Comparison

Based on the analysis in the original document:

| Method | Time (800 nodes) | Time (10k nodes) | Scalability |
|--------|------------------|------------------|-------------|
| Cypher (4-cycles) | 2-5 sec | 30+ sec | Poor |
| Cypher (Union) | 1-2 sec | 10-20 sec | Fair |
| GDS (SCC) | 100ms | 500ms | Excellent |
| GDS (Louvain) | 150ms | 800ms | Excellent |
| GDS (Triangles) | 50ms | 300ms | Excellent |
| NetworkX (Pull) | 500ms | Timeout | Poor |

## Notes

- The scripts assume your Neo4j database has Account nodes with account_id properties and TRANSFER relationships
- Additional properties like kyc_risk_score and monthly_transaction_count are used in scoring but are optional
- The Hybrid approach creates new FraudRing nodes and MEMBER_OF relationships in your database