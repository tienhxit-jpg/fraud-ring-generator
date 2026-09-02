#!/usr/bin/env python3
"""
Neo4j Data Loader for Fraud Ring Detection System
Loads synthetic data from CSV files into Neo4j database
Resets fraud ring identification fields to default values
"""

import argparse
import csv
import logging
from pathlib import Path
from typing import Dict, List
from neo4j import GraphDatabase
from tqdm import tqdm


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Neo4jDataLoader:
    """Load CSV data into Neo4j database with fraud ring detection schema"""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def clear_database(self):
        """Clear all nodes and relationships from database"""
        with self.driver.session(database=self.database) as session:
            logger.info("Clearing database...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared successfully")
    
    def create_constraints(self):
        """Create uniqueness constraints and indexes"""
        with self.driver.session(database=self.database) as session:
            logger.info("Creating constraints and indexes...")
            
            constraints = [
                "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.account_id IS UNIQUE",
                "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
                "CREATE CONSTRAINT merchant_id_unique IF NOT EXISTS FOR (m:Merchant) REQUIRE m.merchant_id IS UNIQUE",
                "CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint warning: {e}")
            
            indexes = [
                "CREATE INDEX account_type_idx IF NOT EXISTS FOR (a:Account) ON (a.account_type)",
                "CREATE INDEX transaction_date_idx IF NOT EXISTS FOR (t:Transaction) ON (t.date)",
                "CREATE INDEX transaction_type_idx IF NOT EXISTS FOR (t:Transaction) ON (t.transaction_type)",
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    logger.warning(f"Index warning: {e}")
            
            logger.info("Constraints and indexes created")
    
    def load_accounts(self, csv_path: Path, batch_size: int = 1000):
        """Load accounts and customers, reset fraud_ring_member to None"""
        logger.info(f"Loading accounts from {csv_path}")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total_rows = sum(1 for _ in open(csv_path, 'r', encoding='utf-8')) - 1
            
            with self.driver.session(database=self.database) as session:
                batch = []
                with tqdm(total=total_rows, desc="Loading accounts") as pbar:
                    f.seek(0)
                    next(reader)
                    
                    for row in reader:
                        account_data = {
                            'account_id': row['account_id'],
                            'customer_id': row['customer_id'],
                            'customer_name': row['customer_name'],
                            'account_type': row['account_type'],
                            'created_date': row['created_date'],
                            'account_age_days': int(row['account_age_days']) if row['account_age_days'] else 0,
                            'kyc_risk_score': float(row['kyc_risk_score']) if row['kyc_risk_score'] else 0.0,
                            'kyc_level': row['kyc_level'],
                            'daily_limit_usd': float(row['daily_limit_usd']) if row['daily_limit_usd'] else 0.0,
                            'avg_transaction_amount': float(row['avg_transaction_amount']) if row['avg_transaction_amount'] else 0.0,
                            'monthly_transaction_count': int(row['monthly_transaction_count']) if row['monthly_transaction_count'] else 0,
                            'is_blacklisted': row['is_blacklisted'].lower() == 'true' if row['is_blacklisted'] else False,
                            'status': row['status'],
                            'fraud_ring_member': None
                        }
                        batch.append(account_data)
                        
                        if len(batch) >= batch_size:
                            self._insert_accounts_batch(session, batch)
                            pbar.update(len(batch))
                            batch = []
                    
                    if batch:
                        self._insert_accounts_batch(session, batch)
                        pbar.update(len(batch))
        
        logger.info("Accounts loaded successfully")
    
    def _insert_accounts_batch(self, session, batch: List[Dict]):
        """Insert batch of accounts"""
        query = """
        UNWIND $batch AS row
        MERGE (c:Customer {customer_id: row.customer_id})
        SET c.customer_name = row.customer_name
        MERGE (a:Account {account_id: row.account_id})
        SET a.account_type = row.account_type,
            a.created_date = row.created_date,
            a.account_age_days = row.account_age_days,
            a.kyc_risk_score = row.kyc_risk_score,
            a.kyc_level = row.kyc_level,
            a.daily_limit_usd = row.daily_limit_usd,
            a.avg_transaction_amount = row.avg_transaction_amount,
            a.monthly_transaction_count = row.monthly_transaction_count,
            a.is_blacklisted = row.is_blacklisted,
            a.status = row.status,
            a.fraud_ring_member = row.fraud_ring_member
        MERGE (c)-[:OWNS]->(a)
        """
        session.run(query, batch=batch)
    
    def load_merchants(self, csv_path: Path, batch_size: int = 1000):
        """Load merchants from CSV"""
        logger.info(f"Loading merchants from {csv_path}")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total_rows = sum(1 for _ in open(csv_path, 'r', encoding='utf-8')) - 1
            
            with self.driver.session(database=self.database) as session:
                batch = []
                with tqdm(total=total_rows, desc="Loading merchants") as pbar:
                    f.seek(0)
                    next(reader)
                    
                    for row in reader:
                        merchant_data = {
                            'merchant_id': row['merchant_id'],
                            'merchant_name': row['merchant_name'],
                            'merchant_type': row['merchant_type'],
                            'category': row['category'],
                            'risk_level': row['risk_level'],
                            'is_verified': row['is_verified'].lower() == 'true' if row['is_verified'] else False,
                            'country': row['country']
                        }
                        batch.append(merchant_data)
                        
                        if len(batch) >= batch_size:
                            self._insert_merchants_batch(session, batch)
                            pbar.update(len(batch))
                            batch = []
                    
                    if batch:
                        self._insert_merchants_batch(session, batch)
                        pbar.update(len(batch))
        
        logger.info("Merchants loaded successfully")
    
    def _insert_merchants_batch(self, session, batch: List[Dict]):
        """Insert batch of merchants"""
        query = """
        UNWIND $batch AS row
        MERGE (m:Merchant {merchant_id: row.merchant_id})
        SET m.merchant_name = row.merchant_name,
            m.merchant_type = row.merchant_type,
            m.category = row.category,
            m.risk_level = row.risk_level,
            m.is_verified = row.is_verified,
            m.country = row.country
        """
        session.run(query, batch=batch)
    
    def load_transactions(self, csv_path: Path, batch_size: int = 500):
        """Load transactions, reset fraud fields to defaults"""
        logger.info(f"Loading transactions from {csv_path}")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total_rows = sum(1 for _ in open(csv_path, 'r', encoding='utf-8')) - 1
            
            with self.driver.session(database=self.database) as session:
                batch = []
                with tqdm(total=total_rows, desc="Loading transactions") as pbar:
                    f.seek(0)
                    next(reader)
                    
                    for row in reader:
                        transaction_data = {
                            'transaction_id': row['transaction_id'],
                            'source_account': row['source_account'],
                            'destination_account': row['destination_account'],
                            'amount_usd': float(row['amount_usd']) if row['amount_usd'] else 0.0,
                            'original_amount': float(row['original_amount']) if row['original_amount'] else 0.0,
                            'original_currency': row['original_currency'],
                            'timestamp': row['timestamp'],
                            'date': row['date'],
                            'hour': int(row['hour']) if row['hour'] else 0,
                            'channel': row['channel'],
                            'transaction_type': row['transaction_type'],
                            'is_fraud': 0,
                            'fraud_ring_id': None,
                            'cycle_num': None
                        }
                        batch.append(transaction_data)
                        
                        if len(batch) >= batch_size:
                            self._insert_transactions_batch(session, batch)
                            pbar.update(len(batch))
                            batch = []
                    
                    if batch:
                        self._insert_transactions_batch(session, batch)
                        pbar.update(len(batch))
        
        logger.info("Transactions loaded successfully")
    
    def _insert_transactions_batch(self, session, batch: List[Dict]):
        """Insert batch of transactions with relationships"""
        query = """
        UNWIND $batch AS row
        CREATE (t:Transaction {transaction_id: row.transaction_id})
        SET t.amount_usd = row.amount_usd,
            t.original_amount = row.original_amount,
            t.original_currency = row.original_currency,
            t.timestamp = row.timestamp,
            t.date = row.date,
            t.hour = row.hour,
            t.channel = row.channel,
            t.transaction_type = row.transaction_type,
            t.is_fraud = row.is_fraud,
            t.fraud_ring_id = row.fraud_ring_id,
            t.cycle_num = row.cycle_num
        WITH t, row
        MATCH (src:Account {account_id: row.source_account})
        MATCH (dst:Account {account_id: row.destination_account})
        CREATE (src)-[:SENT]->(t)
        CREATE (t)-[:RECEIVED_BY]->(dst)
        """
        session.run(query, batch=batch)
    
    def load_all_data(self, data_dir: Path, clear_first: bool = False):
        """Load all CSV files into Neo4j"""
        try:
            if clear_first:
                self.clear_database()
            
            self.create_constraints()
            
            accounts_path = data_dir / "accounts.csv"
            merchants_path = data_dir / "merchants.csv"
            transactions_path = data_dir / "transactions.csv"
            
            if accounts_path.exists():
                self.load_accounts(accounts_path)
            else:
                logger.warning(f"Accounts file not found: {accounts_path}")
            
            if merchants_path.exists():
                self.load_merchants(merchants_path)
            else:
                logger.warning(f"Merchants file not found: {merchants_path}")
            
            if transactions_path.exists():
                self.load_transactions(transactions_path)
            else:
                logger.warning(f"Transactions file not found: {transactions_path}")
            
            logger.info("All data loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error during data loading: {e}")
            raise


def main():
    """Main function to load data into Neo4j"""
    parser = argparse.ArgumentParser(
        description='Load synthetic fraud detection data into Neo4j',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python load_data.py --uri bolt://localhost:7687 --username neo4j --password mypassword --data-dir data/synthetic/v2/raw
  python load_data.py --uri bolt://localhost:7687 --username neo4j --password mypassword --data-dir data/synthetic/v2/raw --clear
        '''
    )
    
    parser.add_argument('--uri', required=True, help='Neo4j connection URI (e.g., bolt://localhost:7687)')
    parser.add_argument('--username', required=True, help='Neo4j username')
    parser.add_argument('--password', required=True, help='Neo4j password')
    parser.add_argument('--database', default='neo4j', help='Neo4j database name (default: neo4j)')
    parser.add_argument('--data-dir', required=True, help='Directory containing CSV files')
    parser.add_argument('--clear', action='store_true', help='Clear database before loading')
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 1
    
    loader = None
    try:
        loader = Neo4jDataLoader(
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database
        )
        
        loader.load_all_data(data_dir, clear_first=args.clear)
        logger.info("Data loading completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
        
    finally:
        if loader:
            loader.close()


if __name__ == '__main__':
    exit(main())
