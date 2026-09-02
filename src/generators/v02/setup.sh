#!/bin/bash
# setup.sh

echo "Setting up Fraud Ring Detection Synthetic Data Generator..."

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r src/generators/v02/requirements.txt

# Create output directories
echo "Creating output directories..."
mkdir -p data/synthetic/v2/{raw,processed,ground_truth}

echo "Setup complete!"
echo "To activate the environment, run: source venv/bin/activate"
echo "To generate data, run: python src/generators/v02/main.py"