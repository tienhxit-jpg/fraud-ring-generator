# Fraud Ring Detection Synthetic Data Generator

This project generates synthetic data for academic research on fraud ring detection in digital banking.

## Overview

- **Project**: Fraud Ring Detection in Digital Banking
- **Purpose**: Generate realistic synthetic data for academic paper
- **Scale**: 50,000 transactions, 5,000 accounts, 45 fraud rings
- **Output**: CSV files for accounts and transactions, JSON for fraud ring ground truth

## Features

- Realistic account generation (normal customers and fraudsters)
- Merchant account simulation
- Three types of fraud rings (small, medium, large)
- Multiple fraud patterns (money laundering, account takeover, collusion, phishing)
- Realistic transaction patterns (amounts, timing, channels)
- Cross-border transaction simulation
- Data validation and quality checks

## Setup

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

#### On Unix/Linux/macOS:

```bash
chmod +x src/generators/v02/setup.sh
./src/generators/v02/setup.sh
```

#### On Windows:

```cmd
src/generators/v02/setup.bat
```

### Manual Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - On Unix/Linux/macOS: `source venv/bin/activate`
   - On Windows: `venv\Scripts\activate.bat`

3. Install dependencies:
   ```bash
   pip install -r src/generators/v02/requirements.txt
   ```

4. Create output directories:
   ```bash
   mkdir -p data/synthetic/{raw,processed,ground_truth}
   ```

## Usage

1. Activate the virtual environment:
   - On Unix/Linux/macOS: `source venv/bin/activate`
   - On Windows: `venv\Scripts\activate.bat`

2. Run the generator:
   ```bash
   python src/generators/v02/main.py
   ```

## Output

The generator creates the following files in the `data/synthetic` directory:

- `raw/accounts.csv`: Account information (5,250 accounts)
- `raw/merchants.csv`: Merchant information (200 merchants)
- `raw/transactions.csv`: Transaction data (50,000 transactions)
- `ground_truth/fraud_rings.json`: Ground truth data for fraud rings (45 rings)

## Configuration

The generator uses `src/generators/v02/config_academic.yaml` for configuration. You can modify this file to change:

- Number of accounts, transactions, and fraud rings
- Fraud patterns and behaviors
- Transaction characteristics
- Data quality parameters

## Validation

The generator includes built-in validation to ensure data quality:

- No duplicate IDs
- Valid amounts and timestamps
- Consistent fraud labeling
- Valid ring structures
- Realistic distributions

## License

This project is licensed under the MIT License - see the LICENSE file for details.