# src/config_loader.py

import yaml
import os
from typing import Dict, Any
from pathlib import Path

class ConfigLoader:
    """Load and validate configuration file"""
    
    def __init__(self, config_path: str = "config/config_academic.yaml"):
        self.config_path = config_path
        self.config = None
    
    def load(self) -> Dict[str, Any]:
        """Load YAML config file"""
        
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        print(f"✓ Loaded config from {self.config_path}")
        self._print_config_summary()
        
        return self.config
    
    def _print_config_summary(self):
        """Print summary of configuration"""
        
        cfg = self.config['synthetic_data']
        
        print("\n" + "="*70)
        print("SYNTHETIC DATA CONFIGURATION SUMMARY")
        print("="*70)
        print(f"Total Transactions:     {cfg['total_transactions']:,}")
        print(f"Duration:               {cfg['duration_days']} days")
        print(f"Normal Accounts:        {cfg['accounts']['normal_account_count']:,}")
        print(f"Merchants:              {cfg['accounts']['merchant_count']}")
        print(f"Fraud Rings:            {cfg['fraud_rings']['total_ring_count']}")
        print(f"  - Small (3-person):   {cfg['fraud_rings']['ring_distribution']['small_rings_3person']}")
        print(f"  - Medium (5-person):  {cfg['fraud_rings']['ring_distribution']['medium_rings_5person']}")
        print(f"  - Large (8-person):   {cfg['fraud_rings']['ring_distribution']['large_rings_8person']}")
        print("="*70 + "\n")
    
    def get_config(self) -> Dict[str, Any]:
        """Get loaded config"""
        if self.config is None:
            self.load()
        return self.config