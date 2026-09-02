# src/data_validator.py

import pandas as pd
from typing import Dict, List
from datetime import datetime

class DataValidator:
    """Validate generated synthetic data"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cfg_validation = config['synthetic_data']['validation']
    
    def validate(self, accounts: pd.DataFrame, transactions: pd.DataFrame, fraud_rings: List[Dict]):
        """Run all validation checks"""
        
        if not self.cfg_validation['enabled']:
            print("⚠️  Validation disabled in config")
            return
        
        print("\n" + "="*70)
        print("DATA VALIDATION")
        print("="*70)
        
        # Run individual checks
        self._check_no_duplicate_ids(transactions)
        self._check_valid_amounts(transactions)
        self._check_valid_timestamps(transactions)
        self._check_fraud_label_consistency(transactions)
        self._check_ring_structure_valid(accounts, transactions, fraud_rings)
        self._check_distributions_realistic(transactions)
        
        print("✅ All validation checks passed!")
    
    def _check_no_duplicate_ids(self, transactions: pd.DataFrame):
        """Check for duplicate transaction IDs"""
        if self.cfg_validation['checks']['no_duplicate_ids']:
            duplicates = transactions[transactions.duplicated('transaction_id', keep=False)]
            if len(duplicates) > 0:
                raise ValueError(f"Found {len(duplicates)} duplicate transaction IDs")
            print("✓ No duplicate transaction IDs")
    
    def _check_valid_amounts(self, transactions: pd.DataFrame):
        """Check that all amounts are positive and within limits"""
        if self.cfg_validation['checks']['valid_amounts']:
            amount_max = self.config['synthetic_data']['transactions']['amounts']['amount_max']
            normal_txns = transactions[transactions['is_fraud'] == 0]
            invalid = normal_txns[
                (normal_txns['amount_usd'] <= 0) |
                (normal_txns['amount_usd'] > amount_max)
            ]
            if len(invalid) > 0:
                raise ValueError(f"Found {len(invalid)} transactions with invalid amounts")
            if (transactions['amount_usd'] <= 0).any():
                raise ValueError("Found transactions with non-positive amounts")
            print("✓ All normal transaction amounts positive and within limits")
    
    def _check_valid_timestamps(self, transactions: pd.DataFrame):
        """Check that all timestamps are within the expected range"""
        if self.cfg_validation['checks']['valid_timestamps']:
            start_date = datetime.strptime(self.config['synthetic_data']['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(self.config['synthetic_data']['end_date'], '%Y-%m-%d')
            
            transactions['timestamp_dt'] = pd.to_datetime(transactions['timestamp'])
            invalid = transactions[
                (transactions['timestamp_dt'] < start_date) | 
                (transactions['timestamp_dt'] > end_date)
            ]
            
            if len(invalid) > 0:
                raise ValueError(f"Found {len(invalid)} transactions with invalid timestamps")
            print("✓ All timestamps within range")
    
    def _check_fraud_label_consistency(self, transactions: pd.DataFrame):
        """Check that fraud labels are consistent"""
        if self.cfg_validation['checks']['fraud_label_consistency']:
            # Fraud transactions should have ring_id, normal shouldn't
            fraud_txns = transactions[transactions['is_fraud'] == 1]
            normal_txns = transactions[transactions['is_fraud'] == 0]
            
            if fraud_txns['fraud_ring_id'].isna().any():
                raise ValueError("Found fraud transactions without fraud_ring_id")
            
            if normal_txns['fraud_ring_id'].notna().any():
                raise ValueError("Found normal transactions with fraud_ring_id")
            
            print("✓ Fraud labels consistent")
    
    def _check_ring_structure_valid(self, accounts: pd.DataFrame, transactions: pd.DataFrame, fraud_rings: List[Dict]):
        """Check that ring structure is valid"""
        if self.cfg_validation['checks']['ring_structure_valid']:
            # Check that all ring participants exist in accounts
            all_participants = set()
            for ring in fraud_rings:
                all_participants.update(ring['participants'])
            
            missing_accounts = all_participants - set(accounts['account_id'])
            if missing_accounts:
                raise ValueError(f"Found {len(missing_accounts)} ring participants not in accounts")
            
            # Check that all fraud transactions have valid ring_ids
            fraud_txns = transactions[transactions['is_fraud'] == 1]
            ring_ids = {ring['ring_id'] for ring in fraud_rings}
            invalid_ring_refs = fraud_txns[~fraud_txns['fraud_ring_id'].isin(ring_ids)]
            
            if len(invalid_ring_refs) > 0:
                raise ValueError(f"Found {len(invalid_ring_refs)} fraud transactions with invalid ring IDs")
            
            print("✓ Ring structure valid")
    
    def _check_distributions_realistic(self, transactions: pd.DataFrame):
        """Check that distributions are realistic"""
        if self.cfg_validation['checks']['distribution_check']:
            # Check fraud ratio
            fraud_ratio = transactions['is_fraud'].mean()
            expected = self.config['synthetic_data']['validation']['expected_fraud_ratio']
            max_allowed = self.config['synthetic_data']['validation']['max_fraud_ratio']
            
            if fraud_ratio > max_allowed:
                raise ValueError(f"Fraud ratio {fraud_ratio:.3f} exceeds maximum allowed {max_allowed}")
            
            print(f"✓ Fraud ratio {fraud_ratio:.3f} within expected range ({expected}±{max_allowed-expected})")