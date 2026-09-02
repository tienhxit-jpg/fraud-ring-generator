# src/data_generator.py

import os
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from config_loader import ConfigLoader
from account_generator import AccountGenerator
from fraud_ring_generator import FraudRingGenerator
from transaction_generator import TransactionGenerator
from data_validator import DataValidator

class SyntheticDataGenerator:
    """Main orchestrator for synthetic data generation"""
    
    def __init__(self, config_path: str = "config/config_academic.yaml"):
        self.loader = ConfigLoader(config_path)
        self.config = self.loader.load()
        self.seed = self.config['synthetic_data'].get('seed', self.config.get('project', {}).get('seed', 42))
        
        # Create output directories
        self._create_directories()
    
    def _create_directories(self):
        """Create output directories"""
        
        output_cfg = self.config['synthetic_data']['output']
        
        for key in ['raw_dir', 'processed_dir', 'ground_truth_dir']:
            path = output_cfg[key]
            Path(path).mkdir(parents=True, exist_ok=True)
    
    def generate_all(self):
        """Generate all synthetic data"""
        
        print("\n" + "="*70)
        print("SYNTHETIC DATA GENERATION PIPELINE")
        print("="*70)
        
        start_time = datetime.now()
        np.random.seed(self.seed)
        
        # Step 1: Generate accounts
        account_gen = AccountGenerator(self.config)
        normal_accounts = account_gen.generate_normal_accounts(
            self.config['synthetic_data']['accounts']['normal_account_count']
        )
        merchants = account_gen.generate_merchants(
            self.config['synthetic_data']['accounts']['merchant_count']
        )
        
        # Step 2: Generate fraudster accounts first, then use those exact
        # accounts as fraud-ring participants. This avoids orphan fraudsters
        # and ensures rings have high-risk KYC profiles.
        required_fraudster_count = self._required_fraudster_account_count()
        fraudster_accounts = account_gen.generate_fraudster_accounts(required_fraudster_count)

        normal_accounts = normal_accounts.copy()
        normal_accounts['fraud_ring_member'] = False

        fraud_ring_gen = FraudRingGenerator(self.config, fraudster_accounts)
        fraud_rings, fraud_transactions_data = fraud_ring_gen.generate_all_rings()
        
        # Combine all accounts
        all_accounts = pd.concat([normal_accounts, fraudster_accounts], ignore_index=True)
        
        # Step 3: Generate normal transactions
        transaction_gen = TransactionGenerator(self.config, all_accounts)
        total_txn = self.config['synthetic_data']['total_transactions']
        normal_txn_count = int(total_txn * self.config['synthetic_data']['transactions']['normal_transaction_ratio'])
        
        normal_transactions = transaction_gen.generate_normal_transactions(normal_txn_count)
        
        # Step 4: Convert fraud ring transactions to dataframe
        fraud_df = pd.DataFrame(fraud_transactions_data)
        if not fraud_df.empty:
            fraud_df = fraud_df.copy()
            fraud_df['transaction_id'] = [f"TXN_{normal_txn_count + i + 1:09d}" for i in range(len(fraud_df))]
            fraud_df['fraud_ring_id'] = fraud_df['ring_id']
            fraud_df['amount_usd'] = fraud_df['amount']
            fraud_df['original_amount'] = fraud_df['amount']
            fraud_df['original_currency'] = 'USD'

            timestamp_dt = pd.to_datetime(fraud_df['timestamp'])
            fraud_df['date'] = timestamp_dt.dt.strftime('%Y-%m-%d')
            fraud_df['hour'] = timestamp_dt.dt.hour
            fraud_df['channel'] = 'peer_to_peer'
            fraud_df['transaction_type'] = 'fraud_ring'
            fraud_df = fraud_df.drop(columns=['amount', 'ring_id'], errors='ignore')
        
        # Step 5: Combine and shuffle
        all_transactions = pd.concat([normal_transactions, fraud_df], ignore_index=True)
        all_transactions = all_transactions.sample(frac=1).reset_index(drop=True)
        
        # Step 6: Validate
        print("\n" + "="*70)
        validator = DataValidator(self.config)
        validator.validate(all_accounts, all_transactions, fraud_rings)
        print("="*70)
        
        # Step 7: Save
        self._save_data(all_accounts, merchants, all_transactions, fraud_rings)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*70)
        print(f"✓ GENERATION COMPLETE in {duration:.1f} seconds")
        print("="*70)
        
        return all_accounts, merchants, all_transactions, fraud_rings

    def _required_fraudster_account_count(self) -> int:
        """Return unique fraudster accounts needed if rings do not share accounts."""
        distribution = self.config['synthetic_data']['fraud_rings']['ring_distribution']
        characteristics = self.config['synthetic_data']['fraud_rings']['ring_characteristics']
        return (
            int(distribution.get('small_rings_3person', 0)) * int(characteristics['small']['participant_count'])
            + int(distribution.get('medium_rings_5person', 0)) * int(characteristics['medium']['participant_count'])
            + int(distribution.get('large_rings_8person', 0)) * int(characteristics['large']['participant_count'])
        )
    
    def _save_data(self, accounts, merchants, transactions, fraud_rings):
        """Save generated data to CSV and JSON"""
        
        print("\n💾 Saving data files...\n")
        
        output_cfg = self.config['synthetic_data']['output']
        
        # Save accounts
        accounts_path = f"{output_cfg['raw_dir']}/{output_cfg['accounts_file']}"
        accounts.to_csv(accounts_path, index=False)
        print(f"✓ Saved {len(accounts):,} accounts to {accounts_path}")
        
        # Save merchants
        merchants_path = f"{output_cfg['raw_dir']}/{output_cfg['merchants_file']}"
        merchants.to_csv(merchants_path, index=False)
        print(f"✓ Saved {len(merchants):,} merchants to {merchants_path}")
        
        # Save transactions
        transactions_path = f"{output_cfg['raw_dir']}/{output_cfg['transactions_file']}"
        transactions.to_csv(transactions_path, index=False)
        print(f"✓ Saved {len(transactions):,} transactions to {transactions_path}")
        
        # Save fraud rings
        rings_path = f"{output_cfg['ground_truth_dir']}/{output_cfg['fraud_rings_file']}"
        fraud_ring_gen = FraudRingGenerator(self.config, accounts)
        fraud_ring_gen.fraud_rings = fraud_rings
        fraud_ring_gen.save_rings_to_json(rings_path)
        
        print("\n✓ All files saved successfully!")