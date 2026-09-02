# src/transaction_generator.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

class TransactionGenerator:
    """Generate realistic transaction data"""
    
    def __init__(self, config: Dict, accounts: pd.DataFrame):
        self.config = config
        self.accounts = accounts
        self.cfg_txn = config['synthetic_data']['transactions']
        self.cfg_normal = config['synthetic_data']['normal_transaction_rules']
        self.seed = config['synthetic_data'].get('seed', config.get('project', {}).get('seed', 42))
        # Seed is set once by SyntheticDataGenerator to keep phase RNG streams independent.
    
    def generate_normal_transactions(self, count: int) -> pd.DataFrame:
        """Generate normal (non-fraud) transactions"""
        
        print(f"\n💳 Generating {count:,} normal transactions...")
        
        transactions = []
        start_date = datetime.strptime(self.config['synthetic_data']['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(self.config['synthetic_data']['end_date'], '%Y-%m-%d')
        
        # Get non-fraudster accounts only
        fraud_member_flags = self.accounts.get('fraud_ring_member')
        if fraud_member_flags is None:
            normal_accounts = self.accounts['account_id'].values
        else:
            normal_accounts = self.accounts[~fraud_member_flags.fillna(False).astype(bool)]['account_id'].values
        
        for i in range(count):
            # Random date within range
            random_days = int(np.random.randint(0, (end_date - start_date).days))
            
            # Time pattern: 85% business hours, 15% other
            is_business_hour = np.random.random() < self.cfg_normal['business_hours_probability']
            
            if is_business_hour:
                hour = int(np.random.choice(range(8, 18)))
            else:
                hour = int(np.random.choice(range(24)))
            
            timestamp = start_date + timedelta(days=random_days, hours=hour, minutes=int(np.random.randint(0, 60)))
            
            # Amount (lognormal distribution)
            amount = np.random.lognormal(
                mean=np.log(self.cfg_normal['amount_mean']),
                sigma=self.cfg_normal['amount_std'] / self.cfg_normal['amount_mean']
            )
            amount = np.clip(amount, self.cfg_normal['amount_min'], self.cfg_normal['amount_max'])
            
            # Currency
            currencies = list(self.cfg_txn['amounts']['currency_distribution'].keys())
            probs = list(self.cfg_txn['amounts']['currency_distribution'].values())
            currency = np.random.choice(currencies, p=probs)
            
            # Convert to USD
            exchange_rates = self.cfg_txn['exchange_rates']
            if currency == 'VND':
                amount_usd = amount / exchange_rates['VND_to_USD']
            elif currency == 'EUR':
                amount_usd = amount * exchange_rates['EUR_to_USD']
            elif currency == 'GBP':
                amount_usd = amount * exchange_rates['GBP_to_USD']
            else:
                amount_usd = amount
            
            # Random source and destination
            src = np.random.choice(normal_accounts)
            dst = np.random.choice(normal_accounts)
            
            # Ensure different
            while dst == src:
                dst = np.random.choice(normal_accounts)
            
            # Channel
            channels = list(self.cfg_txn['channels'].keys())
            probs = list(self.cfg_txn['channels'].values())
            channel = np.random.choice(channels, p=probs)
            
            transactions.append({
                'transaction_id': f'TXN_{i+1:09d}',
                'source_account': src,
                'destination_account': dst,
                'amount_usd': round(amount_usd, 2),
                'original_amount': round(amount, 2),
                'original_currency': currency,
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'date': timestamp.strftime('%Y-%m-%d'),
                'hour': hour,
                'channel': channel,
                'transaction_type': 'p2p',
                'is_fraud': 0,
                'fraud_ring_id': None
            })
        
        df = pd.DataFrame(transactions)
        print(f"✓ Generated {len(df):,} normal transactions")
        
        return df