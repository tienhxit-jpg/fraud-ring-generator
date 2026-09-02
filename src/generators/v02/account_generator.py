# src/account_generator.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import uuid

class AccountGenerator:
    """Generate realistic bank accounts"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cfg_accounts = config['synthetic_data']['accounts']
        self.cfg_normal = config['synthetic_data']['normal_account_rules']
        self.cfg_fraudster = config['synthetic_data']['fraudster_account_rules']
        self.seed = config['synthetic_data'].get('seed', config.get('project', {}).get('seed', 42))

        # Seed is set once by SyntheticDataGenerator to keep phase RNG streams independent.
    
    def generate_normal_accounts(self, count: int) -> pd.DataFrame:
        """Generate normal customer accounts"""
        
        print(f"\n📝 Generating {count:,} normal accounts...")
        
        accounts = []
        
        for i in range(count):
            account_id = f"ACC_{i+1:06d}"
            
            # Account age (lognormal: newer accounts more likely)
            account_age = np.random.randint(
                self.cfg_normal['account_age_days_min'],
                self.cfg_normal['account_age_days_max']
            )
            
            created_date = datetime(2025, 10, 1) - timedelta(days=account_age)
            
            # KYC risk score (Beta distribution: skewed toward low risk)
            kyc_risk = np.random.beta(
                self.cfg_normal['kyc_risk_alpha'],
                self.cfg_normal['kyc_risk_beta']
            )
            
            # Daily limit (random choice)
            daily_limit = np.random.choice(self.cfg_normal['daily_limit_options'])
            
            # Transaction statistics
            avg_amount = np.random.normal(
                self.cfg_normal['avg_amount_mean'],
                self.cfg_normal['avg_amount_std']
            )
            avg_amount = max(100, avg_amount)  # Minimum $100
            
            monthly_txn = np.random.poisson(self.cfg_normal['monthly_transaction_count_lambda'])
            
            accounts.append({
                'account_id': account_id,
                'customer_id': f"CUST_{i+1:06d}",
                'customer_name': f"Customer {i+1}",
                'account_type': np.random.choice(['checking', 'savings', 'business']),
                'created_date': created_date.strftime('%Y-%m-%d'),
                'account_age_days': account_age,
                'kyc_risk_score': round(kyc_risk, 3),
                'kyc_level': 'verified' if kyc_risk < 0.5 else 'pending',
                'daily_limit_usd': daily_limit,
                'avg_transaction_amount': round(avg_amount, 2),
                'monthly_transaction_count': monthly_txn,
                'is_blacklisted': False,
                'status': 'active'
            })
        
        df = pd.DataFrame(accounts)
        print(f"✓ Generated {len(df):,} normal accounts")
        
        return df
    
    def generate_fraudster_accounts(self, count: int) -> pd.DataFrame:
        """Generate fraudster accounts (for fraud rings)"""
        
        print(f"\n📝 Generating {count:,} fraudster accounts...")
        
        accounts = []
        normal_count = self.cfg_accounts['normal_account_count']
        
        for i in range(count):
            account_id = f"ACC_{normal_count + i + 1:06d}"
            
            # Fraudster accounts: newer, more suspicious
            account_age = np.random.randint(
                self.cfg_fraudster['account_age_days_min'],
                self.cfg_fraudster['account_age_days_max']
            )
            
            created_date = datetime(2025, 10, 1) - timedelta(days=account_age)
            
            # Higher KYC risk
            kyc_risk = np.random.beta(
                self.cfg_fraudster['kyc_risk_alpha'],
                self.cfg_fraudster['kyc_risk_beta']
            )
            
            daily_limit = np.random.choice(self.cfg_fraudster['daily_limit_options'])
            
            # Higher average amounts
            avg_amount = np.random.normal(
                self.cfg_fraudster['avg_amount_mean'],
                self.cfg_fraudster['avg_amount_std']
            )
            avg_amount = max(1000, avg_amount)
            
            monthly_txn = np.random.poisson(self.cfg_fraudster['monthly_transaction_count_lambda'])
            
            accounts.append({
                'account_id': account_id,
                'customer_id': f"CUST_{normal_count + i + 1:06d}",
                'customer_name': f"Fraudster {i+1}",
                'account_type': np.random.choice(['checking', 'business']),
                'created_date': created_date.strftime('%Y-%m-%d'),
                'account_age_days': account_age,
                'kyc_risk_score': min(round(kyc_risk, 3), 0.95),  # Higher risk
                'kyc_level': 'pending' if kyc_risk > 0.5 else 'verified',
                'daily_limit_usd': daily_limit,
                'avg_transaction_amount': round(avg_amount, 2),
                'monthly_transaction_count': monthly_txn,
                'is_blacklisted': False,
                'status': 'active',
                'fraud_ring_member': True
            })
        
        df = pd.DataFrame(accounts)
        print(f"✓ Generated {len(df):,} fraudster accounts")
        
        return df
    
    def generate_merchants(self, count: int) -> pd.DataFrame:
        """Generate merchant accounts"""
        
        print(f"\n📝 Generating {count:,} merchants...")
        
        merchants = []
        
        categories = ['retail', 'online', 'restaurant', 'services', 'telecom', 'utilities']
        
        for i in range(count):
            merchant_id = f"MER_{i+1:06d}"
            
            is_high_risk = i < self.config['synthetic_data']['merchants']['high_risk_merchants']
            
            merchants.append({
                'merchant_id': merchant_id,
                'merchant_name': f"Merchant {i+1}",
                'merchant_type': np.random.choice(['retail', 'online', 'bank']),
                'category': np.random.choice(categories),
                'risk_level': 'high' if is_high_risk else 'low',
                'is_verified': True,
                'country': 'Vietnam'
            })
        
        df = pd.DataFrame(merchants)
        print(f"✓ Generated {len(df):,} merchants")
        
        return df