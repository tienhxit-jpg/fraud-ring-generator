# Fraud Ring Generator & Cycle Detection

Synthetic data generator for fraud ring detection with multiple cycle detection approaches for Neo4j graphs.

## Project Structure

```
fraud-ring-generator/
├── README.md
└── src/
    ├── generators/v03/          # Synthetic data generator
    └── cycle_detection/v02/     # Cycle detection algorithms
```

## Generators (`src/generators/v03/`)

Generates synthetic fraud ring datasets with configurable parameters.

### Features

- Configurable number of normal accounts, fraudsters, and rings
- Supports 3-person, 5-person, and 8-person fraud rings
- Generates background transactions with bridge connections
- Reproducible data generation with seed control

### Usage

```bash
python src/generators/v03/data_generator.py
```

### Configuration

Edit `config_d3.yaml` or `config_academic.yaml` to customize:

```yaml
synthetic_data:
  accounts:
    normal_account_count: 5000
  fraud_rings:
    ring_distribution:
      small_rings_3person: 15
      medium_rings_5person: 15
      large_rings_8person: 15
```

### Output

- `accounts.csv` - Account data
- `transactions.csv` - Transaction data
- `merchants.csv` - Merchant data
- `fraud_rings.json` - Ground truth ring definitions

---

## Cycle Detection (`src/cycle_detection/v02/`)

Multiple approaches to detect fraud rings (cycles) in Neo4j graphs.

### Approaches

| Approach | File | Best For |
|----------|------|----------|
| **GDS SCC** | `gds_cycle_detection_v02.py` | Large graphs, production |
| **Cypher** | `cypher_cycle_detection_v02.py` | Small-medium graphs |
| **Hybrid** | `hybrid_networkx_cycle_detection_v02.py` | Complex analysis |

### GDS SCC Detection

```bash
python src/cycle_detection/v02/gds_cycle_detection_v02.py \
  --min-component-size 3 \
  --max-component-size 12 \
  --json-out results/summary.json \
  --jsonl-out results/candidates.jsonl
```

### Cypher Detection

```bash
python src/cycle_detection/v02/cypher_cycle_detection_v02.py \
  --cycle-sizes 3,5,8 \
  --limit 0 \
  --json-out results/summary.json
```

### Hybrid Detection

```bash
python src/cycle_detection/v02/hybrid_networkx_cycle_detection_v02.py \
  --cycle-sizes 3,5,8 \
  --json-out results/summary.json
```

## Requirements

- Python 3.7+
- Neo4j with GDS plugin
- Python packages: `neo4j`, `networkx`, `pandas`, `numpy`, `pyyaml`

```bash
pip install neo4j networkx pandas numpy pyyaml
```

## Neo4j Connection

Update connection in scripts or set environment:

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
```
