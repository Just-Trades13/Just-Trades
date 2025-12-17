#!/usr/bin/env python3
"""
Database Initialization Script
Runs on startup to ensure all tables exist.
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('init_db')

DATABASE_URL = os.getenv('DATABASE_URL')

def init_postgres():
    """Initialize PostgreSQL tables."""
    if not DATABASE_URL or not DATABASE_URL.startswith('postgres'):
        logger.info("No PostgreSQL DATABASE_URL - skipping")
        return
    
    import psycopg2
    
    # Fix Heroku-style URL
    db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    logger.info("Connecting to PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Create tables
    logger.info("Creating tables...")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255),
            password VARCHAR(255),
            tradovate_token TEXT,
            tradovate_refresh_token TEXT,
            md_access_token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traders (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES accounts(id),
            name VARCHAR(255) NOT NULL,
            subaccount_id INTEGER,
            subaccount_name VARCHAR(255),
            is_demo BOOLEAN DEFAULT TRUE,
            max_contracts INTEGER DEFAULT 10,
            custom_ticker VARCHAR(50),
            multiplier REAL DEFAULT 1.0,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id SERIAL PRIMARY KEY,
            trader_id INTEGER REFERENCES traders(id),
            name VARCHAR(255) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            webhook_token VARCHAR(255),
            ticker VARCHAR(50),
            position_size INTEGER DEFAULT 1,
            tp_enabled BOOLEAN DEFAULT TRUE,
            tp_targets TEXT,
            sl_enabled BOOLEAN DEFAULT FALSE,
            sl_amount REAL,
            trailing_sl BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_trades (
            id SERIAL PRIMARY KEY,
            recorder_id INTEGER,
            signal_id VARCHAR(255),
            ticker VARCHAR(50),
            action VARCHAR(20),
            side VARCHAR(10),
            entry_price REAL,
            entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exit_price REAL,
            exit_time TIMESTAMP,
            quantity INTEGER DEFAULT 1,
            status VARCHAR(20) DEFAULT 'open',
            tp_price REAL,
            sl_price REAL,
            tp_order_id VARCHAR(100),
            sl_order_id VARCHAR(100),
            pnl REAL,
            pnl_ticks REAL,
            exit_reason VARCHAR(50),
            broker_order_id VARCHAR(100),
            broker_strategy_id VARCHAR(100),
            broker_fill_price REAL,
            broker_managed_tp_sl BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorder_positions (
            id SERIAL PRIMARY KEY,
            recorder_id INTEGER,
            ticker VARCHAR(50),
            side VARCHAR(10),
            total_quantity INTEGER DEFAULT 0,
            fills TEXT,
            avg_entry_price REAL,
            realized_pnl REAL DEFAULT 0,
            unrealized_pnl REAL DEFAULT 0,
            worst_unrealized_pnl REAL DEFAULT 0,
            exit_price REAL,
            exit_time TIMESTAMP,
            status VARCHAR(20) DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            recorder_id INTEGER,
            raw_data TEXT,
            action VARCHAR(20),
            ticker VARCHAR(50),
            price REAL,
            processed BOOLEAN DEFAULT FALSE,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logger.info("✅ PostgreSQL tables created successfully!")

def init_sqlite():
    """Initialize SQLite tables (for local dev)."""
    import sqlite3
    
    db_path = 'just_trades.db'
    if os.path.exists(db_path):
        logger.info(f"SQLite database exists: {db_path}")
        return
    
    logger.info(f"Creating SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    # Tables would be created here...
    conn.close()

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 50)
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        init_postgres()
    else:
        init_sqlite()
    
    logger.info("Done!")
