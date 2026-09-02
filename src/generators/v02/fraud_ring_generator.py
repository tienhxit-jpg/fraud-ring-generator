# src/fraud_ring_generator.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json

class FraudRingGenerator:
    """Generate fraud rings embedded in transaction data"""
    
    def __init__(self, config: Dict, normal_accounts: pd.DataFrame):
        self.config = config
        self.normal_accounts = normal_accounts
        self.participant_accounts = normal_accounts
        self._available_participants = list(normal_accounts['account_id'].values)
        self.cfg_rings = config['synthetic_data']['fraud_rings']
        self.seed = config['synthetic_data'].get('seed', config.get('project', {}).get('seed', 42))

        self.fraud_rings = []
        self.fraud_ring_transactions = []

    def _select_participants(self, count: int) -> List[str]:
        """Select fraud ring participants without replacement across rings.

        The caller should pass fraudster accounts, not the normal-account pool.
        Without global no-replacement sampling, generated fraudster accounts can
        become orphaned and never appear in any fraud ring transaction.
        """
        if len(self._available_participants) < count:
            raise ValueError(
                f"Not enough available fraud-ring participant accounts: "
                f"need {count}, have {len(self._available_participants)}"
            )
        selected = np.random.choice(self._available_participants, size=count, replace=False).tolist()
        selected_set = set(selected)
        self._available_participants = [account for account in self._available_participants if account not in selected_set]
        return selected
    
    def generate_all_rings(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate all fraud rings"""
        
        print(f"\n🔄 Generating {self.cfg_rings['total_ring_count']} fraud rings...\n")
        
        ring_id = 0
        start_date = datetime.strptime(self.config['synthetic_data']['start_date'], '%Y-%m-%d')
        
        # Small rings
        for _ in range(self.cfg_rings['ring_distribution']['small_rings_3person']):
            ring, txns = self._generate_small_ring(ring_id, start_date)
            self.fraud_rings.append(ring)
            self.fraud_ring_transactions.extend(txns)
            ring_id += 1
        
        # Medium rings
        for _ in range(self.cfg_rings['ring_distribution']['medium_rings_5person']):
            ring, txns = self._generate_medium_ring(ring_id, start_date)
            self.fraud_rings.append(ring)
            self.fraud_ring_transactions.extend(txns)
            ring_id += 1
        
        # Large rings
        for _ in range(self.cfg_rings['ring_distribution']['large_rings_8person']):
            ring, txns = self._generate_large_ring(ring_id, start_date)
            self.fraud_rings.append(ring)
            self.fraud_ring_transactions.extend(txns)
            ring_id += 1
        
        print(f"✓ Generated {len(self.fraud_rings)} fraud rings")
        print(f"✓ Generated {len(self.fraud_ring_transactions)} fraud-related transactions")
        
        return self.fraud_rings, self.fraud_ring_transactions
    
    def _generate_small_ring(self, ring_id: int, start_date: datetime) -> Tuple[Dict, List[Dict]]:
        """Generate 3-person triangle ring"""
        
        cfg = self.cfg_rings['ring_characteristics']['small']
        
        participants = self._select_participants(3)
        
        # Generate cycles
        num_cycles = np.random.randint(cfg['cycles_per_ring_min'], cfg['cycles_per_ring_max'] + 1)
        base_amount = np.random.uniform(cfg['total_amount_min'], cfg['total_amount_max'])
        
        transactions = []
        
        for cycle_num in range(num_cycles):
            # Amount escalates with cycle
            if self.cfg_rings['amount_patterns']['escalating']:
                amount = base_amount * (1 + self.cfg_rings['amount_patterns']['escalation_factor'] * cycle_num)
            else:
                amount = base_amount + np.random.uniform(-100, 100)
            
            amount_per_txn = amount / 3
            
            # Timing: burst activity
            cycle_start = start_date + timedelta(
                days=int(np.random.randint(0, 85)),  # Within 90-day window
                hours=int(np.random.choice(self.cfg_rings['activity_patterns']['typical_hours']))
            )
            
            # A → B → C → A
            for i in range(3):
                src = participants[i]
                dst = participants[(i + 1) % 3]
                
                timestamp = cycle_start + timedelta(hours=i*2)  # 2 hours apart
                
                transactions.append({
                    'source_account': src,
                    'destination_account': dst,
                    'amount': round(amount_per_txn, 2),
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'ring_id': f'RING_{ring_id:04d}',
                    'is_fraud': 1,
                    'cycle_num': cycle_num
                })
        
        # Create ring metadata
        ring_metadata = {
            'ring_id': f'RING_{ring_id:04d}',
            'ring_type': np.random.choice(list(self.cfg_rings['ring_types'].keys())),
            'participants': participants,
            'participant_count': 3,
            'transactions': len(transactions),
            'total_amount': round(sum(t['amount'] for t in transactions), 2),
            'pattern': 'cycle_3',
            'cycles': num_cycles
        }
        
        print(f"  • Small ring {ring_id}: {participants} → ${ring_metadata['total_amount']:,.0f}")
        
        return ring_metadata, transactions
    
    def _generate_medium_ring(self, ring_id: int, start_date: datetime) -> Tuple[Dict, List[Dict]]:
        """Generate 5-person cycle ring"""
        
        cfg = self.cfg_rings['ring_characteristics']['medium']
        
        participants = self._select_participants(5)
        
        num_cycles = np.random.randint(cfg['cycles_per_ring_min'], cfg['cycles_per_ring_max'] + 1)
        base_amount = np.random.uniform(cfg['total_amount_min'], cfg['total_amount_max'])
        
        transactions = []
        
        for cycle_num in range(num_cycles):
            if self.cfg_rings['amount_patterns']['escalating']:
                amount = base_amount * (1 + self.cfg_rings['amount_patterns']['escalation_factor'] * cycle_num)
            else:
                amount = base_amount + np.random.uniform(-500, 500)
            
            amount_per_txn = amount / 5
            
            cycle_start = start_date + timedelta(
                days=int(np.random.randint(0, 85)),
                hours=int(np.random.choice(self.cfg_rings['activity_patterns']['typical_hours']))
            )
            
            for i in range(5):
                src = participants[i]
                dst = participants[(i + 1) % 5]
                
                timestamp = cycle_start + timedelta(hours=i*1.5)
                
                transactions.append({
                    'source_account': src,
                    'destination_account': dst,
                    'amount': round(amount_per_txn, 2),
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'ring_id': f'RING_{ring_id:04d}',
                    'is_fraud': 1,
                    'cycle_num': cycle_num
                })
        
        ring_metadata = {
            'ring_id': f'RING_{ring_id:04d}',
            'ring_type': np.random.choice(list(self.cfg_rings['ring_types'].keys())),
            'participants': participants,
            'participant_count': 5,
            'transactions': len(transactions),
            'total_amount': round(sum(t['amount'] for t in transactions), 2),
            'pattern': 'cycle_5',
            'cycles': num_cycles
        }
        
        print(f"  • Medium ring {ring_id}: {len(participants)} participants → ${ring_metadata['total_amount']:,.0f}")
        
        return ring_metadata, transactions
    
    def _generate_large_ring(self, ring_id: int, start_date: datetime) -> Tuple[Dict, List[Dict]]:
        """Generate 8-person complex network ring"""
        
        cfg = self.cfg_rings['ring_characteristics']['large']
        
        participants = self._select_participants(8)
        
        num_cycles = np.random.randint(cfg['cycles_per_ring_min'], cfg['cycles_per_ring_max'] + 1)
        base_amount = np.random.uniform(cfg['total_amount_min'], cfg['total_amount_max'])
        
        transactions = []
        
        for cycle_num in range(num_cycles):
            if self.cfg_rings['amount_patterns']['escalating']:
                amount = base_amount * (1 + self.cfg_rings['amount_patterns']['escalation_factor'] * cycle_num)
            else:
                amount = base_amount + np.random.uniform(-1000, 1000)
            
            # Datasets may request one deterministic Hamiltonian cycle for a
            # compact correctness fixture; the default remains the dense random
            # topology used by the academic D2/D3 configurations.
            simple_cycle_only = cfg.get('topology') == 'simple_cycle'
            txn_count = 8 if simple_cycle_only else np.random.randint(
                cfg['transactions_per_cycle_min'], cfg['transactions_per_cycle_max'] + 1
            )
            amount_per_txn = amount / txn_count
            
            cycle_start = start_date + timedelta(
                days=int(np.random.randint(0, 85)),
                hours=int(np.random.choice(self.cfg_rings['activity_patterns']['typical_hours']))
            )
            
            # Create connections between participants (not necessarily linear)
            for i in range(txn_count):
                src_idx = i % 8
                dst_idx = (i + 1) % 8 if simple_cycle_only else (
                    i + np.random.randint(1, 8)
                ) % 8
                
                src = participants[src_idx]
                dst = participants[dst_idx]
                
                timestamp = cycle_start + timedelta(hours=i)
                
                transactions.append({
                    'source_account': src,
                    'destination_account': dst,
                    'amount': round(amount_per_txn, 2),
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'ring_id': f'RING_{ring_id:04d}',
                    'is_fraud': 1,
                    'cycle_num': cycle_num
                })
        
        ring_metadata = {
            'ring_id': f'RING_{ring_id:04d}',
            'ring_type': np.random.choice(list(self.cfg_rings['ring_types'].keys())),
            'participants': participants,
            'participant_count': 8,
            'transactions': len(transactions),
            'total_amount': round(sum(t['amount'] for t in transactions), 2),
            'pattern': 'complex_network',
            'cycles': num_cycles
        }
        
        print(f"  • Large ring {ring_id}: {len(participants)} participants → ${ring_metadata['total_amount']:,.0f}")
        
        return ring_metadata, transactions
    
    def get_ring_metadata(self) -> Dict:
        """Get metadata for all rings"""
        
        return {
            'rings': self.fraud_rings,
            'total_rings': len(self.fraud_rings),
            'total_fraud_transactions': len(self.fraud_ring_transactions),
            'total_fraud_amount': sum(r['total_amount'] for r in self.fraud_rings)
        }
    
    def save_rings_to_json(self, output_path: str):
        """Save fraud ring metadata to JSON"""
        
        metadata = self.get_ring_metadata()
        
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✓ Saved fraud ring metadata to {output_path}")