# main.py

"""
Synthetic Data Generation for Academic Paper
Project: Fraud Ring Detection in Digital Banking
"""

import sys
import os
from pathlib import Path

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_generator import SyntheticDataGenerator

def main():
    """Main execution"""
    
    print("\n" + "="*70)
    print("🚀 FRAUD RING DETECTION - SYNTHETIC DATA GENERATION")
    print("="*70)
    print("For Academic Paper Submission")
    print("="*70)
    
    try:
        # Initialize generator
        config_path = Path(__file__).with_name("config_academic.yaml")
        generator = SyntheticDataGenerator(str(config_path))
        
        # Generate all data
        accounts, merchants, transactions, fraud_rings = generator.generate_all()
        
        print("\n" + "="*70)
        print("📊 GENERATION SUMMARY")
        print("="*70)
        print(f"Accounts:           {len(accounts):,}")
        print(f"Merchants:          {len(merchants):,}")
        print(f"Transactions:       {len(transactions):,}")
        print(f"Fraud Rings:        {len(fraud_rings)}")
        print(f"Fraud Transactions: {len(transactions[transactions['is_fraud']==1]):,}")
        print(f"Fraud Ratio:        {len(transactions[transactions['is_fraud']==1])/len(transactions)*100:.2f}%")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)