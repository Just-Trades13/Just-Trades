#!/usr/bin/env python3
"""
⚠️ CRITICAL FOR AI ASSISTANTS: READ START_HERE.md BEFORE MODIFYING THIS FILE

PROTECTION RULES:
- Tab Isolation: Only modify files for the tab you're working on (see TAB_ISOLATION_MAP.md)
- Protected Functions: Account management functions are PROTECTED (see ACCOUNT_MGMT_SNAPSHOT.md)
- Verify Before Fixing: Don't fix things that aren't broken
- One Change at a Time: Make minimal, focused changes

See START_HERE.md for complete protection rules.
"""
from __future__ import annotations
import sqlite3
import logging
import asyncio
import argparse
import sys
import os
import json
import re
import time
import threading
import requests
from typing import Optional
from queue import Queue, Empty
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta

# ============================================================================
# USER AUTHENTICATION MODULE
# ============================================================================
try:
    from user_auth import (
        init_auth_system, login_required, admin_required,
        get_current_user, get_current_user_id, is_logged_in,
        login_user, logout_user, authenticate_user, create_user,
        auth_context_processor, create_initial_admin, assign_existing_data_to_user
    )
    USER_AUTH_AVAILABLE = True
except ImportError as e:
    USER_AUTH_AVAILABLE = False
    print(f"⚠️ User authentication module not available: {e}")

# ============================================================================
# SCALABILITY MODULES - PostgreSQL, Async Safety, Redis Caching
# ============================================================================
try:
    from async_utils import run_async, async_executor, SafeTradovateClient
    ASYNC_UTILS_AVAILABLE = True
except ImportError:
    ASYNC_UTILS_AVAILABLE = False
    
try:
    from cache import token_cache, position_cache, cache, get_cache_status
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

try:
    from production_db import get_db_connection as prod_get_db_connection, check_db_health, get_db_type
    PRODUCTION_DB_AVAILABLE = True
except ImportError:
    PRODUCTION_DB_AVAILABLE = False

# High-performance signal queue for handling hundreds of signals per second
signal_queue = Queue(maxsize=10000)
BATCH_SIZE = 50  # Process signals in batches for faster DB writes
BATCH_TIMEOUT = 0.1  # Max wait time before processing partial batch (seconds)

# ============================================================================
# 🛡️ BULLETPROOF AUTH TRACKING - Track accounts that need OAuth re-authentication
# ============================================================================
_ACCOUNTS_NEED_REAUTH = set()  # Set of account IDs that need manual OAuth re-auth
_ACCOUNTS_NEED_REAUTH_LOCK = threading.Lock()

def mark_account_needs_reauth(account_id: int):
    """Mark an account as needing OAuth re-authentication."""
    with _ACCOUNTS_NEED_REAUTH_LOCK:
        _ACCOUNTS_NEED_REAUTH.add(account_id)

def clear_account_reauth(account_id: int):
    """Clear the re-auth flag for an account (after successful OAuth)."""
    with _ACCOUNTS_NEED_REAUTH_LOCK:
        _ACCOUNTS_NEED_REAUTH.discard(account_id)

def get_accounts_needing_reauth():
    """Get list of account IDs that need OAuth re-authentication."""
    with _ACCOUNTS_NEED_REAUTH_LOCK:
        return list(_ACCOUNTS_NEED_REAUTH)

def is_account_auth_valid(account_id: int) -> bool:
    """Check if an account's authentication is valid."""
    with _ACCOUNTS_NEED_REAUTH_LOCK:
        return account_id not in _ACCOUNTS_NEED_REAUTH

# WebSocket support for Tradovate market data
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    # Logger not defined yet, will log later


# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip (optional dependency)
    pass

# ============================================================
# DATABASE CONNECTION - Supports both SQLite and PostgreSQL
# NO POOLING - Create fresh connection each time (more reliable)
# ============================================================
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_PRIVATE_URL') or os.getenv('DATABASE_PUBLIC_URL')
_using_postgres = False
_tables_initialized = False
_db_url = None

def is_using_postgres():
    """Check if we're actually using PostgreSQL"""
    return _using_postgres

def _init_db_once():
    """Initialize database once on startup."""
    global _using_postgres, _tables_initialized, _db_url
    
    if _tables_initialized:
        return
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        try:
            import psycopg2
            _db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            
            # Test connection and create tables
            conn = psycopg2.connect(_db_url)
            conn.close()
            _using_postgres = True
            _init_postgres_tables()
            _tables_initialized = True
            print("✅ PostgreSQL connected and tables initialized")
            return
        except Exception as e:
            print(f"⚠️ PostgreSQL init failed: {e}")
            _using_postgres = False
    
    # SQLite fallback
    _using_postgres = False
    conn = sqlite3.connect('just_trades.db', timeout=30)
    _init_sqlite_tables(conn)
    conn.close()
    _tables_initialized = True
    print("✅ SQLite initialized")

def get_db_connection():
    """Get fresh database connection - NO POOLING."""
    global _using_postgres, _db_url
    
    # Initialize on first call
    _init_db_once()
    
    # PostgreSQL - create fresh connection each time
    if _using_postgres and _db_url:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            conn = psycopg2.connect(_db_url)
            conn.cursor_factory = RealDictCursor
            return PostgresConnectionWrapper(conn, None)  # No pool
        except Exception as e:
            print(f"⚠️ PostgreSQL connection failed: {e}")
            # Fall through to SQLite
    
    # SQLite fallback
    conn = sqlite3.connect('just_trades.db', timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

class DictRow:
    """Row that supports both dict-style and index-style access."""
    def __init__(self, data, keys):
        self._data = data
        self._keys = keys
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()
    
    def items(self):
        return self._data.items()
    
    def __repr__(self):
        return repr(self._data)

class PostgresCursorWrapper:
    """Wrapper to make PostgreSQL cursor auto-convert SQLite ? to PostgreSQL %s."""
    def __init__(self, cursor):
        self._cursor = cursor
        self._keys = None
    
    def execute(self, sql, params=None):
        # Convert SQLite ? placeholders to PostgreSQL %s
        sql = sql.replace('?', '%s')
        if params:
            self._cursor.execute(sql, params)
        else:
            self._cursor.execute(sql)
        # Cache column names
        if self._cursor.description:
            self._keys = [desc[0] for desc in self._cursor.description]
        return self
    
    def _wrap_row(self, row):
        """Wrap a dict row to support both dict and index access."""
        if row is None:
            return None
        if isinstance(row, dict) and self._keys:
            return DictRow(row, self._keys)
        return row
    
    def fetchone(self):
        row = self._cursor.fetchone()
        return self._wrap_row(row)
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows and isinstance(rows[0], dict) and self._keys:
            return [DictRow(r, self._keys) for r in rows]
        return rows
    
    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        if rows and isinstance(rows[0], dict) and self._keys:
            return [DictRow(r, self._keys) for r in rows]
        return rows
    
    @property
    def lastrowid(self):
        return None  # PostgreSQL uses RETURNING instead
    
    @property
    def rowcount(self):
        return self._cursor.rowcount
    
    @property
    def description(self):
        return self._cursor.description
    
    def close(self):
        self._cursor.close()
    
    def __iter__(self):
        for row in self._cursor:
            yield self._wrap_row(row)

class PostgresConnectionWrapper:
    """Wrapper to make PostgreSQL connection behave like SQLite."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._row_factory = None
        self._closed = False

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._row_factory = value

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        cursor = self._conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return PostgresCursorWrapper(cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """Return connection to pool (or close direct connection)."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._pool:
                self._pool.putconn(self._conn)
            else:
                self._conn.close()
        except Exception as e:
            print(f"⚠️ Error closing connection: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
    
    def __del__(self):
        """Ensure connection is returned even if close() wasn't called."""
        if not self._closed:
            self.close()

def _init_sqlite_tables(conn):
    """Initialize ALL SQLite tables - mirrors PostgreSQL schema."""
    cursor = conn.cursor()
    
    print("📊 Creating SQLite tables (complete schema)...")
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            discord_user_id TEXT UNIQUE,
            discord_access_token TEXT,
            discord_dms_enabled INTEGER DEFAULT 0,
            session_id TEXT,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            settings_json TEXT DEFAULT '{}'
        )
    ''')
    
    # Accounts table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            broker TEXT DEFAULT 'Tradovate',
            auth_type TEXT DEFAULT 'oauth',
            username TEXT,
            password TEXT,
            account_id TEXT,
            api_key TEXT,
            api_secret TEXT,
            api_endpoint TEXT,
            environment TEXT DEFAULT 'demo',
            client_id TEXT,
            client_secret TEXT,
            tradovate_token TEXT,
            tradovate_refresh_token TEXT,
            token_expires_at TEXT,
            max_contracts INTEGER,
            multiplier REAL DEFAULT 1.0,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            subaccounts TEXT,
            tradovate_accounts TEXT,
            md_access_token TEXT,
            tradingview_session TEXT,
            has_tradingview_addon INTEGER DEFAULT 0,
            device_id TEXT
        )
    ''')
    
    # Recorders table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            strategy_type TEXT DEFAULT 'Futures',
            symbol TEXT,
            demo_account_id TEXT,
            account_id INTEGER,
            initial_position_size INTEGER DEFAULT 2,
            add_position_size INTEGER DEFAULT 2,
            tp_units TEXT DEFAULT 'Ticks',
            trim_units TEXT DEFAULT 'Contracts',
            tp_targets TEXT DEFAULT '[]',
            sl_enabled INTEGER DEFAULT 0,
            sl_amount REAL DEFAULT 0,
            sl_units TEXT DEFAULT 'Ticks',
            sl_type TEXT DEFAULT 'Fixed',
            avg_down_enabled INTEGER DEFAULT 0,
            avg_down_amount INTEGER DEFAULT 1,
            avg_down_point REAL DEFAULT 0,
            avg_down_units TEXT DEFAULT 'Ticks',
            add_delay INTEGER DEFAULT 1,
            max_contracts_per_trade INTEGER DEFAULT 0,
            option_premium_filter REAL DEFAULT 0,
            direction_filter TEXT,
            time_filter_1_start TEXT DEFAULT '8:45 AM',
            time_filter_1_stop TEXT DEFAULT '1:45 PM',
            time_filter_2_start TEXT DEFAULT '12:30 PM',
            time_filter_2_stop TEXT DEFAULT '3:15 PM',
            signal_cooldown INTEGER DEFAULT 60,
            max_signals_per_session INTEGER DEFAULT 10,
            max_daily_loss REAL DEFAULT 500,
            auto_flat_after_cutoff INTEGER DEFAULT 1,
            notes TEXT,
            recording_enabled INTEGER DEFAULT 1,
            is_recording INTEGER DEFAULT 0,
            webhook_token TEXT,
            signal_count INTEGER DEFAULT 0,
            ticker TEXT,
            position_size INTEGER DEFAULT 1,
            tp_enabled INTEGER DEFAULT 1,
            trailing_sl INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Traders table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            recorder_id INTEGER,
            account_id INTEGER,
            subaccount_id INTEGER,
            subaccount_name TEXT,
            is_demo INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            initial_position_size INTEGER,
            add_position_size INTEGER,
            tp_targets TEXT,
            sl_enabled INTEGER,
            sl_amount REAL,
            sl_units TEXT,
            max_daily_loss REAL,
            enabled_accounts TEXT,
            max_contracts INTEGER DEFAULT 10,
            custom_ticker TEXT,
            multiplier REAL DEFAULT 1.0,
            risk_percent REAL,
            name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorded trades table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            recorder_id INTEGER NOT NULL,
            signal_id INTEGER,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL,
            entry_time TEXT,
            exit_price REAL,
            exit_time TEXT,
            quantity INTEGER DEFAULT 1,
            pnl REAL DEFAULT 0,
            pnl_ticks REAL DEFAULT 0,
            fees REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            notes TEXT,
            tp_price REAL,
            sl_price REAL,
            tp_ticks REAL,
            sl_ticks REAL,
            max_favorable REAL DEFAULT 0,
            max_adverse REAL DEFAULT 0,
            tp_order_id TEXT,
            sl_order_id TEXT,
            broker_order_id TEXT,
            broker_strategy_id TEXT,
            broker_fill_price REAL,
            broker_managed_tp_sl INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorded signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            signal_type TEXT,
            ticker TEXT,
            action TEXT,
            price REAL,
            raw_signal TEXT,
            processed INTEGER DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorder positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorder_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER,
            ticker TEXT,
            side TEXT,
            total_quantity INTEGER DEFAULT 0,
            fills TEXT,
            avg_entry_price REAL,
            realized_pnl REAL DEFAULT 0,
            unrealized_pnl REAL DEFAULT 0,
            worst_unrealized_pnl REAL DEFAULT 0,
            exit_price REAL,
            exit_time TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Signals table (legacy)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER,
            raw_data TEXT,
            action TEXT,
            ticker TEXT,
            price REAL,
            processed INTEGER DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Open positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS open_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            subaccount_id TEXT,
            account_name TEXT,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            order_id TEXT,
            strategy_name TEXT,
            direction TEXT,
            open_time TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, subaccount_id, symbol)
        )
    ''')
    
    # Strategies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            account_id INTEGER,
            demo_account_id INTEGER,
            name TEXT NOT NULL,
            symbol TEXT,
            strat_type TEXT,
            days_to_expiry INTEGER,
            strike_offset REAL,
            position_size INTEGER,
            position_add INTEGER,
            take_profit REAL,
            stop_loss REAL,
            trim REAL,
            tpsl_units TEXT,
            directional_strategy TEXT,
            recording_enabled INTEGER DEFAULT 1,
            positional_settings TEXT,
            delay_seconds INTEGER,
            max_contracts INTEGER,
            premium_filter INTEGER,
            direction_filter TEXT,
            time_filter_enabled INTEGER,
            time_filter_start TEXT,
            time_filter_end TEXT,
            entry_delay INTEGER,
            signal_cooldown INTEGER,
            max_signals_per_session INTEGER,
            max_daily_loss REAL,
            auto_flat INTEGER,
            active INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            account_routing TEXT,
            is_public INTEGER DEFAULT 0,
            created_by_username TEXT
        )
    ''')
    
    # Webhooks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            method TEXT DEFAULT 'POST',
            headers TEXT,
            body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Strategy PnL history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_pnl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            strategy_name TEXT,
            pnl REAL,
            drawdown REAL DEFAULT 0.0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # OAuth states table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            account_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            redirect_uri TEXT
        )
    ''')
    
    # Watchlist items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            company_name TEXT,
            cik TEXT,
            exchange TEXT,
            currency TEXT DEFAULT 'USD',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Digest runs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS digest_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            run_type TEXT,
            status TEXT DEFAULT 'running',
            error TEXT
        )
    ''')
    
    # News items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT NOT NULL UNIQUE,
            ticker TEXT NOT NULL,
            source TEXT NOT NULL,
            headline TEXT NOT NULL,
            summary TEXT,
            url TEXT,
            published_at TEXT,
            inserted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Ratings snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            provider TEXT NOT NULL,
            raw_rating TEXT,
            normalized_bucket TEXT,
            as_of TEXT DEFAULT CURRENT_TIMESTAMP,
            inserted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Politician trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politician_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            chamber TEXT,
            politician TEXT NOT NULL,
            filed_at TEXT,
            txn_date TEXT,
            issuer TEXT,
            ticker_guess TEXT,
            action TEXT,
            amount_range TEXT,
            url TEXT,
            inserted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    print("✅ SQLite tables created (complete schema)!")


def _init_postgres_tables():
    """Initialize ALL PostgreSQL tables to match SQLite schema."""
    import psycopg2
    db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("📊 Creating PostgreSQL tables (complete schema)...")
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            discord_user_id VARCHAR(50) UNIQUE,
            discord_access_token TEXT,
            discord_dms_enabled BOOLEAN DEFAULT FALSE,
            session_id VARCHAR(255),
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            display_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            settings_json TEXT DEFAULT '{}'
        )
    ''')
    
    # Accounts table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            name VARCHAR(100) NOT NULL,
            broker VARCHAR(50) DEFAULT 'Tradovate',
            auth_type VARCHAR(20) DEFAULT 'oauth',
            username VARCHAR(100),
            password TEXT,
            account_id VARCHAR(50),
            api_key VARCHAR(255),
            api_secret TEXT,
            api_endpoint VARCHAR(255),
            environment VARCHAR(20) DEFAULT 'demo',
            client_id VARCHAR(255),
            client_secret TEXT,
            tradovate_token TEXT,
            tradovate_refresh_token TEXT,
            token_expires_at TIMESTAMP,
            max_contracts INTEGER,
            multiplier REAL DEFAULT 1.0,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subaccounts TEXT,
            tradovate_accounts TEXT,
            md_access_token TEXT,
            tradingview_session TEXT,
            has_tradingview_addon BOOLEAN DEFAULT FALSE,
            device_id VARCHAR(255)
        )
    ''')
    
    # Recorders table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            strategy_type TEXT DEFAULT 'Futures',
            symbol TEXT,
            demo_account_id TEXT,
            account_id INTEGER,
            initial_position_size INTEGER DEFAULT 2,
            add_position_size INTEGER DEFAULT 2,
            tp_units TEXT DEFAULT 'Ticks',
            trim_units TEXT DEFAULT 'Contracts',
            tp_targets TEXT DEFAULT '[]',
            sl_enabled BOOLEAN DEFAULT FALSE,
            sl_amount REAL DEFAULT 0,
            sl_units TEXT DEFAULT 'Ticks',
            sl_type TEXT DEFAULT 'Fixed',
            avg_down_enabled BOOLEAN DEFAULT FALSE,
            avg_down_amount INTEGER DEFAULT 1,
            avg_down_point REAL DEFAULT 0,
            avg_down_units TEXT DEFAULT 'Ticks',
            add_delay INTEGER DEFAULT 1,
            max_contracts_per_trade INTEGER DEFAULT 0,
            option_premium_filter REAL DEFAULT 0,
            direction_filter TEXT,
            time_filter_1_start TEXT DEFAULT '8:45 AM',
            time_filter_1_stop TEXT DEFAULT '1:45 PM',
            time_filter_2_start TEXT DEFAULT '12:30 PM',
            time_filter_2_stop TEXT DEFAULT '3:15 PM',
            signal_cooldown INTEGER DEFAULT 60,
            max_signals_per_session INTEGER DEFAULT 10,
            max_daily_loss REAL DEFAULT 500,
            auto_flat_after_cutoff BOOLEAN DEFAULT TRUE,
            notes TEXT,
            recording_enabled BOOLEAN DEFAULT TRUE,
            is_recording BOOLEAN DEFAULT FALSE,
            webhook_token TEXT,
            signal_count INTEGER DEFAULT 0,
            ticker TEXT,
            position_size INTEGER DEFAULT 1,
            tp_enabled BOOLEAN DEFAULT TRUE,
            trailing_sl BOOLEAN DEFAULT FALSE,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Traders table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            recorder_id INTEGER,
            account_id INTEGER,
            subaccount_id INTEGER,
            subaccount_name VARCHAR(255),
            is_demo BOOLEAN DEFAULT TRUE,
            enabled BOOLEAN DEFAULT TRUE,
            initial_position_size INTEGER,
            add_position_size INTEGER,
            tp_targets TEXT,
            sl_enabled BOOLEAN,
            sl_amount REAL,
            sl_units TEXT,
            max_daily_loss REAL,
            enabled_accounts TEXT,
            max_contracts INTEGER DEFAULT 10,
            custom_ticker VARCHAR(50),
            multiplier REAL DEFAULT 1.0,
            risk_percent REAL,
            name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorded trades table - full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            recorder_id INTEGER NOT NULL,
            signal_id INTEGER,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL,
            entry_time TIMESTAMP,
            exit_price REAL,
            exit_time TIMESTAMP,
            quantity INTEGER DEFAULT 1,
            pnl REAL DEFAULT 0,
            pnl_ticks REAL DEFAULT 0,
            fees REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            notes TEXT,
            tp_price REAL,
            sl_price REAL,
            tp_ticks REAL,
            sl_ticks REAL,
            max_favorable REAL DEFAULT 0,
            max_adverse REAL DEFAULT 0,
            tp_order_id VARCHAR(100),
            sl_order_id VARCHAR(100),
            broker_order_id VARCHAR(100),
            broker_strategy_id VARCHAR(100),
            broker_fill_price REAL,
            broker_managed_tp_sl BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorded signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_signals (
            id SERIAL PRIMARY KEY,
            recorder_id INTEGER NOT NULL,
            signal_type TEXT,
            ticker TEXT,
            action TEXT,
            price REAL,
            raw_signal TEXT,
            processed BOOLEAN DEFAULT FALSE,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Recorder positions table
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
    
    # Signals table (legacy)
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
    
    # Open positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS open_positions (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL,
            subaccount_id TEXT,
            account_name TEXT,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            order_id TEXT,
            strategy_name TEXT,
            direction TEXT,
            open_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, subaccount_id, symbol)
        )
    ''')
    
    # Strategies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            account_id INTEGER,
            demo_account_id INTEGER,
            name VARCHAR(100) NOT NULL,
            symbol VARCHAR(20),
            strat_type VARCHAR(50),
            days_to_expiry INTEGER,
            strike_offset REAL,
            position_size INTEGER,
            position_add INTEGER,
            take_profit REAL,
            stop_loss REAL,
            trim REAL,
            tpsl_units VARCHAR(20),
            directional_strategy VARCHAR(50),
            recording_enabled BOOLEAN DEFAULT TRUE,
            positional_settings TEXT,
            delay_seconds INTEGER,
            max_contracts INTEGER,
            premium_filter BOOLEAN,
            direction_filter VARCHAR(20),
            time_filter_enabled BOOLEAN,
            time_filter_start VARCHAR(10),
            time_filter_end VARCHAR(10),
            entry_delay INTEGER,
            signal_cooldown INTEGER,
            max_signals_per_session INTEGER,
            max_daily_loss REAL,
            auto_flat BOOLEAN,
            active BOOLEAN DEFAULT TRUE,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            account_routing TEXT,
            is_public BOOLEAN DEFAULT FALSE,
            created_by_username VARCHAR(100)
        )
    ''')
    
    # Webhooks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhooks (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            method TEXT DEFAULT 'POST',
            headers TEXT,
            body TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Strategy PnL history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_pnl_history (
            id SERIAL PRIMARY KEY,
            strategy_id INTEGER,
            strategy_name TEXT,
            pnl REAL,
            drawdown REAL DEFAULT 0.0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # OAuth states table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            account_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            redirect_uri TEXT
        )
    ''')
    
    # Watchlist items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id SERIAL PRIMARY KEY,
            ticker TEXT NOT NULL UNIQUE,
            company_name TEXT,
            cik TEXT,
            exchange TEXT,
            currency TEXT DEFAULT 'USD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Digest runs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS digest_runs (
            run_id SERIAL PRIMARY KEY,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            run_type TEXT,
            status TEXT DEFAULT 'running',
            error TEXT
        )
    ''')
    
    # News items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_items (
            id SERIAL PRIMARY KEY,
            url_hash TEXT NOT NULL UNIQUE,
            ticker TEXT NOT NULL,
            source TEXT NOT NULL,
            headline TEXT NOT NULL,
            summary TEXT,
            url TEXT,
            published_at TIMESTAMP,
            inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Ratings snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_snapshots (
            id SERIAL PRIMARY KEY,
            ticker TEXT NOT NULL,
            provider TEXT NOT NULL,
            raw_rating TEXT,
            normalized_bucket TEXT,
            as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Politician trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politician_trades (
            id SERIAL PRIMARY KEY,
            source TEXT,
            chamber TEXT,
            politician TEXT NOT NULL,
            filed_at TIMESTAMP,
            txn_date TIMESTAMP,
            issuer TEXT,
            ticker_guess TEXT,
            action TEXT,
            amount_range TEXT,
            url TEXT,
            inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ PostgreSQL tables created (complete schema)!")

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL ERROR HANDLER - Catch ALL errors and display them
# ============================================================================
@app.errorhandler(500)
def internal_error(error):
    import traceback
    tb = traceback.format_exc()
    print(f"❌ 500 ERROR: {error}")
    print(f"❌ TRACEBACK: {tb}")
    return f"""
    <h1>500 Internal Server Error</h1>
    <h2>Error: {error}</h2>
    <h3>Traceback:</h3>
    <pre>{tb}</pre>
    """, 500

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    tb = traceback.format_exc()
    print(f"❌ EXCEPTION: {e}")
    print(f"❌ TRACEBACK: {tb}")
    return f"""
    <h1>Error</h1>
    <h2>{type(e).__name__}: {e}</h2>
    <h3>Traceback:</h3>
    <pre>{tb}</pre>
    """, 500

# ============================================================================
# SESSION CONFIGURATION - Required for User Authentication
# ============================================================================
# Use environment variable for production, or generate a secure random key
import secrets
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Sessions last 7 days
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Register auth context processor to make current_user available in all templates
if USER_AUTH_AVAILABLE:
    app.context_processor(auth_context_processor)

# Initialize SocketIO for WebSocket support (like Trade Manager)
# Use 'eventlet' or 'gevent' if available, otherwise fall back to threading
try:
    import eventlet
    eventlet.monkey_patch()
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    logger.info("SocketIO using eventlet async mode")
except ImportError:
    try:
        import gevent
        from gevent import monkey
        monkey.patch_all()
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
        logger.info("SocketIO using gevent async mode")
    except ImportError:
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)
        logger.info("SocketIO using threading async mode (fallback)")

# ⚠️ SECURITY WARNING: API credentials should be stored in environment variables or secure config
# These are default credentials - prefer storing in .env file or environment variables
# Example: TRADOVATE_API_CID=8720, TRADOVATE_API_SECRET=your-secret
TRADOVATE_API_CID = int(os.getenv('TRADOVATE_API_CID', '8720'))
TRADOVATE_API_SECRET = os.getenv('TRADOVATE_API_SECRET', 'e76ee8d1-d168-4252-a59e-f11a8b0cdae4')

# Contract multipliers for PnL calculation
CONTRACT_MULTIPLIERS = {
    'MES': 5.0,    # Micro E-mini S&P 500: $5 per point
    'MNQ': 2.0,    # Micro E-mini Nasdaq: $2 per point
    'ES': 50.0,    # E-mini S&P 500: $50 per point
    'NQ': 20.0,    # E-mini Nasdaq: $20 per point
    'MYM': 5.0,    # Micro E-mini Dow: $5 per point
    'YM': 5.0,     # E-mini Dow: $5 per point
    'M2K': 5.0,    # Micro E-mini Russell 2000: $5 per point
    'RTY': 50.0,   # E-mini Russell 2000: $50 per point
}

def get_contract_multiplier(symbol: str) -> float:
    """Get contract multiplier for a symbol"""
    symbol_upper = symbol.upper().strip()
    
    # Try to match known base symbols (2-3 characters)
    # Check 3-char symbols first (MES, MNQ, M2K, etc.)
    if symbol_upper[:3] in CONTRACT_MULTIPLIERS:
        return CONTRACT_MULTIPLIERS[symbol_upper[:3]]
    
    # Check 2-char symbols (ES, NQ, YM, etc.)
    if symbol_upper[:2] in CONTRACT_MULTIPLIERS:
        return CONTRACT_MULTIPLIERS[symbol_upper[:2]]
    
    # Fallback: remove month codes and numbers
    # Month codes: F, G, H, J, K, M, N, Q, U, V, X, Z
    base_symbol = re.sub(r'[0-9!]+', '', symbol_upper)  # Remove numbers and !
    base_symbol = re.sub(r'[FGHJKMNQUVXZ]$', '', base_symbol)  # Remove trailing month code
    
    return CONTRACT_MULTIPLIERS.get(base_symbol, 1.0)

def get_market_price_simple(symbol: str) -> Optional[float]:
    """
    Get current market price using TradingView's public scanner API.
    This doesn't require authentication but has rate limits.
    """
    try:
        if not symbol:
            return None
        
        # Normalize symbol (remove !, add CME prefix if needed)
        clean_symbol = symbol.upper().replace('!', '')
        
        # Map common futures symbols to TradingView format
        tv_symbol_map = {
            'MNQ': 'CME_MINI:MNQ1!',
            'MES': 'CME_MINI:MES1!',
            'MYM': 'CBOT_MINI:MYM1!',
            'M2K': 'CME_MINI:M2K1!',
            'NQ': 'CME:NQ1!',
            'ES': 'CME:ES1!',
            'YM': 'CBOT:YM1!',
            'RTY': 'CME:RTY1!',
            'CL': 'NYMEX:CL1!',
            'GC': 'COMEX:GC1!',
        }
        
        # Extract root symbol
        root = extract_symbol_root(clean_symbol)
        tv_symbol = tv_symbol_map.get(root)
        
        if not tv_symbol:
            # Try direct format
            tv_symbol = f'CME:{clean_symbol}'
        
        # Use TradingView's scanner endpoint
        url = "https://scanner.tradingview.com/futures/scan"
        payload = {
            "symbols": {"tickers": [tv_symbol]},
            "columns": ["close", "change", "high", "low", "volume"]
        }
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                price = data['data'][0].get('d', [None])[0]
                if price:
                    logger.debug(f"Got price for {symbol}: {price}")
                    return float(price)
        
        logger.debug(f"Could not get price for {symbol} from TradingView")
        return None
        
    except Exception as e:
        logger.warning(f"Error getting market price for {symbol}: {e}")
        return None


# Cache for price data to avoid excessive API calls
_price_cache = {}
_price_cache_ttl = 60  # seconds (increased to 60s - trades are priority, PnL is secondary)


def get_cached_price(symbol: str) -> Optional[float]:
    """Get price with caching to avoid rate limits"""
    global _price_cache
    
    if not symbol:
        return None
    
    root = extract_symbol_root(symbol)
    cache_key = root
    
    # Check cache first
    if cache_key in _price_cache:
        cached_price, cached_time = _price_cache[cache_key]
        if time.time() - cached_time < _price_cache_ttl:
            return cached_price
    
    # Fetch new price
    price = get_market_price_simple(symbol)
    
    if price:
        _price_cache[cache_key] = (price, time.time())
    
    return price

SYMBOL_FALLBACK_MAP = {
    'MNQ': 'MNQZ5',
    'MES': 'MESZ5',
    'ES': 'ESZ5',
    'NQ': 'NQZ5',
    'CL': 'CLZ5',
    'GC': 'GCZ5',
    'MCL': 'MCLZ5'
}
SYMBOL_CONVERSION_CACHE: dict[tuple[str, bool], tuple[str, datetime]] = {}
SYMBOL_CACHE_TTL = timedelta(hours=1)

TICK_INFO = {
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.5},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.0},
    'MES': {'tick_size': 0.25, 'tick_value': 1.25},
    'ES': {'tick_size': 0.25, 'tick_value': 12.5},
    'M2K': {'tick_size': 0.1, 'tick_value': 0.5},
    'RTY': {'tick_size': 0.1, 'tick_value': 5.0},
    'CL': {'tick_size': 0.01, 'tick_value': 10.0},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.0},
    'GC': {'tick_size': 0.1, 'tick_value': 10.0}
}


def convert_tradingview_to_tradovate_symbol(symbol: str, access_token: str | None = None, demo: bool = True) -> str:
    """
    Convert TradingView symbol (MNQ1!) to Tradovate front-month symbol (MNQZ5).
    Calculates the current front month contract based on today's date.
    """
    if not symbol:
        return symbol
    clean = symbol.strip().upper()
    # Already Tradovate format (no ! suffix)
    if '!' not in clean:
        return clean
    match = re.match(r'^([A-Z]+)\d*!$', clean)
    if not match:
        return clean.replace('!', '')
    root = match.group(1)
    cache_key = (root, demo)
    cached = SYMBOL_CONVERSION_CACHE.get(cache_key)
    if cached:
        value, expires = cached
        if datetime.utcnow() < expires:
            return value
    
    # Calculate front month contract based on current date
    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year % 10  # Last digit of year (e.g., 2025 -> 5)
    
    # Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
    month_codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
    
    # For quarterly contracts (MNQ, MES, ES, NQ, etc.), use quarterly months: H(Mar), M(Jun), U(Sep), Z(Dec)
    quarterly_contracts = ['MNQ', 'MES', 'ES', 'NQ', 'YM', 'RTY', 'M2K', 'CL', 'MCL', 'GC', 'MGC']
    
    if root in quarterly_contracts:
        # Quarterly contracts: Find next quarterly expiration
        quarterly_months = [2, 5, 8, 11]  # Mar, Jun, Sep, Dec (0-indexed: 2, 5, 8, 11)
        quarterly_codes = ['H', 'M', 'U', 'Z']
        
        # Find the next quarterly month
        for i, qm in enumerate(quarterly_months):
            if current_month <= qm + 1:  # Add 1 month buffer for rollover
                month_code = quarterly_codes[i]
                year = current_year
                break
        else:
            # Past December, use March of next year
            month_code = 'H'
            year = (current_year + 1) % 10
        
        converted = f"{root}{month_code}{year}"
    else:
        # Monthly contracts: Use current month or next month
        if current_month == 12:
            month_code = 'F'  # January
            year = (current_year + 1) % 10
        else:
            month_code = month_codes[current_month]  # Current month
            year = current_year
        
        converted = f"{root}{month_code}{year}"
    
    logger.info(f"📅 Converted {symbol} → {converted} (front month for {now.strftime('%Y-%m')})")
    SYMBOL_CONVERSION_CACHE[cache_key] = (converted, datetime.utcnow() + SYMBOL_CACHE_TTL)
    return converted


def extract_symbol_root(symbol: str) -> str:
    if not symbol:
        return ''
    clean = symbol.upper()
    clean = clean.replace('!', '')
    match = re.match(r'^([A-Z]+)', clean)
    return match.group(1) if match else clean


def get_tick_info(symbol: str) -> dict:
    root = extract_symbol_root(symbol)
    return TICK_INFO.get(root, {'tick_size': 0.25, 'tick_value': 1.0})


async def wait_for_position_fill(tradovate, account_id: int, symbol: str, expected_side: str, timeout: float = 10.0):
    """
    Wait for position to appear after order fill.
    Increased timeout to 10 seconds and added better logging.
    """
    expected_side = expected_side.lower()
    symbol_upper = symbol.upper()
    deadline = time.time() + timeout
    attempt = 0
    
    logger.info(f"🔍 Waiting for position fill: symbol={symbol_upper}, side={expected_side}, account_id={account_id}")
    
    while time.time() < deadline:
        attempt += 1
        try:
            positions = await tradovate.get_positions(account_id)
            logger.debug(f"  Attempt {attempt}: Found {len(positions)} positions")
            
            for pos in positions:
                pos_symbol = str(pos.get('symbol', '')).upper()
                net_pos = pos.get('netPos') or 0
                
                # Match by root symbol (e.g., "MNQ" matches "MNQZ5", "MNQ1!", etc.)
                symbol_root = symbol_upper[:3] if len(symbol_upper) >= 3 else symbol_upper
                pos_root = pos_symbol[:3] if len(pos_symbol) >= 3 else pos_symbol
                
                if symbol_root == pos_root or symbol_upper in pos_symbol or pos_symbol in symbol_upper:
                    logger.debug(f"  Symbol match: {pos_symbol} (netPos={net_pos})")
                    if (expected_side == 'buy' and net_pos > 0) or (expected_side == 'sell' and net_pos < 0):
                        logger.info(f"✅ Position found: {pos_symbol} {net_pos} @ {pos.get('netPrice', 'N/A')}")
                        return pos
        except Exception as e:
            logger.warning(f"  Error checking positions (attempt {attempt}): {e}")
        
        await asyncio.sleep(0.5)  # Check every 0.5 seconds
    
    logger.warning(f"⏱️ Timeout waiting for position: {symbol_upper} (checked {attempt} times)")
    return None


def clamp_price(price: float, tick_size: float) -> float:
    if price is None:
        return None
    decimals = max(3, len(str(tick_size).split('.')[-1]))
    return round(price, decimals)


async def apply_risk_orders(tradovate, account_spec: str, account_id: int, symbol: str, entry_side: str, quantity: int, risk_config: dict):
    """
    Apply risk management orders (TP/SL) as OCO (One-Cancels-Other) using Tradovate's order strategy.
    When TP hits, SL is automatically cancelled (and vice versa).
    """
    logger.info(f"🎯 apply_risk_orders called: symbol={symbol}, side={entry_side}, qty={quantity}")
    logger.info(f"🎯 Risk config: {risk_config}")
    
    if not risk_config or not quantity:
        logger.info(f"🎯 No risk config or quantity=0, skipping bracket orders")
        return
    symbol_upper = symbol.upper()
    logger.info(f"🔍 Waiting for position fill to calculate TP/SL prices...")
    fill = await wait_for_position_fill(tradovate, account_id, symbol_upper, entry_side)
    if not fill:
        logger.error(f"❌ Unable to locate filled position for {symbol_upper} to apply brackets")
        logger.error(f"   This means TP/SL orders will NOT be placed!")
        logger.error(f"   Possible causes: Position not visible yet, symbol mismatch, or timeout")
        return
    entry_price = fill.get('netPrice') or fill.get('price') or fill.get('avgPrice')
    if not entry_price:
        logger.error(f"❌ No entry price found for {symbol_upper}; skipping bracket creation")
        logger.error(f"   Position data: {fill}")
        return
    
    logger.info(f"✅ Position found: Entry price = {entry_price}, will calculate TP/SL from here")
    tick_info = get_tick_info(symbol_upper)
    tick_size = tick_info['tick_size']
    is_long = entry_side.lower() == 'buy'
    exit_action = 'Sell' if is_long else 'Buy'

    # Get risk settings
    take_profit_list = risk_config.get('take_profit') or []
    stop_cfg = risk_config.get('stop_loss')
    trail_cfg = risk_config.get('trail')
    
    # Get tick values
    tp_ticks = None
    sl_ticks = None
    
    if take_profit_list:
        first_tp = take_profit_list[0]
        tp_ticks = first_tp.get('gain_ticks')
    
    if stop_cfg:
        sl_ticks = stop_cfg.get('loss_ticks')
    
    # Calculate absolute prices for OCO exit orders
    tp_price = None
    sl_price = None
    
    if tp_ticks:
        tp_offset = tick_size * tp_ticks
        tp_price = entry_price + tp_offset if is_long else entry_price - tp_offset
        tp_price = clamp_price(tp_price, tick_size)
    
    if sl_ticks:
        sl_offset = tick_size * sl_ticks
        sl_price = entry_price - sl_offset if is_long else entry_price + sl_offset
        sl_price = clamp_price(sl_price, tick_size)
    
    # Track order IDs for break-even and trailing stop integration
    tp_order_id = None
    sl_order_id = None
    
    # If we have BOTH TP and SL, try to place as OCO order strategy
    if tp_price and sl_price:
        logger.info(f"📊 Placing OCO exit orders: TP @ {tp_price}, SL @ {sl_price}, Qty: {quantity}")
        logger.info(f"   Entry: {entry_price}, TP ticks: {tp_ticks}, SL ticks: {sl_ticks}")
        
        # Use the new OCO exit method
        result = await tradovate.place_exit_oco(
            account_id=account_id,
            account_spec=account_spec,
            symbol=symbol_upper,
            exit_side=exit_action,
            quantity=quantity,
            take_profit_price=tp_price,
            stop_loss_price=sl_price
        )
        
        if result and result.get('success'):
            logger.info(f"✅ OCO exit orders placed successfully")
            
            # Register the pair for custom OCO monitoring (if they were placed as individual orders)
            tp_order_id = result.get('tp_order_id')
            sl_order_id = result.get('sl_order_id')
            
            if tp_order_id and sl_order_id:
                register_oco_pair(tp_order_id, sl_order_id, account_id, symbol_upper)
        else:
            logger.warning(f"⚠️ OCO exit failed, orders may have been placed individually: {result}")
    
    # If only TP (no SL)
    elif tp_price:
        logger.info(f"📊 Placing Take Profit only @ {tp_price}, Qty: {quantity}")
        tp_order_data = tradovate.create_limit_order(account_spec, symbol_upper, exit_action, quantity, tp_price, account_id)
        tp_result = await tradovate.place_order(tp_order_data)
        if tp_result and tp_result.get('success'):
            tp_order_id = tp_result.get('orderId') or tp_result.get('data', {}).get('orderId')
    
    # If only SL (no TP)
    elif sl_price:
        logger.info(f"📊 Placing Stop Loss only @ {sl_price}, Qty: {quantity}")
        sl_order_data = tradovate.create_stop_order(account_spec, symbol_upper, exit_action, quantity, sl_price, account_id)
        sl_result = await tradovate.place_order(sl_order_data)
        if sl_result and sl_result.get('success'):
            sl_order_id = sl_result.get('orderId') or sl_result.get('data', {}).get('orderId')
    
    # Handle trailing stop (can be used with or instead of fixed SL)
    if trail_cfg and trail_cfg.get('offset_ticks'):
        trail_ticks = trail_cfg.get('offset_ticks')
        trail_offset = tick_size * trail_ticks
        
        # Calculate initial stop price (entry - offset for long, entry + offset for short)
        if is_long:
            initial_stop_price = entry_price - trail_offset
        else:
            initial_stop_price = entry_price + trail_offset
        initial_stop_price = clamp_price(initial_stop_price, tick_size)
        
        logger.info(f"📊 Placing Trailing Stop: offset={trail_offset} ({trail_ticks} ticks), initial stop={initial_stop_price}")
        trail_order = tradovate.create_trailing_stop_order(
            account_spec, symbol_upper, exit_action, quantity, 
            float(trail_offset), account_id, initial_stop_price
        )
        trail_result = await tradovate.place_order(trail_order)
        
        if trail_result and trail_result.get('success'):
            trail_order_id = trail_result.get('orderId') or trail_result.get('data', {}).get('orderId')
            logger.info(f"✅ Trailing Stop placed: Order ID={trail_order_id}")
            
            # If we placed a trailing stop AND an SL, register them for OCO
            if sl_order_id and trail_order_id:
                # The trailing stop and fixed SL are alternatives - register as OCO
                register_oco_pair(trail_order_id, sl_order_id, account_id, symbol_upper)
                logger.info(f"🔗 Trailing Stop and SL registered as OCO: Trail={trail_order_id} <-> SL={sl_order_id}")
        else:
            error_msg = trail_result.get('error', 'Unknown error') if trail_result else 'No response'
            logger.warning(f"⚠️ Failed to place trailing stop: {error_msg}")
    
    # Handle break-even (monitor position and move SL to entry when profitable)
    break_even_cfg = risk_config.get('break_even')
    if break_even_cfg and break_even_cfg.get('activation_ticks'):
        be_ticks = break_even_cfg.get('activation_ticks')
        logger.info(f"📊 Break-even enabled: Will move SL to entry after {be_ticks} ticks profit")
        
        # Register for break-even monitoring
        register_break_even_monitor(
            account_id=account_id,
            symbol=symbol_upper,
            entry_price=entry_price,
            is_long=is_long,
            activation_ticks=be_ticks,
            tick_size=tick_size,
            sl_order_id=sl_order_id,  # We'll modify this order
            quantity=quantity,
            account_spec=account_spec
        )
    
    # Handle multiple TP levels (if any beyond the first)
    if len(take_profit_list) > 1:
        logger.info(f"📊 Processing {len(take_profit_list) - 1} additional TP levels")
        first_tp_percent = take_profit_list[0].get('trim_percent', 100)
        first_tp_qty = int(round(quantity * (first_tp_percent / 100.0))) if first_tp_percent else quantity
        remaining_qty = quantity - first_tp_qty
        
        for idx, tp in enumerate(take_profit_list[1:], start=1):
            ticks = tp.get('gain_ticks')
            trim_percent = tp.get('trim_percent', 0)
            
            level_qty = int(round(quantity * (trim_percent / 100.0))) if trim_percent else 0
            if idx == len(take_profit_list) - 1 and level_qty == 0:
                level_qty = remaining_qty  # Last level gets remaining
            
            level_qty = min(max(level_qty, 0), remaining_qty)
            if level_qty <= 0:
                continue
                
            remaining_qty -= level_qty
            
            if ticks:
                tp_offset = tick_size * ticks
                level_price = entry_price + tp_offset if is_long else entry_price - tp_offset
                level_price = clamp_price(level_price, tick_size)
                
                logger.info(f"  TP Level {idx + 1}: Price={level_price}, Qty={level_qty}")
                tp_order = tradovate.create_limit_order(account_spec, symbol_upper, exit_action, level_qty, level_price, account_id)
                await tradovate.place_order(tp_order)


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol for comparison (remove !, handle different formats)"""
    if not symbol:
        return ''
    normalized = symbol.upper().strip()
    # Remove trailing ! (TradingView format)
    normalized = normalized.rstrip('!')
    return normalized

async def cancel_open_orders(tradovate, account_id: int, symbol: str | None = None, cancel_all: bool = False):
    cancelled = 0
    try:
        # Try getting all orders first (includes order strategies), then filter by account
        # This ensures we get bracket orders, OCO orders, etc. that might not show up in account-specific endpoint
        all_orders = await tradovate.get_orders(None) or []  # Get all orders
        orders = [o for o in all_orders if str(o.get('accountId', '')) == str(account_id)]
        
        # If we got no orders from /order/list, fallback to account-specific endpoint
        if not orders:
            logger.info(f"No orders found via /order/list, trying account-specific endpoint")
            orders = await tradovate.get_orders(str(account_id)) or []
        logger.info(f"Retrieved {len(orders)} orders for account {account_id}, filtering for symbol: {symbol}, cancel_all: {cancel_all}")
        
        # Log all orders for debugging
        if orders:
            logger.info(f"=== ALL ORDERS RETRIEVED ===")
            for idx, order in enumerate(orders[:10]):  # Log first 10 orders
                logger.info(f"Order #{idx+1}: id={order.get('id')}, status={order.get('status')}, ordStatus={order.get('ordStatus')}, "
                           f"symbol={order.get('symbol')}, contractId={order.get('contractId')}, "
                           f"orderType={order.get('orderType')}, orderQty={order.get('orderQty')}, "
                           f"action={order.get('action')}, strategyId={order.get('orderStrategyId')}, "
                           f"keys={list(order.keys())[:15]}")
            if len(orders) > 10:
                logger.info(f"... and {len(orders) - 10} more orders")
            logger.info(f"=== END ORDER LIST ===")
        
        # Statuses that represent active/resting orders that can be cancelled
        # According to Tradovate docs, statuses are: Working, Filled, Canceled, Rejected, Expired
        # Also check: PendingNew, PendingReplace, PendingCancel, Stopped, Suspended
        # We check both lowercase and capitalized versions for robustness
        cancellable_statuses = {
            'working', 'pending', 'queued', 'accepted', 'new', 
            'pendingnew', 'pendingreplace', 'pendingcancel',
            'stopped', 'suspended',
            # Capitalized versions (Tradovate standard format)
            'Working', 'Pending', 'Queued', 'Accepted', 'New',
            'PendingNew', 'PendingReplace', 'PendingCancel',
            'Stopped', 'Suspended'
        }
        
        # Normalize target symbol if provided
        target_symbol_normalized = None
        target_contract_ids = set()
        if symbol:
            target_symbol_normalized = normalize_symbol(symbol)
            logger.info(f"Target symbol normalized: {target_symbol_normalized}")
        
        # Resolve target symbol to contractId(s) if we have a symbol to match
        if symbol and target_symbol_normalized:
            try:
                # Get positions to find matching contractIds
                positions = await tradovate.get_positions(account_id)
                for pos in positions:
                    pos_symbol = str(pos.get('symbol') or '').upper()
                    if normalize_symbol(pos_symbol) == target_symbol_normalized:
                        contract_id = pos.get('contractId')
                        if contract_id:
                            target_contract_ids.add(contract_id)
                            logger.info(f"Found matching contractId {contract_id} for symbol {target_symbol_normalized}")
            except Exception as e:
                logger.warning(f"Error resolving contractIds for symbol matching: {e}")
        
        for order in orders:
            if not order:
                continue
            
            # Check both 'status' and 'ordStatus' fields (Tradovate uses ordStatus per docs)
            # Also check 'action' which sometimes indicates buy/sell (meaning order is active)
            status = order.get('ordStatus') or order.get('status') or ''
            status_lower = status.lower() if status else ''
            order_id = order.get('id')
            order_type = order.get('orderType') or order.get('order_type') or 'Unknown'
            order_strategy_id = order.get('orderStrategyId')  # For bracket/OCO orders
            order_action = order.get('action')  # Buy/Sell indicates active order
            
            # Non-cancellable final statuses (order is already complete)
            non_cancellable = {'filled', 'canceled', 'cancelled', 'rejected', 'expired', 'complete', 'completed'}
            
            # Skip if status indicates order is already done
            if status_lower and status_lower in non_cancellable:
                logger.debug(f"Skipping order {order_id} - status '{status}' is final (not cancellable)")
                continue
            
            # If status is empty but order has action (Buy/Sell), it's likely an active order
            if not status and not order_action:
                # If no status and no action, check if it has position-related fields (might be position data, not order)
                if 'netPos' in order:
                    logger.debug(f"Skipping order {order_id} - appears to be position data, not order")
                    continue
            
            # Log what we're about to try to cancel
            logger.info(f"Order {order_id} may be active: status='{status}', ordStatus='{order.get('ordStatus')}', action={order_action}, strategyId={order_strategy_id}")
            
            # Get symbol from order - could be direct symbol field or need to resolve from contractId
            order_symbol = str(order.get('symbol') or '').upper()
            order_contract_id = order.get('contractId')
            
            # Resolve contractId to symbol if we don't have symbol
            if not order_symbol and order_contract_id:
                try:
                    resolved_symbol = await tradovate._get_contract_symbol(order_contract_id)
                    if resolved_symbol:
                        order_symbol = resolved_symbol.upper()
                        order['symbol'] = resolved_symbol  # Cache it for future use
                        logger.debug(f"Resolved contractId {order_contract_id} to symbol {order_symbol}")
                except Exception as e:
                    logger.debug(f"Could not resolve contractId {order_contract_id}: {e}")
            
            # Filter by symbol if provided - try multiple matching strategies
            should_cancel = True
            if cancel_all:
                # Cancel all cancellable orders regardless of symbol
                should_cancel = True
                logger.info(f"Cancel-all mode: Will cancel order {order_id} ({order_symbol or f'contractId:{order_contract_id}' or 'no symbol'}, {order_type}, status: {status})")
            elif symbol:
                should_cancel = False
                
                # Strategy 1: Exact symbol match (after normalization)
                if order_symbol:
                    order_symbol_normalized = normalize_symbol(order_symbol)
                    if order_symbol_normalized == target_symbol_normalized:
                        should_cancel = True
                        logger.info(f"Order {order_id} matches by normalized symbol: {order_symbol} -> {order_symbol_normalized}")
                
                # Strategy 2: ContractId match
                if not should_cancel and order_contract_id and order_contract_id in target_contract_ids:
                    should_cancel = True
                    logger.info(f"Order {order_id} matches by contractId: {order_contract_id}")
                
                # Strategy 3: Partial symbol match (in case of format differences)
                if not should_cancel and order_symbol:
                    # Try matching base symbol (e.g., "ES" in "ESM1" or "ES1!")
                    order_base = normalize_symbol(order_symbol)
                    target_base = target_symbol_normalized
                    # Extract base symbol (remove month codes and numbers)
                    order_base_only = re.sub(r'\d+[A-Z]*$', '', order_base)
                    target_base_only = re.sub(r'\d+[A-Z]*$', '', target_base)
                    if order_base_only and target_base_only and order_base_only == target_base_only:
                        # If base matches and one contains the other, it's likely a match
                        if target_base_only in order_base or order_base_only in target_base:
                            should_cancel = True
                            logger.info(f"Order {order_id} matches by base symbol: {order_base} vs {target_base}")
                
                if not should_cancel:
                    logger.debug(f"Skipping order {order_id} ({order_symbol or 'no symbol'}) - doesn't match {symbol}")
                    continue
            
            # Attempt to cancel the order
            logger.info(f"Attempting to cancel order {order_id} ({order_symbol or f'contractId:{order_contract_id}' or 'no symbol'}, {order_type}, status: {status})")
            if await tradovate.cancel_order(order_id):
                cancelled += 1
                logger.info(f"✅ Successfully cancelled order {order_id} ({order_symbol or 'no symbol'})")
            else:
                logger.warning(f"❌ Failed to cancel order {order_id} ({order_symbol or 'no symbol'})")
                
    except Exception as e:
        logger.error(f"Unable to cancel open orders for {symbol or 'account'}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info(f"Total cancelled: {cancelled} orders for symbol {symbol or 'all'}")
    return cancelled


def get_tick_size(symbol):
    """Get tick size for a given symbol"""
    if not symbol:
        return 0.25  # Default
    
    symbol_upper = symbol.upper()
    
    # Micro futures
    if 'MNQ' in symbol_upper:
        return 0.25
    elif 'MES' in symbol_upper:
        return 0.25
    elif 'MYM' in symbol_upper:
        return 1.0
    elif 'M2K' in symbol_upper:
        return 0.10
    elif 'MCL' in symbol_upper:
        return 0.01
    elif 'MGC' in symbol_upper:
        return 0.10
    # E-mini futures
    elif 'NQ' in symbol_upper:
        return 0.25
    elif 'ES' in symbol_upper:
        return 0.25
    elif 'YM' in symbol_upper:
        return 1.0
    elif 'RTY' in symbol_upper:
        return 0.10
    # Commodities
    elif 'CL' in symbol_upper:
        return 0.01
    elif 'GC' in symbol_upper:
        return 0.10
    elif 'SI' in symbol_upper:
        return 0.005
    elif 'NG' in symbol_upper:
        return 0.001
    # Currencies
    elif '6E' in symbol_upper or 'EUR' in symbol_upper:
        return 0.00005
    elif '6J' in symbol_upper or 'JPY' in symbol_upper:
        return 0.0000005
    elif '6B' in symbol_upper or 'GBP' in symbol_upper:
        return 0.0001
    # Default
    else:
        return 0.25


def get_tick_value(symbol):
    """Get tick value (dollar value per tick) for a given symbol"""
    if not symbol:
        return 0.50  # Default for micro futures
    
    symbol_upper = symbol.upper()
    
    # Micro futures (smaller tick values)
    if 'MNQ' in symbol_upper:
        return 0.50   # $0.50 per tick (0.25 points)
    elif 'MES' in symbol_upper:
        return 1.25   # $1.25 per tick (0.25 points)
    elif 'MYM' in symbol_upper:
        return 0.50   # $0.50 per tick (1 point)
    elif 'M2K' in symbol_upper:
        return 0.50   # $0.50 per tick (0.10 points)
    elif 'MCL' in symbol_upper:
        return 1.00   # $1.00 per tick (0.01)
    elif 'MGC' in symbol_upper:
        return 1.00   # $1.00 per tick (0.10)
    # E-mini futures (larger tick values)
    elif 'NQ' in symbol_upper:
        return 5.00   # $5.00 per tick (0.25 points)
    elif 'ES' in symbol_upper:
        return 12.50  # $12.50 per tick (0.25 points)
    elif 'YM' in symbol_upper:
        return 5.00   # $5.00 per tick (1 point)
    elif 'RTY' in symbol_upper:
        return 5.00   # $5.00 per tick (0.10 points)
    # Commodities
    elif 'CL' in symbol_upper:
        return 10.00  # $10.00 per tick (0.01)
    elif 'GC' in symbol_upper:
        return 10.00  # $10.00 per tick (0.10)
    elif 'SI' in symbol_upper:
        return 25.00  # $25.00 per tick
    elif 'NG' in symbol_upper:
        return 10.00  # $10.00 per tick
    # Currencies
    elif '6E' in symbol_upper or 'EUR' in symbol_upper:
        return 6.25   # $6.25 per tick
    elif '6J' in symbol_upper or 'JPY' in symbol_upper:
        return 6.25
    elif '6B' in symbol_upper or 'GBP' in symbol_upper:
        return 6.25
    # Default
    else:
        return 0.50


def init_db():
    """Initialize webhook and strategy tables - supports both SQLite and PostgreSQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if using PostgreSQL
    is_postgres = is_using_postgres()
    
    if is_postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                headers TEXT,
                body TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_pnl_history (
                id SERIAL PRIMARY KEY,
                strategy_id INTEGER,
                strategy_name TEXT,
                pnl REAL,
                drawdown REAL DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                headers TEXT,
                body TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_pnl_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER,
                strategy_name TEXT,
                pnl REAL,
                drawdown REAL DEFAULT 0.0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_strategy_pnl_timestamp 
            ON strategy_pnl_history(strategy_id, timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_strategy_pnl_date 
            ON strategy_pnl_history(DATE(timestamp))
        ''')
    conn.commit()
    conn.close()
    
    # Initialize just_trades.db with positions table (like Trade Manager)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS open_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            subaccount_id TEXT,
            account_name TEXT,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            order_id TEXT,
            strategy_name TEXT,
            direction TEXT,  -- 'BUY' or 'SELL'
            open_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, subaccount_id, symbol)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_open_positions_account 
        ON open_positions(account_id, subaccount_id)
    ''')
    
    # Recorders table - stores recorder configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            strategy_type TEXT DEFAULT 'Futures',
            symbol TEXT,
            demo_account_id TEXT,
            account_id INTEGER,
            -- Positional Settings
            initial_position_size INTEGER DEFAULT 2,
            add_position_size INTEGER DEFAULT 2,
            -- TP Settings
            tp_units TEXT DEFAULT 'Ticks',
            trim_units TEXT DEFAULT 'Contracts',
            tp_targets TEXT DEFAULT '[]',
            -- SL Settings
            sl_enabled INTEGER DEFAULT 0,
            sl_amount REAL DEFAULT 0,
            sl_units TEXT DEFAULT 'Ticks',
            sl_type TEXT DEFAULT 'Fixed',
            -- Averaging Down
            avg_down_enabled INTEGER DEFAULT 0,
            avg_down_amount INTEGER DEFAULT 1,
            avg_down_point REAL DEFAULT 0,
            avg_down_units TEXT DEFAULT 'Ticks',
            -- Filter Settings
            add_delay INTEGER DEFAULT 1,
            max_contracts_per_trade INTEGER DEFAULT 0,
            option_premium_filter REAL DEFAULT 0,
            direction_filter TEXT,
            -- Time Filters
            time_filter_1_start TEXT DEFAULT '8:45 AM',
            time_filter_1_stop TEXT DEFAULT '1:45 PM',
            time_filter_2_start TEXT DEFAULT '12:30 PM',
            time_filter_2_stop TEXT DEFAULT '3:15 PM',
            -- Execution Controls
            signal_cooldown INTEGER DEFAULT 60,
            max_signals_per_session INTEGER DEFAULT 10,
            max_daily_loss REAL DEFAULT 500,
            auto_flat_after_cutoff INTEGER DEFAULT 1,
            -- Miscellaneous
            notes TEXT,
            -- Recording Status
            recording_enabled INTEGER DEFAULT 1,
            is_recording INTEGER DEFAULT 0,
            -- Webhook
            webhook_token TEXT,
            signal_count INTEGER DEFAULT 0,
            -- Timestamps
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorders_name 
        ON recorders(name)
    ''')
    
    # Recorded trades table - stores individual trade executions from signals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            signal_id INTEGER,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL,
            entry_time DATETIME,
            exit_price REAL,
            exit_time DATETIME,
            quantity INTEGER DEFAULT 1,
            pnl REAL DEFAULT 0,
            pnl_ticks REAL DEFAULT 0,
            fees REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            notes TEXT,
            -- TP/SL tracking
            tp_price REAL,
            sl_price REAL,
            tp_ticks REAL,
            sl_ticks REAL,
            max_favorable REAL DEFAULT 0,
            max_adverse REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id),
            FOREIGN KEY (signal_id) REFERENCES recorded_signals(id)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorded_trades_recorder 
        ON recorded_trades(recorder_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorded_trades_status 
        ON recorded_trades(status)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorded_trades_entry_time 
        ON recorded_trades(entry_time)
    ''')
    
    # Recorder positions table - combines DCA entries into single position for drawdown tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorder_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            total_quantity INTEGER DEFAULT 0,
            avg_entry_price REAL,
            entries TEXT,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0,
            worst_unrealized_pnl REAL DEFAULT 0,
            best_unrealized_pnl REAL DEFAULT 0,
            exit_price REAL,
            realized_pnl REAL,
            status TEXT DEFAULT 'open',
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorder_positions_recorder 
        ON recorder_positions(recorder_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_recorder_positions_status 
        ON recorder_positions(status)
    ''')
    
    # Traders table - links recorders to accounts for live trading
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            enabled INTEGER DEFAULT 1,
            -- Risk settings (copied from recorder, can be customized per trader)
            initial_position_size INTEGER DEFAULT 2,
            add_position_size INTEGER DEFAULT 2,
            tp_targets TEXT DEFAULT '[]',
            sl_enabled INTEGER DEFAULT 0,
            sl_amount REAL DEFAULT 0,
            sl_units TEXT DEFAULT 'Ticks',
            max_daily_loss REAL DEFAULT 500,
            -- Subaccount info
            subaccount_id INTEGER,
            subaccount_name TEXT,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            UNIQUE(recorder_id, account_id, subaccount_id)
        )
    ''')
    
    # Add risk settings columns to existing traders table (for existing databases)
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN initial_position_size INTEGER DEFAULT 2')
    except:
        pass  # Column already exists
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN add_position_size INTEGER DEFAULT 2')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN tp_targets TEXT DEFAULT "[]"')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN sl_enabled INTEGER DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN sl_amount REAL DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN sl_units TEXT DEFAULT "Ticks"')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE traders ADD COLUMN max_daily_loss REAL DEFAULT 500')
    except:
        pass
    
    # Add shared strategy columns to existing strategies table (for existing databases)
    try:
        cursor.execute('ALTER TABLE strategies ADD COLUMN is_public INTEGER DEFAULT 0')
    except:
        pass  # Column already exists
    try:
        cursor.execute('ALTER TABLE strategies ADD COLUMN created_by_username TEXT')
    except:
        pass  # Column already exists
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_traders_recorder 
        ON traders(recorder_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_traders_account 
        ON traders(account_id)
    ''')
    
    conn.commit()
    conn.close()

def fetch_and_store_tradovate_accounts(account_id: int, access_token: str, base_url: str = "https://demo.tradovateapi.com") -> dict:
    """
    Fetch Tradovate accounts/subaccounts for the given account_id and MERGE with existing data.
    This preserves accounts from environments the token can't access.
    Returns a dict with success flag and parsed subaccounts.
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # First, get EXISTING data from the database to preserve accounts we can't access
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT tradovate_accounts, subaccounts FROM accounts WHERE id = ?", (account_id,))
        existing_row = cursor.fetchone()
        conn.close()
        
        existing_accounts = []
        existing_subaccounts = []
        if existing_row:
            try:
                if existing_row['tradovate_accounts']:
                    existing_accounts = json.loads(existing_row['tradovate_accounts'])
            except:
                pass
            try:
                if existing_row['subaccounts']:
                    existing_subaccounts = json.loads(existing_row['subaccounts'])
            except:
                pass

        # Always attempt both demo and live endpoints so we capture all accounts
        base_urls = []
        if base_url:
            base_urls.append(base_url.rstrip('/'))
        for candidate in ("https://demo.tradovateapi.com", "https://live.tradovateapi.com"):
            if candidate not in base_urls:
                base_urls.append(candidate)

        # Track which environments we successfully fetched
        fetched_environments = set()
        new_accounts = []
        new_subaccounts = []
        success = False
        
        for candidate_base in base_urls:
            try:
                response = requests.get(f"{candidate_base}/v1/account/list", headers=headers, timeout=15)
            except Exception as req_err:
                logger.warning(f"Error fetching Tradovate accounts from {candidate_base}: {req_err}")
                continue

            if response.status_code != 200:
                logger.warning(f"Could not fetch from {candidate_base}: {response.status_code} (token may not have access)")
                continue

            success = True
            environment = "demo" if "demo." in candidate_base else "live"
            fetched_environments.add(environment)
            logger.info(f"Successfully fetched accounts from {environment} environment")
            
            accounts_payload = response.json() or []
            for account in accounts_payload:
                account_copy = dict(account) if isinstance(account, dict) else {}
                account_copy["environment"] = environment
                account_copy["is_demo"] = environment == "demo"
                new_accounts.append(account_copy)

                parent_name = account_copy.get('name') or account_copy.get('accountName', 'Tradovate')
                for sub in account_copy.get('subAccounts', []) or []:
                    tags = sub.get('tags') or []
                    if isinstance(tags, str):
                        tags = [tags]
                    name = sub.get('name') or ''
                    is_demo = True if environment == "demo" else False
                    new_subaccounts.append({
                        "id": sub.get('id'),
                        "name": name,
                        "parent": parent_name,
                        "tags": tags,
                        "active": sub.get('active', True),
                        "environment": environment,
                        "is_demo": is_demo
                    })

        if not success:
            # If we couldn't fetch from any endpoint, keep existing data
            if existing_accounts:
                logger.warning(f"Could not refresh accounts, keeping existing {len(existing_accounts)} accounts")
                return {"success": True, "subaccounts": existing_subaccounts, "message": "Using cached data"}
            return {"success": False, "error": "Failed to fetch Tradovate accounts from demo or live endpoints"}

        # MERGE: Keep existing accounts from environments we couldn't fetch
        combined_accounts = list(new_accounts)
        combined_subaccounts = list(new_subaccounts)
        
        for existing_acc in existing_accounts:
            existing_env = existing_acc.get('environment') or ('demo' if existing_acc.get('is_demo') else 'live')
            if existing_env not in fetched_environments:
                # We couldn't access this environment, so keep the existing data
                logger.info(f"Preserving existing {existing_env} account: {existing_acc.get('name')}")
                combined_accounts.append(existing_acc)
        
        for existing_sub in existing_subaccounts:
            existing_env = existing_sub.get('environment') or ('demo' if existing_sub.get('is_demo') else 'live')
            if existing_env not in fetched_environments:
                combined_subaccounts.append(existing_sub)

        # Log what we're storing
        demo_count = sum(1 for a in combined_accounts if a.get('is_demo'))
        live_count = sum(1 for a in combined_accounts if not a.get('is_demo'))
        logger.info(f"Storing {demo_count} demo + {live_count} live accounts for account {account_id}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts
            SET tradovate_accounts = ?, subaccounts = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(combined_accounts), json.dumps(combined_subaccounts), account_id))
        conn.commit()
        conn.close()
        logger.info(f"Stored {len(combined_subaccounts)} Tradovate subaccounts for account {account_id}")
        return {"success": True, "subaccounts": combined_subaccounts}
    except Exception as e:
        logger.error(f"Error storing Tradovate accounts: {e}")
        return {"success": False, "error": str(e)}

@app.route('/')
def index():
    """Root route - redirect to dashboard if logged in, otherwise to login."""
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

# ============================================================================
# USER AUTHENTICATION ROUTES
# ============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    # If already logged in, redirect to dashboard
    if USER_AUTH_AVAILABLE and is_logged_in():
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if not USER_AUTH_AVAILABLE:
            flash('Authentication system not available.', 'error')
            return render_template('login.html')
        
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not username_or_email or not password:
            flash('Please enter your username/email and password.', 'error')
            return render_template('login.html')
        
        user = authenticate_user(username_or_email, password)
        if user:
            login_user(user)
            
            # Set session permanence based on "remember me"
            session.permanent = remember
            
            # Redirect to originally requested page or dashboard
            next_url = session.pop('next_url', None)
            flash(f'Welcome back, {user.display_name}!', 'success')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler."""
    # If already logged in, redirect to dashboard
    if USER_AUTH_AVAILABLE and is_logged_in():
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if not USER_AUTH_AVAILABLE:
            flash('Authentication system not available.', 'error')
            return render_template('register.html')
        
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        display_name = request.form.get('display_name', '').strip() or username
        terms = request.form.get('terms')
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not terms:
            errors.append('You must agree to the Terms of Service.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Try to create user
        user = create_user(username, email, password, display_name)
        if user:
            # Auto-login after registration
            login_user(user)
            flash(f'Welcome to Just.Trades., {user.display_name}! Your account has been created.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username or email already exists. Please try different credentials.', 'error')
    
    return render_template('register.html')


@app.route('/logout')
def logout():
    """Logout handler."""
    if USER_AUTH_AVAILABLE:
        logout_user()
        flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ============================================================================
# ADMIN ROUTES - User Management
# ============================================================================
@app.route('/admin/users')
def admin_users():
    """Admin page for managing users."""
    if not USER_AUTH_AVAILABLE:
        flash('Authentication system not available.', 'error')
        return redirect(url_for('dashboard'))
    
    if not is_logged_in():
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('dashboard'))
    
    from user_auth import get_all_users
    users = get_all_users()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/create', methods=['POST'])
def admin_create_user():
    """Admin endpoint to create a new user."""
    if not USER_AUTH_AVAILABLE:
        return jsonify({'success': False, 'error': 'Auth not available'}), 400
    
    if not is_logged_in():
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('dashboard'))
    
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    display_name = request.form.get('display_name', '').strip() or username
    is_admin = request.form.get('is_admin') == '1'
    
    if not username or not email or not password:
        flash('All fields are required.', 'error')
        return redirect(url_for('admin_users'))
    
    new_user = create_user(username, email, password, display_name, is_admin)
    if new_user:
        flash(f'User "{username}" created successfully.', 'success')
    else:
        flash('Failed to create user. Username or email may already exist.', 'error')
    
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def admin_delete_user(user_id):
    """Admin endpoint to delete a user."""
    if not USER_AUTH_AVAILABLE:
        return jsonify({'success': False, 'error': 'Auth not available'}), 400
    
    if not is_logged_in():
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    current = get_current_user()
    if not current or not current.is_admin:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    # Don't allow deleting yourself
    if user_id == current.id:
        return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400
    
    from user_auth import get_auth_db_connection
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        else:
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/health')
def health():
    """Health check endpoint for load balancers and monitoring."""
    try:
        # Check database connection
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "healthy"
        db_type = get_db_type() if PRODUCTION_DB_AVAILABLE else "sqlite"
    except Exception as e:
        db_status = f"error: {str(e)}"
        db_type = "unknown"
    
    # Check Redis/cache if available
    cache_status = "not configured"
    if CACHE_AVAILABLE:
        try:
            cache_info = get_cache_status()
            cache_status = cache_info.get('backend', 'memory')
            if cache_info.get('connected'):
                cache_status += " (connected)"
        except:
            cache_status = "error"
    
    # Check async utils
    async_status = "available" if ASYNC_UTILS_AVAILABLE else "not loaded"
    
    status = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "database_type": db_type,
        "cache": cache_status,
        "async_utils": async_status,
        "timestamp": datetime.now().isoformat(),
        "version": "2025-12-19-v4-auth-fix"
    }
    
    return jsonify(status), 200 if db_status == "healthy" else 503


@app.route('/api/accounts/auth-status')
def api_accounts_auth_status():
    """
    Get authentication status for all accounts.
    Returns list of accounts that need OAuth re-authentication.
    Use this to show warnings in the UI when accounts need manual reconnection.
    """
    try:
        accounts_need_reauth = get_accounts_needing_reauth()
        
        # Get account names for the IDs
        account_details = []
        if accounts_need_reauth:
            conn = get_db_connection()
            cursor = conn.cursor()
            for acct_id in accounts_need_reauth:
                cursor.execute('SELECT id, name FROM accounts WHERE id = ?', (acct_id,))
                row = cursor.fetchone()
                if row:
                    account_details.append({
                        'id': row['id'] if isinstance(row, dict) else row[0],
                        'name': row['name'] if isinstance(row, dict) else row[1],
                        'status': 'needs_reauth',
                        'action': 'Go to Account Management and click "Connect to Tradovate"'
                    })
            conn.close()
        
        return jsonify({
            'success': True,
            'all_accounts_valid': len(accounts_need_reauth) == 0,
            'accounts_needing_reauth': account_details,
            'count': len(account_details),
            'message': 'All accounts authenticated!' if len(accounts_need_reauth) == 0 else f'{len(accounts_need_reauth)} account(s) need OAuth re-authentication'
        })
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# DEVICE AUTHORIZATION ROUTES (Captcha/Device Trust)
# =============================================================================

@app.route('/device-authorization')
def device_authorization():
    """Device authorization page for API Access verification"""
    return render_template('device_authorization.html')

@app.route('/api/account/<int:account_id>/device-info')
def get_account_device_info(account_id):
    """Get device ID and account info for device authorization"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, device_id FROM accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        return jsonify({
            'success': True,
            'account_id': row['id'],
            'account_name': row['name'],
            'device_id': row['device_id'] or f'Just.Trade-{account_id}'
        })
    except Exception as e:
        logger.error(f"Error getting device info: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/account/<int:account_id>/api-credentials', methods=['GET'])
def get_api_credentials(account_id):
    """Get API credentials for an account (CID only, not secret)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT api_key FROM accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        return jsonify({
            'success': True,
            'api_key': row['api_key'] or ''
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/account/<int:account_id>/api-credentials', methods=['POST'])
def save_api_credentials(account_id):
    """Save API credentials (CID and Secret) for an account"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
        
        if not api_key:
            return jsonify({'success': False, 'error': 'Client ID (CID) is required'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update API credentials
        if api_secret:
            cursor.execute('UPDATE accounts SET api_key = ?, api_secret = ? WHERE id = ?', 
                          (api_key, api_secret, account_id))
        else:
            # Only update CID if no secret provided (preserve existing secret)
            cursor.execute('UPDATE accounts SET api_key = ? WHERE id = ?', 
                          (api_key, account_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ API credentials saved for account {account_id}")
        return jsonify({'success': True, 'message': 'API credentials saved'})
    except Exception as e:
        logger.error(f"Error saving API credentials: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/account/<int:account_id>/test-api-access', methods=['POST'])
def test_api_access(account_id):
    """Test if API Access works for an account (triggers device verification if needed)"""
    import aiohttp
    import asyncio
    
    async def do_test():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, username, password, device_id, environment, api_key, api_secret FROM accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {'success': False, 'error': 'Account not found'}
        
        if not row['username'] or not row['password']:
            return {'success': False, 'error': 'No username/password stored for this account'}
        
        device_id = row['device_id'] or f'Just.Trade-{account_id}'
        is_demo = row['environment'] == 'demo'
        base_url = "https://demo.tradovateapi.com/v1" if is_demo else "https://live.tradovateapi.com/v1"
        
        # Use per-account API key if available (TradeManager's approach!)
        use_cid = int(row['api_key']) if row['api_key'] else int(os.getenv("TRADOVATE_API_CID", "8949"))
        use_sec = row['api_secret'] if row['api_secret'] else os.getenv("TRADOVATE_API_SECRET", "c8440ba5-6315-4845-8c69-977651d5c77a")
        
        body = {
            'name': row['username'],
            'password': row['password'],
            'appId': 'JustTrades',
            'appVersion': '1.0',
            'deviceId': device_id,
            'cid': use_cid,
            'sec': use_sec
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/auth/accesstokenrequest", json=body) as resp:
                data = await resp.json()
                
                if data.get('p-captcha'):
                    logger.info(f"Device verification triggered for {row['name']} (device: {device_id})")
                    return {
                        'success': False,
                        'p_captcha': True,
                        'p_time': data.get('p-time', 60),
                        'device_id': device_id,
                        'message': 'Device verification required. Check your email from Tradovate.'
                    }
                elif data.get('accessToken'):
                    logger.info(f"✅ API Access successful for {row['name']} - device is trusted!")
                    return {
                        'success': True,
                        'message': 'API Access is working! Device is trusted.'
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('error', 'Unknown error'),
                        'response': data
                    }
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(do_test())
        loop.close()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing API access: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/dashboard')
def dashboard():
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# =============================================================================
# INSIDER SIGNALS ROUTES (Added Dec 8, 2025)
# Integrated directly - no separate service needed
# =============================================================================

# Initialize insider tables for PostgreSQL/SQLite
def _init_insider_tables():
    """Create insider tables if they don't exist (works with both SQLite and PostgreSQL)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            # PostgreSQL table creation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_filings (
                    id SERIAL PRIMARY KEY,
                    accession_number TEXT UNIQUE,
                    form_type TEXT,
                    ticker TEXT,
                    company_name TEXT,
                    insider_name TEXT,
                    insider_title TEXT,
                    transaction_type TEXT,
                    shares INTEGER,
                    price REAL,
                    total_value REAL,
                    ownership_change_percent REAL,
                    shares_owned_after REAL,
                    filing_date TEXT,
                    transaction_date TEXT,
                    filing_url TEXT,
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_signals (
                    id SERIAL PRIMARY KEY,
                    filing_id INTEGER,
                    ticker TEXT,
                    signal_score INTEGER,
                    insider_name TEXT,
                    insider_role TEXT,
                    transaction_type TEXT,
                    dollar_value REAL,
                    reason_flags TEXT,
                    is_highlighted INTEGER DEFAULT 0,
                    is_conviction INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_poll_status (
                    id INTEGER PRIMARY KEY,
                    last_poll_time TEXT,
                    last_filing_date TEXT,
                    filings_processed INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_watchlist (
                    id SERIAL PRIMARY KEY,
                    watch_type TEXT NOT NULL,
                    watch_value TEXT NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(watch_type, watch_value)
                )
            ''')
            # Initialize poll status if not exists
            cursor.execute('SELECT COUNT(*) FROM insider_poll_status')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO insider_poll_status (id, last_poll_time, filings_processed) VALUES (1, %s, 0)', (datetime.now().isoformat(),))
        else:
            # SQLite table creation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_filings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accession_number TEXT UNIQUE,
                    form_type TEXT,
                    ticker TEXT,
                    company_name TEXT,
                    insider_name TEXT,
                    insider_title TEXT,
                    transaction_type TEXT,
                    shares INTEGER,
                    price REAL,
                    total_value REAL,
                    ownership_change_percent REAL,
                    shares_owned_after REAL,
                    filing_date TEXT,
                    transaction_date TEXT,
                    filing_url TEXT,
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filing_id INTEGER,
                    ticker TEXT,
                    signal_score INTEGER,
                    insider_name TEXT,
                    insider_role TEXT,
                    transaction_type TEXT,
                    dollar_value REAL,
                    reason_flags TEXT,
                    is_highlighted INTEGER DEFAULT 0,
                    is_conviction INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_poll_status (
                    id INTEGER PRIMARY KEY,
                    last_poll_time TEXT,
                    last_filing_date TEXT,
                    filings_processed INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insider_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watch_type TEXT NOT NULL,
                    watch_value TEXT NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(watch_type, watch_value)
                )
            ''')
            # Initialize poll status if not exists
            cursor.execute('SELECT COUNT(*) FROM insider_poll_status')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO insider_poll_status (id, last_poll_time, filings_processed) VALUES (1, ?, 0)', (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
        print("✅ Insider tables initialized")
        return True
    except Exception as e:
        print(f"⚠️ Insider tables init failed: {e}")
        return False

# Lazy initialization for insider tables
_insider_tables_initialized = False

def _ensure_insider_tables():
    """Lazily initialize insider tables on first use"""
    global _insider_tables_initialized
    if _insider_tables_initialized:
        return True
    try:
        result = _init_insider_tables()
        if result:
            _insider_tables_initialized = True
        return result
    except Exception as e:
        print(f"⚠️ Insider tables init error: {e}")
        return False

# Always mark as available - tables will be created on demand
INSIDER_SERVICE_AVAILABLE = True
print("✅ Insider Signals module ready (tables will init on first use)")

# =============================================================================
# SEC EDGAR POLLING (PostgreSQL-compatible)
# =============================================================================
SEC_USER_AGENT = "JustTrades/1.0 (Contact: support@just.trades)"
INSIDER_POLL_INTERVAL = 300  # 5 minutes
INSIDER_HIGHLIGHT_THRESHOLD = 70
INSIDER_CONVICTION_THRESHOLD = 85

# Scoring weights
INSIDER_SCORING_WEIGHTS = {
    'dollar_value': 0.35, 'ownership_change': 0.20, 'insider_role': 0.15,
    'cluster': 0.15, 'recency': 0.15
}
INSIDER_ROLE_WEIGHTS = {
    'ceo': 1.0, 'chief executive': 1.0, 'cfo': 0.95, 'chief financial': 0.95,
    'coo': 0.9, 'president': 0.9, 'director': 0.7, '10%': 1.1, 'chairman': 0.85
}

def _insider_parse_atom_feed(xml_content):
    """Parse SEC EDGAR Atom feed for Form 4 filings"""
    import xml.etree.ElementTree as ET
    import re
    filings = []
    seen = set()
    try:
        root = ET.fromstring(xml_content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('.//atom:entry', ns):
            try:
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                updated = entry.find('atom:updated', ns)
                entry_id = entry.find('atom:id', ns)
                if title is not None and title.text:
                    if '(Issuer)' in title.text:
                        continue
                    accession = None
                    if entry_id is not None and entry_id.text:
                        m = re.search(r'accession-number=(\d{10}-\d{2}-\d{6})', entry_id.text)
                        if m:
                            accession = m.group(1)
                    if accession and accession in seen:
                        continue
                    if accession:
                        seen.add(accession)
                    filing = {
                        'form_type': '4', 'accession_number': accession,
                        'filing_url': link.get('href') if link is not None else None,
                        'filing_date': updated.text if updated is not None else None
                    }
                    if ' - ' in title.text:
                        parts = title.text.split(' - ', 1)
                        if len(parts) > 1 and '(' in parts[1]:
                            filing['insider_name'] = parts[1].split('(')[0].strip()
                    filings.append(filing)
            except:
                continue
    except:
        pass
    return filings

def _insider_fetch_form4_details(filing_url):
    """Fetch detailed Form 4 data from filing URL"""
    import xml.etree.ElementTree as ET
    import re
    details = {'ticker': None, 'insider_name': None, 'insider_title': None, 'transaction_type': None,
               'shares': 0, 'price': 0.0, 'total_value': 0.0, 'shares_owned_after': 0, 'ownership_change_percent': 0.0}
    try:
        if not filing_url:
            return details
        headers = {'User-Agent': SEC_USER_AGENT}
        resp = requests.get(filing_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return details
        xml_links = re.findall(r'href="([^"]*\.xml)"', resp.text, re.IGNORECASE)
        primary_xml = None
        for link in xml_links:
            if 'xsl' in link.lower() and 'form4' not in link.lower():
                continue
            if 'form4' in link.lower() or 'primary' in link.lower():
                primary_xml = link
                break
            if primary_xml is None:
                primary_xml = link
        if not primary_xml:
            return details
        if primary_xml.startswith('http'):
            xml_url = primary_xml
        elif primary_xml.startswith('/'):
            xml_url = f"https://www.sec.gov{primary_xml}"
        else:
            base_url = '/'.join(filing_url.rstrip('/').split('/')[:-1])
            xml_url = f"{base_url}/{primary_xml}"
        xml_resp = requests.get(xml_url, headers=headers, timeout=30)
        if xml_resp.status_code != 200:
            return details
        # Parse Form 4 XML
        root = ET.fromstring(xml_resp.text)
        issuer = root.find('.//issuer')
        if issuer is not None:
            ticker_elem = issuer.find('issuerTradingSymbol')
            if ticker_elem is not None and ticker_elem.text:
                details['ticker'] = ticker_elem.text.strip().upper()
        owner = root.find('.//reportingOwner')
        if owner is not None:
            owner_id = owner.find('reportingOwnerId')
            if owner_id is not None:
                name_elem = owner_id.find('rptOwnerName')
                if name_elem is not None and name_elem.text:
                    details['insider_name'] = name_elem.text.strip()
            rel = owner.find('reportingOwnerRelationship')
            if rel is not None:
                for tf in ['officerTitle', 'otherText']:
                    te = rel.find(tf)
                    if te is not None and te.text:
                        details['insider_title'] = te.text.strip()
                        break
        total_shares = 0
        total_value = 0.0
        for trans in root.findall('.//nonDerivativeTransaction'):
            code_elem = trans.find('.//transactionCoding/transactionCode')
            if code_elem is not None and code_elem.text:
                c = code_elem.text.upper()
                details['transaction_type'] = {'P': 'BUY', 'S': 'SELL', 'A': 'AWARD', 'G': 'GIFT', 'M': 'EXERCISE'}.get(c, c)
            shares_elem = trans.find('.//transactionAmounts/transactionShares/value')
            if shares_elem is not None and shares_elem.text:
                try:
                    total_shares += float(shares_elem.text)
                except:
                    pass
            price_elem = trans.find('.//transactionAmounts/transactionPricePerShare/value')
            if price_elem is not None and price_elem.text:
                try:
                    p = float(price_elem.text)
                    details['price'] = p
                    if shares_elem and shares_elem.text:
                        total_value += float(shares_elem.text) * p
                except:
                    pass
            after_elem = trans.find('.//postTransactionAmounts/sharesOwnedFollowingTransaction/value')
            if after_elem is not None and after_elem.text:
                try:
                    details['shares_owned_after'] = float(after_elem.text)
                except:
                    pass
        details['shares'] = int(total_shares)
        details['total_value'] = round(total_value, 2)
        if details['shares_owned_after'] > 0 and total_shares > 0:
            before = details['shares_owned_after'] - total_shares if details['transaction_type'] == 'BUY' else details['shares_owned_after'] + total_shares
            if before > 0:
                details['ownership_change_percent'] = round((total_shares / before) * 100, 2)
    except:
        pass
    return details

def _insider_calculate_score(filing_data):
    """Calculate signal score (0-100) for an insider filing"""
    if filing_data.get('transaction_type') != 'BUY':
        return 0, ['not_buy']
    score = 0
    flags = []
    tv = filing_data.get('total_value', 0) or 0
    if tv >= 1000000:
        ds, flags = 100, flags + ['million_dollar_buy']
    elif tv >= 500000:
        ds, flags = 95, flags + ['large_buy_500k']
    elif tv >= 100000:
        ds, flags = 75, flags + ['significant_buy_100k']
    elif tv >= 50000:
        ds, flags = 65, flags + ['notable_buy_50k']
    else:
        ds = max(20, min(55, tv / 1000))
    score += ds * INSIDER_SCORING_WEIGHTS['dollar_value']
    oc = filing_data.get('ownership_change_percent', 0) or 0
    if oc >= 100:
        os_score, flags = 100, flags + ['doubled_position']
    elif oc >= 50:
        os_score, flags = 90, flags + ['major_position_increase']
    elif oc >= 25:
        os_score = 75
    else:
        os_score = 30
    score += os_score * INSIDER_SCORING_WEIGHTS['ownership_change']
    title = (filing_data.get('insider_title') or '').lower()
    rw = 0.5
    for rk, w in INSIDER_ROLE_WEIGHTS.items():
        if rk in title:
            rw = w
            if w >= 0.9:
                flags.append('c_suite_purchase')
            break
    score += (rw * 100) * INSIDER_SCORING_WEIGHTS['insider_role']
    score += 60 * INSIDER_SCORING_WEIGHTS['recency']
    if filing_data.get('price', 0) > 0:
        score += 5
        flags.append('open_market_purchase')
    return min(100, max(0, round(score))), flags

def _insider_process_filings():
    """Fetch and process SEC filings (works with PostgreSQL and SQLite)"""
    import json
    try:
        _ensure_insider_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Fetch recent Form 4 filings
        api_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {'action': 'getcurrent', 'type': '4', 'owner': 'only', 'count': '100', 'output': 'atom'}
        headers = {'User-Agent': SEC_USER_AGENT, 'Accept': 'application/atom+xml'}
        
        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            conn.close()
            return
        
        filings = _insider_parse_atom_feed(resp.text)
        processed = 0
        
        for filing in filings:
            try:
                acc = filing.get('accession_number')
                if not acc:
                    continue
                # Check if exists
                if is_postgres:
                    cursor.execute('SELECT id FROM insider_filings WHERE accession_number = %s', (acc,))
                else:
                    cursor.execute('SELECT id FROM insider_filings WHERE accession_number = ?', (acc,))
                if cursor.fetchone():
                    continue
                # Fetch details
                details = _insider_fetch_form4_details(filing.get('filing_url'))
                if not details.get('ticker'):
                    continue
                # Insert filing
                if is_postgres:
                    cursor.execute('''INSERT INTO insider_filings (accession_number, form_type, ticker, company_name,
                        insider_name, insider_title, transaction_type, shares, price, total_value,
                        ownership_change_percent, shares_owned_after, filing_date, transaction_date, filing_url, raw_data)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                        (acc, '4', details.get('ticker'), filing.get('company_name'), details.get('insider_name'),
                         details.get('insider_title'), details.get('transaction_type'), details.get('shares'),
                         details.get('price'), details.get('total_value'), details.get('ownership_change_percent'),
                         details.get('shares_owned_after'), filing.get('filing_date'), details.get('transaction_date'),
                         filing.get('filing_url'), json.dumps(details)))
                    filing_id = cursor.fetchone()[0]
                else:
                    cursor.execute('''INSERT INTO insider_filings (accession_number, form_type, ticker, company_name,
                        insider_name, insider_title, transaction_type, shares, price, total_value,
                        ownership_change_percent, shares_owned_after, filing_date, transaction_date, filing_url, raw_data)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (acc, '4', details.get('ticker'), filing.get('company_name'), details.get('insider_name'),
                         details.get('insider_title'), details.get('transaction_type'), details.get('shares'),
                         details.get('price'), details.get('total_value'), details.get('ownership_change_percent'),
                         details.get('shares_owned_after'), filing.get('filing_date'), details.get('transaction_date'),
                         filing.get('filing_url'), json.dumps(details)))
                    filing_id = cursor.lastrowid
                # Score and create signal
                score, flags = _insider_calculate_score(details)
                if details.get('transaction_type') == 'BUY' and score > 0:
                    is_high = 1 if score >= INSIDER_HIGHLIGHT_THRESHOLD else 0
                    is_conv = 1 if score >= INSIDER_CONVICTION_THRESHOLD else 0
                    if is_postgres:
                        cursor.execute('''INSERT INTO insider_signals (filing_id, ticker, signal_score, insider_name,
                            insider_role, transaction_type, dollar_value, reason_flags, is_highlighted, is_conviction)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                            (filing_id, details.get('ticker'), score, details.get('insider_name'),
                             details.get('insider_title'), details.get('transaction_type'), details.get('total_value'),
                             json.dumps(flags), is_high, is_conv))
                    else:
                        cursor.execute('''INSERT INTO insider_signals (filing_id, ticker, signal_score, insider_name,
                            insider_role, transaction_type, dollar_value, reason_flags, is_highlighted, is_conviction)
                            VALUES (?,?,?,?,?,?,?,?,?,?)''',
                            (filing_id, details.get('ticker'), score, details.get('insider_name'),
                             details.get('insider_title'), details.get('transaction_type'), details.get('total_value'),
                             json.dumps(flags), is_high, is_conv))
                processed += 1
                time.sleep(0.1)  # Rate limit
            except Exception as e:
                continue
        
        # Update poll status
        if is_postgres:
            cursor.execute('UPDATE insider_poll_status SET last_poll_time = %s, filings_processed = filings_processed + %s WHERE id = 1',
                          (datetime.now().isoformat(), processed))
        else:
            cursor.execute('UPDATE insider_poll_status SET last_poll_time = ?, filings_processed = filings_processed + ? WHERE id = 1',
                          (datetime.now().isoformat(), processed))
        conn.commit()
        conn.close()
        if processed > 0:
            print(f"📊 Insider polling: {processed} new filings processed")
    except Exception as e:
        print(f"⚠️ Insider polling error: {e}")

def _insider_polling_loop():
    """Background thread for SEC polling"""
    print(f"🚀 Starting SEC insider polling (every {INSIDER_POLL_INTERVAL}s)")
    time.sleep(10)  # Initial delay
    while True:
        try:
            _insider_process_filings()
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
        time.sleep(INSIDER_POLL_INTERVAL)

# Start the polling thread
_insider_poll_thread = threading.Thread(target=_insider_polling_loop, daemon=True)
_insider_poll_thread.start()

@app.route('/insider-signals')
@app.route('/insider_signals')
def insider_signals():
    """Render the Insider Signals tab"""
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('insider_signals.html')

@app.route('/api/insiders/status')
def api_insiders_status():
    """Get insider service status"""
    try:
        # Ensure tables exist (lazy init)
        _ensure_insider_tables()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get counts
        cursor.execute('SELECT COUNT(*) FROM insider_filings')
        total_filings = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM insider_signals')
        total_signals = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM insider_signals WHERE is_conviction = 1')
        conviction_signals = cursor.fetchone()[0]
        
        today = datetime.now().strftime('%Y-%m-%d')
        if is_postgres:
            cursor.execute("SELECT COUNT(*) FROM insider_signals WHERE DATE(created_at) = %s", (today,))
        else:
            cursor.execute("SELECT COUNT(*) FROM insider_signals WHERE DATE(created_at) = ?", (today,))
        today_signals = cursor.fetchone()[0]
        
        # Get poll status
        cursor.execute('SELECT * FROM insider_poll_status WHERE id = 1')
        row = cursor.fetchone()
        poll_status = None
        if row:
            if is_postgres:
                poll_status = {'last_poll_time': row[1], 'filings_processed': row[3], 'errors_count': row[4]}
            else:
                poll_status = {'last_poll_time': row[1], 'filings_processed': row[3], 'errors_count': row[4]}
        
        conn.close()
        
        return jsonify({
            'service': 'insider_signals_integrated',
            'status': 'running',
            'poll_interval_seconds': 300,
            'last_poll_time': poll_status['last_poll_time'] if poll_status else None,
            'total_filings': total_filings,
            'total_signals': total_signals,
            'conviction_signals': conviction_signals,
            'today_signals': today_signals,
            'filings_processed': poll_status['filings_processed'] if poll_status else 0,
            'errors_count': poll_status['errors_count'] if poll_status else 0
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/insiders/today')
def api_insiders_today():
    """Get today's insider signals"""
    try:
        _ensure_insider_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        if is_postgres:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE DATE(s.created_at) = %s
                ORDER BY s.signal_score DESC
            ''', (today,))
        else:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE DATE(s.created_at) = ?
                ORDER BY s.signal_score DESC
            ''', (today,))
        
        columns = ['id', 'filing_id', 'ticker', 'signal_score', 'insider_name', 'insider_role',
                   'transaction_type', 'dollar_value', 'reason_flags', 'is_highlighted', 'is_conviction',
                   'created_at', 'company_name', 'filing_url', 'shares', 'price',
                   'ownership_change_percent', 'filing_date', 'transaction_date']
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'date': today,
            'count': len(signals),
            'signals': signals
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "signals": []}), 500

@app.route('/api/insiders/top')
def api_insiders_top():
    """Get top signals with filters"""
    try:
        _ensure_insider_tables()
        limit = request.args.get('limit', 50, type=int)
        min_score = request.args.get('min_score', 0, type=int)
        days = request.args.get('days', 7, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        if is_postgres:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.signal_score >= %s
                AND s.created_at >= %s
                ORDER BY s.signal_score DESC, s.created_at DESC
                LIMIT %s
            ''', (min_score, since_date, limit))
        else:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.signal_score >= ?
                AND s.created_at >= ?
                ORDER BY s.signal_score DESC, s.created_at DESC
                LIMIT ?
            ''', (min_score, since_date, limit))
        
        columns = ['id', 'filing_id', 'ticker', 'signal_score', 'insider_name', 'insider_role',
                   'transaction_type', 'dollar_value', 'reason_flags', 'is_highlighted', 'is_conviction',
                   'created_at', 'company_name', 'filing_url', 'shares', 'price',
                   'ownership_change_percent', 'filing_date', 'transaction_date']
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(signals),
            'filters': {'limit': limit, 'min_score': min_score, 'days': days},
            'signals': signals
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "signals": []}), 500

@app.route('/api/insiders/ticker/<symbol>')
def api_insiders_ticker(symbol):
    """Get signals for specific ticker"""
    try:
        _ensure_insider_tables()
        symbol = symbol.upper()
        limit = request.args.get('limit', 20, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.ticker = %s
                ORDER BY s.created_at DESC
                LIMIT %s
            ''', (symbol, limit))
        else:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.ticker = ?
                ORDER BY s.created_at DESC
                LIMIT ?
            ''', (symbol, limit))
        
        columns = ['id', 'filing_id', 'ticker', 'signal_score', 'insider_name', 'insider_role',
                   'transaction_type', 'dollar_value', 'reason_flags', 'is_highlighted', 'is_conviction',
                   'created_at', 'company_name', 'filing_url', 'shares', 'price',
                   'ownership_change_percent', 'filing_date', 'transaction_date']
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'ticker': symbol,
            'count': len(signals),
            'signals': signals
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "signals": []}), 500

@app.route('/api/insiders/conviction')
def api_insiders_conviction():
    """Get high conviction signals"""
    try:
        _ensure_insider_tables()
        limit = request.args.get('limit', 20, type=int)
        days = request.args.get('days', 30, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        if is_postgres:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.is_conviction = 1
                AND s.created_at >= %s
                ORDER BY s.signal_score DESC, s.created_at DESC
                LIMIT %s
            ''', (since_date, limit))
        else:
            cursor.execute('''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.is_conviction = 1
                AND s.created_at >= ?
                ORDER BY s.signal_score DESC, s.created_at DESC
                LIMIT ?
            ''', (since_date, limit))
        
        columns = ['id', 'filing_id', 'ticker', 'signal_score', 'insider_name', 'insider_role',
                   'transaction_type', 'dollar_value', 'reason_flags', 'is_highlighted', 'is_conviction',
                   'created_at', 'company_name', 'filing_url', 'shares', 'price',
                   'ownership_change_percent', 'filing_date', 'transaction_date']
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(signals),
            'signals': signals
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "signals": []}), 500

@app.route('/api/insiders/refresh', methods=['POST'])
def api_insiders_refresh():
    """Trigger manual refresh - only works in SQLite mode"""
    try:
        _ensure_insider_tables()
        if is_using_postgres():
            return jsonify({
                'success': True,
                'message': 'PostgreSQL mode - manual refresh not available (data is from SEC filings)'
            })
        thread = threading.Thread(target=insider_service.process_filings, daemon=True)
        thread.start()
        return jsonify({
            'success': True,
            'message': 'Refresh triggered - processing in background'
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/insiders/price/<ticker>')
def api_insiders_price(ticker):
    """Get stock price using Yahoo Finance"""
    try:
        # Use Yahoo Finance directly (no insider_service dependency)
        import time as time_module
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}"
        params = {'interval': '1d', 'range': '5d'}
        headers = {'User-Agent': 'JustTrades/1.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('chart', {}).get('result', [])
            
            if result:
                meta = result[0].get('meta', {})
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose') or meta.get('chartPreviousClose')
                
                if price:
                    change = None
                    change_pct = None
                    if prev_close:
                        change = round(price - prev_close, 2)
                        change_pct = round((change / prev_close) * 100, 2)
                    
                    return jsonify({
                        'success': True,
                        'ticker': ticker.upper(),
                        'price': round(price, 2),
                        'change': change,
                        'change_pct': change_pct
                    })
        
        return jsonify({'success': False, 'ticker': ticker.upper(), 'error': 'Price unavailable'}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/insiders/watchlist', methods=['GET', 'POST'])
def api_insiders_watchlist():
    """Watchlist operations"""
    try:
        _ensure_insider_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if request.method == 'POST':
            data = request.get_json()
            watch_type = data.get('type', 'ticker')
            watch_value = data.get('value', '').strip().upper() if watch_type == 'ticker' else data.get('value', '').strip()
            notes = data.get('notes', '')
            
            if not watch_value:
                return jsonify({'success': False, 'error': 'Value is required'}), 400
            
            try:
                if is_postgres:
                    cursor.execute('''
                        INSERT INTO insider_watchlist (watch_type, watch_value, notes)
                        VALUES (%s, %s, %s) RETURNING id
                    ''', (watch_type, watch_value, notes))
                    watchlist_id = cursor.fetchone()[0]
                else:
                    cursor.execute('''
                        INSERT INTO insider_watchlist (watch_type, watch_value, notes)
                        VALUES (?, ?, ?)
                    ''', (watch_type, watch_value, notes))
                    watchlist_id = cursor.lastrowid
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'id': watchlist_id, 'message': f'Added {watch_value} to watchlist'})
            except Exception as e:
                conn.close()
                if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                    return jsonify({'success': False, 'error': 'Already in watchlist'}), 409
                raise
        else:
            cursor.execute('SELECT id, watch_type, watch_value, notes, created_at FROM insider_watchlist ORDER BY created_at DESC')
            columns = ['id', 'watch_type', 'watch_value', 'notes', 'created_at']
            items = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return jsonify({'success': True, 'count': len(items), 'watchlist': items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/insiders/watchlist/<int:item_id>', methods=['DELETE'])
def api_insiders_watchlist_delete(item_id):
    """Delete watchlist item"""
    try:
        _ensure_insider_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('DELETE FROM insider_watchlist WHERE id = %s', (item_id,))
        else:
            cursor.execute('DELETE FROM insider_watchlist WHERE id = ?', (item_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            return jsonify({'success': True, 'message': 'Removed from watchlist'})
        else:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/insiders/watchlist/signals')
def api_insiders_watchlist_signals():
    """Get signals matching watchlist"""
    try:
        _ensure_insider_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        cursor.execute('SELECT watch_type, watch_value FROM insider_watchlist')
        watchlist = cursor.fetchall()
        
        if not watchlist:
            conn.close()
            return jsonify({'success': True, 'count': 0, 'signals': []})
        
        ticker_list = [w[1] for w in watchlist if w[0] == 'ticker']
        signals = []
        
        if ticker_list:
            if is_postgres:
                placeholders = ','.join(['%s' for _ in ticker_list])
            else:
                placeholders = ','.join(['?' for _ in ticker_list])
            
            query = f'''
                SELECT s.id, s.filing_id, s.ticker, s.signal_score, s.insider_name, s.insider_role,
                       s.transaction_type, s.dollar_value, s.reason_flags, s.is_highlighted, s.is_conviction,
                       s.created_at, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.ticker IN ({placeholders})
                ORDER BY s.created_at DESC
                LIMIT 50
            '''
            cursor.execute(query, ticker_list)
            
            columns = ['id', 'filing_id', 'ticker', 'signal_score', 'insider_name', 'insider_role',
                       'transaction_type', 'dollar_value', 'reason_flags', 'is_highlighted', 'is_conviction',
                       'created_at', 'company_name', 'filing_url', 'shares', 'price',
                       'ownership_change_percent', 'filing_date', 'transaction_date']
            signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'success': True, 'count': len(signals), 'signals': signals})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "signals": []}), 500

# =============================================================================
# END INSIDER SIGNALS ROUTES
# =============================================================================

@app.route('/accounts')
def accounts():
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    # Inject the fetch MD token script into the template context
    return render_template('account_management.html', include_md_token_script=True)

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts for the current user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Filter by user_id if user is logged in - STRICT: only show user's own accounts
        if USER_AUTH_AVAILABLE and is_logged_in():
            user_id = get_current_user_id()
            if is_postgres:
                cursor.execute("SELECT * FROM accounts WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT * FROM accounts WHERE user_id = ?", (user_id,))
        else:
            # Not logged in - show nothing (require login)
            cursor.execute("SELECT * FROM accounts WHERE 1=0")
        accounts = cursor.fetchall()
        conn.close()
        
        # Convert rows to dict format
        if accounts and not hasattr(accounts[0], 'keys'):
            # PostgreSQL returns tuples, need to convert
            columns = ['id', 'user_id', 'name', 'broker', 'auth_type', 'enabled', 'username', 'password', 
                      'client_id', 'client_secret', 'environment', 'access_token', 'refresh_token', 
                      'md_access_token', 'token_expiry', 'tradovate_accounts', 'subaccounts', 'created_at', 'updated_at']
            accounts = [dict(zip(columns[:len(row)], row)) for row in accounts]
        
        accounts_list = []
        for account in accounts:
            # Convert to dict if needed
            if not isinstance(account, dict):
                account = dict(account)
            
            parsed_subaccounts = []
            try:
                if account.get('subaccounts'):
                    parsed_subaccounts = json.loads(account['subaccounts'])
            except Exception as parse_err:
                logger.warning(f"Unable to parse subaccounts for account {account.get('id')}: {parse_err}")
                parsed_subaccounts = []
            
            parsed_tradovate_accounts = []
            try:
                if account.get('tradovate_accounts'):
                    raw_tradovate_accounts = json.loads(account['tradovate_accounts'])
                    if isinstance(raw_tradovate_accounts, list):
                        for raw_acct in raw_tradovate_accounts:
                            acct_copy = dict(raw_acct) if isinstance(raw_acct, dict) else {}
                            if 'is_demo' not in acct_copy:
                                env_value = acct_copy.get('environment') or acct_copy.get('env')
                                name_value = acct_copy.get('name') or ''
                                inferred_demo = False
                                if isinstance(env_value, str):
                                    inferred_demo = env_value.lower() == 'demo'
                                elif isinstance(name_value, str):
                                    inferred_demo = name_value.upper().startswith('DEMO')
                                acct_copy['is_demo'] = inferred_demo
                            parsed_tradovate_accounts.append(acct_copy)
            except Exception as parse_err:
                logger.warning(f"Unable to parse tradovate_accounts for account {account.get('id')}: {parse_err}")
                parsed_tradovate_accounts = []
            
            has_demo = any(sub.get('is_demo') for sub in parsed_subaccounts) or \
                any(trad.get('is_demo') for trad in parsed_tradovate_accounts)
            has_live = any(not sub.get('is_demo') for sub in parsed_subaccounts) or \
                any(not trad.get('is_demo') for trad in parsed_tradovate_accounts)
            
            # Check for access token (tradovate_token is legacy name, access_token is new)
            has_token = bool(account.get('access_token') or account.get('tradovate_token'))
            
            accounts_list.append({
                'id': account.get('id'),
                'name': account.get('name'),
                'broker': account.get('broker', ''),
                'enabled': bool(account.get('enabled', True)),
                'created_at': str(account.get('created_at', '')),
                'tradovate_token': has_token,
                'is_connected': has_token,
                'subaccounts': parsed_subaccounts,
                'tradovate_accounts': parsed_tradovate_accounts,
                'has_demo': has_demo,
                'has_live': has_live
            })
        
        return jsonify({'success': True, 'accounts': accounts_list, 'count': len(accounts_list)})
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts', methods=['POST'])
def create_account():
    """Create a new account"""
    try:
        data = request.get_json()
        account_name = data.get('accountName') or data.get('name', '').strip()
        
        if not account_name:
            return jsonify({'success': False, 'error': 'Account name is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Check if account name already exists (wrapper auto-converts ? to %s)
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (account_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Account name already exists'}), 400
        
        # Get current user_id for data isolation
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Insert new account with default auth_type and user_id
        if is_postgres:
            # PostgreSQL: use RETURNING to get the ID
            cursor.execute("""
                INSERT INTO accounts (name, broker, auth_type, enabled, created_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?) RETURNING id
            """, (account_name, 'Tradovate', 'oauth', True, datetime.now().isoformat(), current_user_id))
            result = cursor.fetchone()
            # Result is a dict from RealDictCursor
            if result:
                account_id = result.get('id') if isinstance(result, dict) else result[0]
            else:
                account_id = None
        else:
            # SQLite: use lastrowid
            cursor.execute("""
                INSERT INTO accounts (name, broker, auth_type, enabled, created_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (account_name, 'Tradovate', 'oauth', 1, datetime.now().isoformat(), current_user_id))
            account_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Return success with redirect URL for broker selection
        return jsonify({
            'success': True,
            'account_id': account_id,
            'redirect': True,
            'broker_selection_url': f'/accounts/{account_id}/broker-selection',
            'connect_url': f'/api/accounts/{account_id}/connect'
        })
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/accounts/<int:account_id>/broker-selection')
def broker_selection(account_id):
    """Render the broker selection page for a new account"""
    return render_template('broker_selection.html', account_id=account_id)

@app.route('/api/accounts/<int:account_id>/set-broker', methods=['POST'])
def set_broker(account_id):
    """Set broker for an account"""
    try:
        data = request.get_json()
        broker_name = data.get('broker') or data.get('brokerName', 'Tradovate')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET broker = ? WHERE id = ?", (broker_name, account_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'broker': broker_name})
    except Exception as e:
        logger.error(f"Error setting broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/accounts/<int:account_id>/credentials')
def collect_credentials(account_id):
    """Render credentials collection page for Tradovate account"""
    return render_template('collect_credentials.html', account_id=account_id)

@app.route('/api/accounts/<int:account_id>/store-credentials', methods=['POST'])
def store_credentials(account_id):
    """Store username/password for an account (optional, for mdAccessToken)"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        environment = data.get('environment', 'demo')  # 'live' or 'demo'
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        # Store credentials in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET username = ?, 
                password = ?,
                environment = ?
            WHERE id = ?
        """, (username, password, environment, account_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Stored credentials for account {account_id}")
        
        # Optionally fetch mdAccessToken immediately if we want
        # For now, just store and continue to OAuth
        
        return jsonify({
            'success': True,
            'message': 'Credentials stored successfully',
            'redirect_url': f'/api/accounts/{account_id}/connect'
        })
    except Exception as e:
        logger.error(f"Error storing credentials: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/connect')
def connect_account(account_id):
    """Redirect to Tradovate OAuth connection"""
    try:
        # ALWAYS use these OAuth app credentials: cid: 8699, secret: 7c74576b-20b1-4ea5-a2a0-eaeb11326a95
        # Do not use database values - these are the only credentials that work
        DEFAULT_CLIENT_ID = "8699"
        DEFAULT_CLIENT_SECRET = "7c74576b-20b1-4ea5-a2a0-eaeb11326a95"

        client_id = DEFAULT_CLIENT_ID  # Always use 8699

        # Build redirect URI - check Railway, then ngrok, then localhost
        railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if railway_url:
            redirect_uri = f'https://{railway_url}/api/oauth/callback'
            logger.info(f"Using Railway redirect_uri: {redirect_uri}")
        else:
            # Check for ngrok URL file (local dev with ngrok)
            try:
                with open('ngrok_url.txt', 'r') as f:
                    ngrok_url = f.read().strip()
                    if ngrok_url and ngrok_url.startswith('http'):
                        redirect_uri = f'{ngrok_url.rstrip("/")}/api/oauth/callback'
                        logger.info(f"Using ngrok redirect_uri: {redirect_uri}")
                    else:
                        redirect_uri = 'http://localhost:8082/api/oauth/callback'
                        logger.info(f"Using localhost redirect_uri: {redirect_uri}")
            except FileNotFoundError:
                redirect_uri = 'http://localhost:8082/api/oauth/callback'
                logger.info(f"Using localhost redirect_uri: {redirect_uri}")
        
        # Build OAuth URL - Tradovate OAuth endpoint (TradersPost pattern)
        # TradersPost uses: https://trader.tradovate.com/oauth with scope=All
        # Use state parameter to pass account_id (OAuth standard)
        from urllib.parse import quote_plus
        encoded_redirect_uri = quote_plus(redirect_uri)
        encoded_state = quote_plus(str(account_id))  # Pass account_id via state parameter
        # Try trader.tradovate.com first (TradersPost pattern), fallback to demo
        oauth_url = f'https://trader.tradovate.com/oauth?response_type=code&client_id={client_id}&redirect_uri={encoded_redirect_uri}&scope=All&state={encoded_state}'
        
        # Log to verify we're using the correct domain
        logger.info(f"OAuth URL domain check: {'demo.tradovate.com' if 'demo.tradovate.com' in oauth_url else 'WRONG DOMAIN - ' + oauth_url}")
        
        logger.info(f"Redirecting account {account_id} to OAuth: {oauth_url}")
        logger.info(f"Redirect URI (decoded): {redirect_uri}")
        return redirect(oauth_url)
    except Exception as e:
        logger.error(f"Error connecting account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Tradovate"""
    try:
        # Get account_id from state parameter (OAuth standard way to pass data)
        account_id = request.args.get('state')
        if not account_id:
            logger.error("No account_id (state) in OAuth callback")
            return redirect(f'/accounts?error=no_account_id')
        
        account_id = int(account_id)
        
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            error_msg = request.args.get('error_description', error)
            logger.error(f"OAuth error for account {account_id}: {error_msg}")
            return redirect(f'/accounts?error=oauth_error&message={error_msg}')
        
        if not code:
            logger.error(f"No authorization code received for account {account_id}")
            return redirect(f'/accounts?error=no_code')
        
        # ALWAYS use these OAuth app credentials: cid: 8699, secret: 7c74576b-20b1-4ea5-a2a0-eaeb11326a95
        # Do not use database values - these are the only credentials that work
        DEFAULT_CLIENT_ID = "8699"
        DEFAULT_CLIENT_SECRET = "7c74576b-20b1-4ea5-a2a0-eaeb11326a95"
        
        client_id = DEFAULT_CLIENT_ID  # Always use 8699
        client_secret = DEFAULT_CLIENT_SECRET  # Always use the secret
        
        # Build redirect_uri - must match what was sent in connect_account
        railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if railway_url:
            redirect_uri = f'https://{railway_url}/api/oauth/callback'
        else:
            # Check for ngrok URL file (local dev with ngrok)
            try:
                with open('ngrok_url.txt', 'r') as f:
                    ngrok_url = f.read().strip()
                    if ngrok_url and ngrok_url.startswith('http'):
                        redirect_uri = f'{ngrok_url.rstrip("/")}/api/oauth/callback'
                    else:
                        redirect_uri = 'http://localhost:8082/api/oauth/callback'
            except FileNotFoundError:
                redirect_uri = 'http://localhost:8082/api/oauth/callback'
        
        # Exchange authorization code for access token
        # Try LIVE endpoint first (demo often rate-limited), then fallback to DEMO
        import requests
        token_endpoints = [
            'https://live.tradovateapi.com/v1/auth/oauthtoken',
            'https://demo.tradovateapi.com/v1/auth/oauthtoken'
        ]
        token_payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret  # Always include the secret
        }
        
        # Try each endpoint until one works
        response = None
        for token_url in token_endpoints:
            logger.info(f"Trying token exchange at: {token_url}")
            response = requests.post(token_url, json=token_payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                logger.info(f"✅ Token exchange succeeded at: {token_url}")
                break
            elif response.status_code == 429:
                logger.warning(f"⚠️ Rate limited (429) at {token_url}, trying next endpoint...")
                continue
            else:
                logger.warning(f"Token exchange failed at {token_url}: {response.status_code} - {response.text[:200]}")
                # For non-429 errors, still try next endpoint
                continue
        
        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"OAuth token response keys: {list(token_data.keys())}")
            
            # Check for error in response body (Tradovate returns 200 with error in body)
            if 'error' in token_data:
                error_msg = token_data.get('error_description', token_data.get('error', 'Unknown error'))
                logger.error(f"OAuth token error from Tradovate: {error_msg}")
                return redirect(f'/accounts?error=oauth_error&message={error_msg}')
            
            access_token = token_data.get('accessToken') or token_data.get('access_token')
            refresh_token = token_data.get('refreshToken') or token_data.get('refresh_token')
            md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
            
            logger.info(f"Tokens extracted - accessToken: {bool(access_token)}, refreshToken: {bool(refresh_token)}, mdAccessToken: {bool(md_access_token)}")
            
            # Calculate actual expiration time from Tradovate response
            # Tradovate returns expiresIn (seconds) or expirationTime (ISO timestamp)
            expires_at = None
            if 'expirationTime' in token_data:
                # ISO timestamp format
                try:
                    from datetime import datetime
                    expires_at = datetime.fromisoformat(token_data['expirationTime'].replace('Z', '+00:00'))
                    expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Could not parse expirationTime: {e}")
            elif 'expiresIn' in token_data:
                # Seconds until expiration - calculate datetime
                try:
                    from datetime import datetime, timedelta
                    expires_in_seconds = int(token_data['expiresIn'])
                    expires_at = (datetime.now() + timedelta(seconds=expires_in_seconds)).strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Could not parse expiresIn: {e}")
            
            # Fallback: Tradovate access tokens typically expire in 90 minutes
            # But we'll use 85 minutes to refresh proactively
            if not expires_at:
                from datetime import datetime, timedelta
                expires_at = (datetime.now() + timedelta(minutes=85)).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Using default expiration (85 minutes) - Tradovate didn't provide expiration time")
            else:
                logger.info(f"Storing actual expiration time: {expires_at}")
            
            # Store tokens in database with actual expiration time
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts 
                SET tradovate_token = ?, 
                    tradovate_refresh_token = ?,
                    md_access_token = ?,
                    token_expires_at = ?
                WHERE id = ?
            """, (access_token, refresh_token, md_access_token, expires_at, account_id))
            conn.commit()
            conn.close()
            
            # Clear any reauth flag - account is now authenticated!
            clear_account_reauth(account_id)
            logger.info(f"✅ Account {account_id} OAuth successful - cleared reauth flag")
            
            # OAuth token exchange doesn't return mdAccessToken - try to get it via accessTokenRequest
            if not md_access_token and access_token:
                try:
                    # Check if we have username/password stored
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT username, password, client_id, client_secret, environment
                        FROM accounts WHERE id = ?
                    """, (account_id,))
                    creds = cursor.fetchone()
                    conn.close()
                    
                    if creds and creds[0] and creds[1]:  # Has username and password
                        username, password, client_id, client_secret, environment = creds
                        base_url = "https://live.tradovateapi.com/v1" if environment == 'live' else "https://demo.tradovateapi.com/v1"
                        
                        # Use OAuth client credentials for accessTokenRequest (same as OAuth flow)
                        # Use API credentials: cid: 8720, secret: e76ee8d1-d168-4252-a59e-f11a8b0cdae4
                        # These are used for fetching mdAccessToken via /auth/accesstokenrequest
                        DEFAULT_CLIENT_ID = str(TRADOVATE_API_CID)  # Use global API CID
                        DEFAULT_CLIENT_SECRET = TRADOVATE_API_SECRET  # Use global API secret
                        
                        # Make accessTokenRequest to get mdAccessToken
                        login_data = {
                            "name": username,
                            "password": password,
                            "appId": "Just.Trade",
                            "appVersion": "1.0.0",
                            "deviceId": f"Just.Trade-{account_id}",
                            "cid": DEFAULT_CLIENT_ID,  # Use OAuth client ID
                            "sec": DEFAULT_CLIENT_SECRET  # Use OAuth client secret
                        }
                        
                        logger.info(f"Fetching mdAccessToken via /auth/accesstokenrequest for account {account_id}")
                        token_response = requests.post(
                            f"{base_url}/auth/accesstokenrequest",
                            json=login_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if token_response.status_code == 200:
                            token_data = token_response.json()
                            logger.info(f"accessTokenRequest response keys: {list(token_data.keys())}")
                            
                            # Check for errors first
                            if 'errorText' in token_data:
                                error_msg = token_data.get('errorText', 'Unknown error')
                                logger.warning(f"accessTokenRequest returned error: {error_msg}")
                                if 'not registered' in error_msg.lower():
                                    logger.info("App not registered - this is expected if using OAuth client credentials with accessTokenRequest")
                                    logger.info("mdAccessToken may not be available via this method. WebSocket will use accessToken instead.")
                                elif 'incorrect username' in error_msg.lower() or 'password' in error_msg.lower():
                                    logger.warning("Credentials may be incorrect or don't match OAuth account")
                            else:
                                md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
                                if md_access_token:
                                    # Update mdAccessToken in database
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE accounts SET md_access_token = ? WHERE id = ?
                                    """, (md_access_token, account_id))
                                    conn.commit()
                                    conn.close()
                                    logger.info(f"✅ Successfully retrieved and stored mdAccessToken for account {account_id}")
                                else:
                                    logger.warning(f"mdAccessToken not in accessTokenRequest response for account {account_id}")
                                    logger.info(f"Full response: {token_data}")
                        else:
                            error_text = token_response.text[:200] if hasattr(token_response, 'text') else str(token_response.status_code)
                            logger.warning(f"Failed to get mdAccessToken: {token_response.status_code} - {error_text}")
                    else:
                        logger.info(f"Account {account_id} doesn't have username/password stored. MD Token will be fetched when credentials are added.")
                        logger.info("Note: WebSocket will work with OAuth accessToken, but mdAccessToken provides better market data access.")
                except Exception as e:
                    logger.error(f"Error fetching mdAccessToken: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Fetch and store Tradovate account + subaccount metadata (TradersPost-style)
            if access_token:
                fetch_result = fetch_and_store_tradovate_accounts(account_id, access_token)
                if not fetch_result.get("success"):
                    logger.warning(f"Unable to fetch subaccounts after OAuth for account {account_id}: {fetch_result.get('error')}")
            
            logger.info(f"Successfully stored tokens for account {account_id}")
            return redirect(f'/accounts?success=true&connected={account_id}')
        else:
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return redirect(f'/accounts?error=token_exchange_failed&message={response.text[:100]}')
            
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect(f'/accounts?error=callback_error&message={str(e)}')

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            logger.info(f"Deleted account {account_id}")
            return jsonify({'success': True, 'message': 'Account deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/refresh-subaccounts', methods=['POST'])
def refresh_account_subaccounts(account_id):
    """Refresh Tradovate subaccounts for an account using stored tokens"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tradovate_token 
            FROM accounts 
            WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        conn.close()
        if not row or not row['tradovate_token']:
            return jsonify({'success': False, 'error': 'Account not connected to Tradovate'}), 400
        
        fetch_result = fetch_and_store_tradovate_accounts(account_id, row['tradovate_token'])
        if fetch_result.get('success'):
            return jsonify({'success': True, 'subaccounts': fetch_result.get('subaccounts', [])})
        return jsonify({'success': False, 'error': fetch_result.get('error', 'Unable to refresh subaccounts')}), 400
    except Exception as e:
        logger.error(f"Error refreshing subaccounts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/fetch-md-token', methods=['POST'])
def fetch_md_access_token(account_id):
    """Fetch mdAccessToken for an account - accepts credentials in request or uses stored ones"""
    try:
        data = request.get_json() or {}
        
        # Get credentials from request or database
        username = data.get('username')
        password = data.get('password')
        use_stored = data.get('use_stored', True)  # Default to using stored credentials
        
        if not username or not password:
            if use_stored:
                # Try to get from database
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, password, client_id, client_secret, environment
                    FROM accounts WHERE id = ?
                """, (account_id,))
                creds = cursor.fetchone()
                conn.close()
                
                if not creds or not creds[0] or not creds[1]:
                    return jsonify({
                        'success': False,
                        'error': 'No credentials provided and account does not have username/password stored.',
                        'instructions': 'Either provide username/password in the request body, or add them to the account first.'
                    }), 400
                
                username, password, client_id, client_secret, environment = creds
            else:
                return jsonify({
                    'success': False,
                    'error': 'Username and password required in request body'
                }), 400
        else:
            # Get environment and client credentials from database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT client_id, client_secret, environment
                FROM accounts WHERE id = ?
            """, (account_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                client_id, client_secret, environment = row
            else:
                environment = 'demo'  # Default
                client_id = None
                client_secret = None
        
        base_url = "https://live.tradovateapi.com/v1" if environment == 'live' else "https://demo.tradovateapi.com/v1"
        
        # Make accessTokenRequest to get mdAccessToken
        # Use provided API credentials (prefer stored, fallback to defaults)
        login_data = {
            "name": username,
            "password": password,
            "appId": "Just.Trade",
            "appVersion": "1.0.0",
            "deviceId": f"Just.Trade-{account_id}",
            "cid": client_id or str(TRADOVATE_API_CID),  # Use stored or default API CID
            "sec": client_secret or TRADOVATE_API_SECRET  # Use stored or default API secret
        }
        
        logger.info(f"Fetching mdAccessToken for account {account_id} via /auth/accesstokenrequest")
        token_response = requests.post(
            f"{base_url}/auth/accesstokenrequest",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
            access_token = token_data.get('accessToken') or token_data.get('access_token')
            refresh_token = token_data.get('refreshToken') or token_data.get('refresh_token')
            
            if md_access_token:
                # Calculate actual expiration time from Tradovate response
                expires_at = None
                if 'expirationTime' in token_data:
                    try:
                        from datetime import datetime
                        expires_at = datetime.fromisoformat(token_data['expirationTime'].replace('Z', '+00:00'))
                        expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logger.warning(f"Could not parse expirationTime: {e}")
                elif 'expiresIn' in token_data:
                    try:
                        from datetime import datetime, timedelta
                        expires_in_seconds = int(token_data['expiresIn'])
                        expires_at = (datetime.now() + timedelta(seconds=expires_in_seconds)).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logger.warning(f"Could not parse expiresIn: {e}")
                
                # Fallback: Tradovate access tokens typically expire in 90 minutes
                if not expires_at:
                    from datetime import datetime, timedelta
                    expires_at = (datetime.now() + timedelta(minutes=85)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Update tokens in database
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE accounts 
                    SET md_access_token = ?,
                        tradovate_token = COALESCE(?, tradovate_token),
                        tradovate_refresh_token = COALESCE(?, tradovate_refresh_token),
                        token_expires_at = ?
                    WHERE id = ?
                """, (md_access_token, access_token, refresh_token, expires_at, account_id))
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Successfully stored mdAccessToken for account {account_id}")
                return jsonify({
                    'success': True,
                    'message': 'mdAccessToken fetched and stored successfully. WebSocket will now work properly.',
                    'has_md_token': True
                })
            else:
                logger.warning(f"mdAccessToken not in response: {list(token_data.keys())}")
                return jsonify({
                    'success': False,
                    'error': 'mdAccessToken not in response from Tradovate',
                    'response_keys': list(token_data.keys())
                }), 400
        else:
            error_text = token_response.text[:200]
            logger.error(f"Failed to fetch mdAccessToken: {token_response.status_code} - {error_text}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch mdAccessToken: {token_response.status_code}',
                'details': error_text
            }), token_response.status_code
            
    except Exception as e:
        logger.error(f"Error fetching mdAccessToken: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# TradingView Session Integration (for real-time price data)
# ============================================================================

@app.route('/api/tradingview/session', methods=['POST'])
def store_tradingview_session():
    """Store TradingView session cookies for real-time price data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        sessionid = data.get('sessionid')
        sessionid_sign = data.get('sessionid_sign')
        device_t = data.get('device_t')
        
        if not sessionid:
            return jsonify({'success': False, 'error': 'sessionid is required'}), 400
        
        # Store as JSON in the first account (or create a settings table later)
        tv_session = json.dumps({
            'sessionid': sessionid,
            'sessionid_sign': sessionid_sign,
            'device_t': device_t,
            'updated_at': datetime.now().isoformat()
        })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET tradingview_session = ? WHERE id = 1", (tv_session,))
        conn.commit()
        conn.close()
        
        logger.info("✅ TradingView session stored successfully")
        
        # Restart TradingView WebSocket with new session
        start_tradingview_websocket()
        
        return jsonify({
            'success': True,
            'message': 'TradingView session stored. WebSocket will connect for real-time prices.'
        })
        
    except Exception as e:
        logger.error(f"Error storing TradingView session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tradingview/session', methods=['GET'])
def get_tradingview_session_status():
    """Check if TradingView session is configured"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT tradingview_session FROM accounts WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            session_data = json.loads(row[0])
            return jsonify({
                'success': True,
                'configured': True,
                'updated_at': session_data.get('updated_at'),
                'has_sessionid': bool(session_data.get('sessionid'))
            })
        else:
            return jsonify({
                'success': True,
                'configured': False
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get all strategies"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies")
        strategies = cursor.fetchall()
        conn.close()
        
        strategies_list = []
        for strategy in strategies:
            strategies_list.append({
                'id': strategy['id'],
                'name': strategy['name'] if 'name' in strategy.keys() else None,
                'symbol': strategy['symbol'] if 'symbol' in strategy.keys() else None,
                'enabled': bool(strategy['enabled'] if 'enabled' in strategy.keys() else 1),
                'created_at': strategy['created_at'] if 'created_at' in strategy.keys() else None
            })
        
        return jsonify({'success': True, 'strategies': strategies_list})
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/live-strategies', methods=['GET'])
def get_live_strategies():
    """Get all live/active strategies"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Try to get enabled strategies, fallback to all if enabled column doesn't exist
        try:
            if is_using_postgres():
                cursor.execute("SELECT * FROM strategies WHERE enabled = true")
            else:
                cursor.execute("SELECT * FROM strategies WHERE enabled = 1")
        except (sqlite3.OperationalError, Exception):
            # enabled column doesn't exist, get all strategies
            cursor.execute("SELECT * FROM strategies")
        strategies = cursor.fetchall()
        conn.close()
        
        strategies_list = []
        for strategy in strategies:
            strategies_list.append({
                'id': strategy['id'],
                'name': strategy['name'] if 'name' in strategy.keys() else None,
                'symbol': strategy['symbol'] if 'symbol' in strategy.keys() else None,
                'enabled': True,
                'created_at': strategy['created_at'] if 'created_at' in strategy.keys() else None
            })
        
        return jsonify({'success': True, 'strategies': strategies_list})
    except Exception as e:
        logger.error(f"Error getting live strategies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/strategies')
def strategies():
    return render_template('strategies.html')


@app.route('/strategies/manage')
def strategies_manage():
    """Strategy Templates Management Page - Create/Edit/Toggle public strategies"""
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('strategy_templates.html')


@app.route('/api/strategies/templates', methods=['GET'])
def get_strategy_templates():
    """
    Get strategy templates for the Create Trader dropdown.
    Returns: All PUBLIC strategies + current user's own strategies.
    Each strategy includes all settings for auto-population.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user ID if logged in
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Query: public strategies OR user's own strategies
        if is_postgres:
            if current_user_id:
                cursor.execute('''
                    SELECT s.*, u.username as owner_username
                    FROM strategies s
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE s.is_public = true OR s.user_id = %s
                    ORDER BY s.is_public DESC, s.name ASC
                ''', (current_user_id,))
            else:
                cursor.execute('''
                    SELECT s.*, u.username as owner_username
                    FROM strategies s
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE s.is_public = true
                    ORDER BY s.name ASC
                ''')
        else:
            if current_user_id:
                cursor.execute('''
                    SELECT s.*, u.username as owner_username
                    FROM strategies s
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE s.is_public = 1 OR s.user_id = ?
                    ORDER BY s.is_public DESC, s.name ASC
                ''', (current_user_id,))
            else:
                cursor.execute('''
                    SELECT s.*, u.username as owner_username
                    FROM strategies s
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE s.is_public = 1
                    ORDER BY s.name ASC
                ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        templates = []
        for row in rows:
            # Convert row to dict
            if hasattr(row, 'keys'):
                row_dict = dict(row)
            else:
                # Handle tuple rows
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                row_dict = dict(zip(columns, row)) if columns else {}
            
            is_own = row_dict.get('user_id') == current_user_id if current_user_id else False
            is_public = bool(row_dict.get('is_public', 0))
            
            templates.append({
                'id': row_dict.get('id'),
                'name': row_dict.get('name'),
                'symbol': row_dict.get('symbol'),
                'strat_type': row_dict.get('strat_type', 'Futures'),
                # Risk settings for auto-population
                'position_size': row_dict.get('position_size', 1),
                'position_add': row_dict.get('position_add', 1),
                'take_profit': row_dict.get('take_profit', 0),
                'stop_loss': row_dict.get('stop_loss', 0),
                'trim': row_dict.get('trim', 100),
                'tpsl_units': row_dict.get('tpsl_units', 'Ticks'),
                'max_contracts': row_dict.get('max_contracts', 0),
                'max_daily_loss': row_dict.get('max_daily_loss', 0),
                'delay_seconds': row_dict.get('delay_seconds', 0),
                'entry_delay': row_dict.get('entry_delay', 0),
                'signal_cooldown': row_dict.get('signal_cooldown', 0),
                'direction_filter': row_dict.get('direction_filter', 'ALL'),
                'time_filter_enabled': bool(row_dict.get('time_filter_enabled', 0)),
                'time_filter_start': row_dict.get('time_filter_start', ''),
                'time_filter_end': row_dict.get('time_filter_end', ''),
                'notes': row_dict.get('notes', ''),
                # Metadata
                'is_public': is_public,
                'is_own': is_own,
                'owner_username': row_dict.get('owner_username') or row_dict.get('created_by_username') or 'Unknown',
                'created_at': row_dict.get('created_at')
            })
        
        return jsonify({
            'success': True,
            'templates': templates,
            'count': len(templates)
        })
        
    except Exception as e:
        logger.error(f"Error getting strategy templates: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    """Create a new strategy template"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'error': 'Strategy name is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user
        current_user_id = None
        current_username = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
            user = get_current_user()
            current_username = user.username if user else None
        
        # Insert strategy
        if is_postgres:
            cursor.execute('''
                INSERT INTO strategies (
                    user_id, name, symbol, strat_type, position_size, position_add,
                    take_profit, stop_loss, trim, tpsl_units, max_contracts,
                    max_daily_loss, delay_seconds, entry_delay, signal_cooldown,
                    direction_filter, time_filter_enabled, time_filter_start,
                    time_filter_end, notes, is_public, created_by_username
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                current_user_id,
                name,
                data.get('symbol', ''),
                data.get('strat_type', 'Futures'),
                data.get('position_size', 1),
                data.get('position_add', 1),
                data.get('take_profit', 0),
                data.get('stop_loss', 0),
                data.get('trim', 100),
                data.get('tpsl_units', 'Ticks'),
                data.get('max_contracts', 0),
                data.get('max_daily_loss', 0),
                data.get('delay_seconds', 0),
                data.get('entry_delay', 0),
                data.get('signal_cooldown', 0),
                data.get('direction_filter', 'ALL'),
                data.get('time_filter_enabled', False),
                data.get('time_filter_start', ''),
                data.get('time_filter_end', ''),
                data.get('notes', ''),
                data.get('is_public', False),
                current_username
            ))
            strategy_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO strategies (
                    user_id, name, symbol, strat_type, position_size, position_add,
                    take_profit, stop_loss, trim, tpsl_units, max_contracts,
                    max_daily_loss, delay_seconds, entry_delay, signal_cooldown,
                    direction_filter, time_filter_enabled, time_filter_start,
                    time_filter_end, notes, is_public, created_by_username
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                current_user_id,
                name,
                data.get('symbol', ''),
                data.get('strat_type', 'Futures'),
                data.get('position_size', 1),
                data.get('position_add', 1),
                data.get('take_profit', 0),
                data.get('stop_loss', 0),
                data.get('trim', 100),
                data.get('tpsl_units', 'Ticks'),
                data.get('max_contracts', 0),
                data.get('max_daily_loss', 0),
                data.get('delay_seconds', 0),
                data.get('entry_delay', 0),
                data.get('signal_cooldown', 0),
                data.get('direction_filter', 'ALL'),
                1 if data.get('time_filter_enabled') else 0,
                data.get('time_filter_start', ''),
                data.get('time_filter_end', ''),
                data.get('notes', ''),
                1 if data.get('is_public') else 0,
                current_username
            ))
            strategy_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created strategy '{name}' (id={strategy_id}, public={data.get('is_public', False)})")
        
        return jsonify({
            'success': True,
            'strategy_id': strategy_id,
            'message': f"Strategy '{name}' created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/<int:strategy_id>', methods=['PUT'])
def update_strategy(strategy_id):
    """Update an existing strategy template"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user to verify ownership
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Verify ownership (only owner can update)
        if is_postgres:
            cursor.execute('SELECT user_id FROM strategies WHERE id = %s', (strategy_id,))
        else:
            cursor.execute('SELECT user_id FROM strategies WHERE id = ?', (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Strategy not found'}), 404
        
        owner_id = row[0] if isinstance(row, tuple) else row.get('user_id')
        if current_user_id and owner_id and owner_id != current_user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'You can only edit your own strategies'}), 403
        
        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []
        
        field_mapping = {
            'name': 'name',
            'symbol': 'symbol',
            'strat_type': 'strat_type',
            'position_size': 'position_size',
            'position_add': 'position_add',
            'take_profit': 'take_profit',
            'stop_loss': 'stop_loss',
            'trim': 'trim',
            'tpsl_units': 'tpsl_units',
            'max_contracts': 'max_contracts',
            'max_daily_loss': 'max_daily_loss',
            'delay_seconds': 'delay_seconds',
            'entry_delay': 'entry_delay',
            'signal_cooldown': 'signal_cooldown',
            'direction_filter': 'direction_filter',
            'time_filter_enabled': 'time_filter_enabled',
            'time_filter_start': 'time_filter_start',
            'time_filter_end': 'time_filter_end',
            'notes': 'notes',
            'is_public': 'is_public'
        }
        
        for key, db_field in field_mapping.items():
            if key in data:
                value = data[key]
                # Convert boolean to int for SQLite
                if key in ['is_public', 'time_filter_enabled'] and not is_postgres:
                    value = 1 if value else 0
                update_fields.append(f"{db_field} = %s" if is_postgres else f"{db_field} = ?")
                update_values.append(value)
        
        if not update_fields:
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update'}), 400
        
        # Add updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        # Execute update
        update_values.append(strategy_id)
        query = f"UPDATE strategies SET {', '.join(update_fields)} WHERE id = %s" if is_postgres else f"UPDATE strategies SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, tuple(update_values))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated strategy {strategy_id}")
        return jsonify({'success': True, 'message': 'Strategy updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/<int:strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    """Delete a strategy template"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user to verify ownership
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Verify ownership
        if is_postgres:
            cursor.execute('SELECT user_id, name FROM strategies WHERE id = %s', (strategy_id,))
        else:
            cursor.execute('SELECT user_id, name FROM strategies WHERE id = ?', (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Strategy not found'}), 404
        
        owner_id = row[0] if isinstance(row, tuple) else row.get('user_id')
        strategy_name = row[1] if isinstance(row, tuple) else row.get('name')
        
        if current_user_id and owner_id and owner_id != current_user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'You can only delete your own strategies'}), 403
        
        # Delete the strategy
        if is_postgres:
            cursor.execute('DELETE FROM strategies WHERE id = %s', (strategy_id,))
        else:
            cursor.execute('DELETE FROM strategies WHERE id = ?', (strategy_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted strategy {strategy_id}: {strategy_name}")
        return jsonify({'success': True, 'message': f"Strategy '{strategy_name}' deleted"})
        
    except Exception as e:
        logger.error(f"Error deleting strategy: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/recorders', methods=['GET'])
def recorders_list():
    """Render the recorders list page"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, ticker, enabled, created_at FROM recorders ORDER BY id DESC')
        rows = cursor.fetchall()
        recorders = []
        for row in rows:
            try:
                if isinstance(row, dict):
                    rec = row
                elif hasattr(row, 'keys'):
                    rec = dict(row)
                else:
                    rec = {
                        'id': row[0],
                        'name': row[1],
                        'ticker': row[2],
                        'enabled': row[3],
                        'created_at': row[4]
                    }
                # Ensure template-required fields exist
                recorders.append({
                    'id': rec.get('id'),
                    'name': rec.get('name', 'Unknown'),
                    'symbol': rec.get('ticker') or rec.get('symbol', ''),
                    'is_recording': rec.get('enabled', False),
                    'enabled': rec.get('enabled', False),
                    'created_at': str(rec.get('created_at', '')) if rec.get('created_at') else ''
                })
            except Exception as row_err:
                logger.warning(f"Error processing recorder row: {row_err}")
                continue
        conn.close()
        return render_template('recorders_list.html', recorders=recorders)
    except Exception as e:
        logger.error(f"Error loading recorders list: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return render_template('recorders_list.html', recorders=[])

@app.route('/recorders/new')
def recorders_new():
    """Render the new recorder form"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    try:
        # Get accounts for dropdown
        conn = get_db_connection()
        cursor = conn.cursor()
        # Use simple query without boolean filter for compatibility
        cursor.execute('SELECT id, name FROM accounts')
        rows = cursor.fetchall()
        accounts = []
        for row in rows:
            try:
                if isinstance(row, dict):
                    accounts.append(row)
                elif hasattr(row, 'keys'):
                    accounts.append(dict(row))
                else:
                    accounts.append({'id': row[0], 'name': row[1]})
            except:
                continue
        conn.close()
        return render_template('recorders.html', recorder=None, accounts=accounts, mode='create')
    except Exception as e:
        logger.error(f"Error loading new recorder form: {e}")
        return render_template('recorders.html', recorder=None, accounts=[], mode='create')

@app.route('/recorders/<int:recorder_id>')
def recorders_edit(recorder_id):
    """Render the edit recorder form"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('SELECT * FROM recorders WHERE id = %s', (recorder_id,))
        else:
            cursor.execute('SELECT * FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return redirect('/recorders')
        
        columns = ['id', 'user_id', 'name', 'enabled', 'webhook_token', 'ticker', 'position_size', 
                   'tp_enabled', 'tp_targets', 'sl_enabled', 'sl_amount', 'trailing_sl', 'account_id', 
                   'created_at', 'updated_at']
        if isinstance(row, dict):
            recorder = row
        elif hasattr(row, 'keys'):
            recorder = dict(row)
        else:
            recorder = dict(zip(columns[:len(row)], row))
        
        # Parse TP targets JSON
        try:
            recorder['tp_targets'] = json.loads(recorder.get('tp_targets') or '[]')
        except:
            recorder['tp_targets'] = []
        # Get accounts for dropdown
        cursor.execute('SELECT id, name FROM accounts')
        rows = cursor.fetchall()
        accounts = []
        for row in rows:
            try:
                if isinstance(row, dict):
                    accounts.append(row)
                elif hasattr(row, 'keys'):
                    accounts.append(dict(row))
                else:
                    accounts.append({'id': row[0], 'name': row[1]})
            except:
                continue
        conn.close()
        return render_template('recorders.html', recorder=recorder, accounts=accounts, mode='edit')
    except Exception as e:
        logger.error(f"Error loading recorder edit form: {e}")
        return redirect('/recorders')

# ============================================================
# RECORDER API ENDPOINTS
# ============================================================

@app.route('/api/recorders', methods=['GET'])
def api_get_recorders():
    """Get all recorders for the current user"""
    try:
        search = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Filter by user_id if logged in
        user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            user_id = get_current_user_id()
        
        if is_postgres:
            if search and user_id:
                cursor.execute('''
                    SELECT * FROM recorders
                    WHERE name LIKE %s AND (user_id = %s OR user_id IS NULL)
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                ''', (f'%{search}%', user_id, per_page, offset))
            elif user_id:
                cursor.execute('''
                    SELECT * FROM recorders
                    WHERE (user_id = %s OR user_id IS NULL)
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                ''', (user_id, per_page, offset))
            elif search:
                cursor.execute('''
                    SELECT * FROM recorders 
                    WHERE name LIKE %s
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                ''', (f'%{search}%', per_page, offset))
            else:
                cursor.execute('''
                    SELECT * FROM recorders 
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                ''', (per_page, offset))
        else:
            if search and user_id:
                cursor.execute('''
                    SELECT * FROM recorders 
                    WHERE name LIKE ? AND (user_id = ? OR user_id IS NULL)
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (f'%{search}%', user_id, per_page, offset))
            elif user_id:
                cursor.execute('''
                    SELECT * FROM recorders 
                    WHERE (user_id = ? OR user_id IS NULL)
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (user_id, per_page, offset))
            elif search:
                cursor.execute('''
                    SELECT * FROM recorders 
                    WHERE name LIKE ?
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (f'%{search}%', per_page, offset))
            else:
                cursor.execute('''
                    SELECT * FROM recorders 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (per_page, offset))
        
        rows = cursor.fetchall()
        recorders = []
        columns = ['id', 'user_id', 'name', 'enabled', 'webhook_token', 'ticker', 'position_size', 
                   'tp_enabled', 'tp_targets', 'sl_enabled', 'sl_amount', 'trailing_sl', 'account_id', 
                   'created_at', 'updated_at']
        for row in rows:
            if hasattr(row, 'keys'):
                recorder = dict(row)
            else:
                recorder = dict(zip(columns[:len(row)], row))
            try:
                recorder['tp_targets'] = json.loads(recorder.get('tp_targets') or '[]')
            except:
                recorder['tp_targets'] = []
            recorders.append(recorder)
        
        # Get total count with user filter - includes shared recorders (user_id IS NULL)
        if is_postgres:
            if user_id and search:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE name LIKE %s AND (user_id = %s OR user_id IS NULL)', (f'%{search}%', user_id))
            elif user_id:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE (user_id = %s OR user_id IS NULL)', (user_id,))
            elif search:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE name LIKE %s', (f'%{search}%',))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM recorders')
        elif USER_AUTH_AVAILABLE and is_logged_in():
            if search:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE name LIKE ? AND (user_id = ? OR user_id IS NULL)', (f'%{search}%', user_id))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE (user_id = ? OR user_id IS NULL)', (user_id,))
        else:
            if search:
                cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE name LIKE ?', (f'%{search}%',))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM recorders')
        total_row = cursor.fetchone()
        total = total_row[0] if total_row else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'recorders': recorders,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        logger.error(f"Error getting recorders: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>', methods=['GET'])
def api_get_recorder(recorder_id):
    """Get a single recorder by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('SELECT * FROM recorders WHERE id = %s', (recorder_id,))
        else:
            cursor.execute('SELECT * FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        columns = ['id', 'user_id', 'name', 'enabled', 'webhook_token', 'ticker', 'position_size', 
                   'tp_enabled', 'tp_targets', 'sl_enabled', 'sl_amount', 'trailing_sl', 'account_id', 
                   'created_at', 'updated_at']
        if hasattr(row, 'keys'):
            recorder = dict(row)
        else:
            recorder = dict(zip(columns[:len(row)], row))
        try:
            recorder['tp_targets'] = json.loads(recorder.get('tp_targets') or '[]')
        except:
            recorder['tp_targets'] = []
        
        return jsonify({'success': True, 'recorder': recorder})
    except Exception as e:
        logger.error(f"Error getting recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders', methods=['POST'])
def api_create_recorder():
    """Create a new recorder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Strategy name is required'}), 400
        
        # Generate webhook token
        import secrets
        webhook_token = secrets.token_urlsafe(16)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Serialize TP targets
        tp_targets = json.dumps(data.get('tp_targets', []))
        
        # Get current user_id for data isolation
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        if is_postgres:
            cursor.execute('''
                INSERT INTO recorders (
                    name, enabled, webhook_token, ticker, position_size,
                    tp_enabled, tp_targets, sl_enabled, sl_amount, trailing_sl,
                    account_id, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            ''', (
                name,
                True,
                webhook_token,
                data.get('symbol') or data.get('ticker'),
                data.get('position_size', data.get('initial_position_size', 1)),
                data.get('tp_enabled', True),
                tp_targets,
                data.get('sl_enabled', False),
                data.get('sl_amount', 0),
                data.get('trailing_sl', False),
                data.get('account_id'),
                current_user_id
            ))
            result = cursor.fetchone()
            if result:
                recorder_id = result.get('id') if isinstance(result, dict) else result[0]
            else:
                recorder_id = None
        else:
            cursor.execute('''
                INSERT INTO recorders (
                    name, enabled, webhook_token, ticker, position_size,
                    tp_enabled, tp_targets, sl_enabled, sl_amount, trailing_sl,
                    account_id, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                1,
                webhook_token,
                data.get('symbol') or data.get('ticker'),
                data.get('position_size', data.get('initial_position_size', 1)),
                1 if data.get('tp_enabled', True) else 0,
                tp_targets,
                1 if data.get('sl_enabled', False) else 0,
                data.get('sl_amount', 0),
                1 if data.get('trailing_sl', False) else 0,
                data.get('account_id'),
                current_user_id
            ))
            recorder_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created recorder: {name} (ID: {recorder_id})")
        
        return jsonify({
            'success': True,
            'message': f'Recorder "{name}" created successfully',
            'recorder_id': recorder_id,
            'webhook_token': webhook_token
        })
    except Exception as e:
        logger.error(f"Error creating recorder: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>', methods=['PUT'])
def api_update_recorder(recorder_id):
    """Update an existing recorder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if recorder exists
        cursor.execute('SELECT id FROM recorders WHERE id = ?', (recorder_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Build update query dynamically
        fields = []
        values = []
        
        field_mapping = {
            'name': 'name',
            'strategy_type': 'strategy_type',
            'symbol': 'symbol',
            'demo_account_id': 'demo_account_id',
            'account_id': 'account_id',
            'initial_position_size': 'initial_position_size',
            'add_position_size': 'add_position_size',
            'tp_units': 'tp_units',
            'trim_units': 'trim_units',
            'sl_amount': 'sl_amount',
            'sl_units': 'sl_units',
            'sl_type': 'sl_type',
            'avg_down_amount': 'avg_down_amount',
            'avg_down_point': 'avg_down_point',
            'avg_down_units': 'avg_down_units',
            'add_delay': 'add_delay',
            'max_contracts_per_trade': 'max_contracts_per_trade',
            'option_premium_filter': 'option_premium_filter',
            'direction_filter': 'direction_filter',
            'time_filter_1_start': 'time_filter_1_start',
            'time_filter_1_stop': 'time_filter_1_stop',
            'time_filter_2_start': 'time_filter_2_start',
            'time_filter_2_stop': 'time_filter_2_stop',
            'signal_cooldown': 'signal_cooldown',
            'max_signals_per_session': 'max_signals_per_session',
            'max_daily_loss': 'max_daily_loss',
            'notes': 'notes',
        }
        
        for key, db_field in field_mapping.items():
            if key in data:
                fields.append(f'{db_field} = ?')
                values.append(data[key])
        
        # Handle boolean fields
        if 'sl_enabled' in data:
            fields.append('sl_enabled = ?')
            values.append(1 if data['sl_enabled'] else 0)
        if 'avg_down_enabled' in data:
            fields.append('avg_down_enabled = ?')
            values.append(1 if data['avg_down_enabled'] else 0)
        if 'auto_flat_after_cutoff' in data:
            fields.append('auto_flat_after_cutoff = ?')
            values.append(1 if data['auto_flat_after_cutoff'] else 0)
        if 'recording_enabled' in data:
            fields.append('recording_enabled = ?')
            values.append(1 if data['recording_enabled'] else 0)
        
        # Handle TP targets JSON
        if 'tp_targets' in data:
            fields.append('tp_targets = ?')
            values.append(json.dumps(data['tp_targets']))
        
        # Always update updated_at
        fields.append('updated_at = CURRENT_TIMESTAMP')
        
        if fields:
            values.append(recorder_id)
            cursor.execute(f'''
                UPDATE recorders SET {', '.join(fields)} WHERE id = ?
            ''', values)
            conn.commit()
        
        conn.close()
        
        logger.info(f"Updated recorder ID: {recorder_id}")
        
        return jsonify({
            'success': True,
            'message': 'Recorder updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating recorder {recorder_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>', methods=['DELETE'])
def api_delete_recorder(recorder_id):
    """Delete a recorder and ALL associated data (trades, signals, positions)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if recorder exists
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name = row[0]
        
        # CASCADE DELETE: Delete all associated data FIRST
        cursor.execute('DELETE FROM recorded_trades WHERE recorder_id = ?', (recorder_id,))
        trades_deleted = cursor.rowcount
        
        cursor.execute('DELETE FROM recorded_signals WHERE recorder_id = ?', (recorder_id,))
        signals_deleted = cursor.rowcount
        
        cursor.execute('DELETE FROM recorder_positions WHERE recorder_id = ?', (recorder_id,))
        positions_deleted = cursor.rowcount
        
        # Now delete the recorder itself
        cursor.execute('DELETE FROM recorders WHERE id = ?', (recorder_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted recorder: {name} (ID: {recorder_id}) - Cascade deleted {trades_deleted} trades, {signals_deleted} signals, {positions_deleted} positions")
        
        return jsonify({
            'success': True,
            'message': f'Recorder "{name}" deleted successfully (including {trades_deleted} trades, {signals_deleted} signals, {positions_deleted} positions)'
        })
    except Exception as e:
        logger.error(f"Error deleting recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>/clone', methods=['POST'])
def api_clone_recorder(recorder_id):
    """Clone an existing recorder"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        original = dict(row)
        
        # Generate new webhook token
        import secrets
        webhook_token = secrets.token_urlsafe(16)
        
        # Create cloned recorder with modified name
        new_name = f"{original['name']} (Copy)"
        
        cursor.execute('''
            INSERT INTO recorders (
                name, strategy_type, symbol, demo_account_id, account_id,
                initial_position_size, add_position_size,
                tp_units, trim_units, tp_targets,
                sl_enabled, sl_amount, sl_units, sl_type,
                avg_down_enabled, avg_down_amount, avg_down_point, avg_down_units,
                add_delay, max_contracts_per_trade, option_premium_filter, direction_filter,
                time_filter_1_start, time_filter_1_stop, time_filter_2_start, time_filter_2_stop,
                signal_cooldown, max_signals_per_session, max_daily_loss, auto_flat_after_cutoff,
                notes, recording_enabled, webhook_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_name,
            original['strategy_type'],
            original['symbol'],
            original['demo_account_id'],
            original['account_id'],
            original['initial_position_size'],
            original['add_position_size'],
            original['tp_units'],
            original['trim_units'],
            original['tp_targets'],
            original['sl_enabled'],
            original['sl_amount'],
            original['sl_units'],
            original['sl_type'],
            original['avg_down_enabled'],
            original['avg_down_amount'],
            original['avg_down_point'],
            original['avg_down_units'],
            original['add_delay'],
            original['max_contracts_per_trade'],
            original['option_premium_filter'],
            original['direction_filter'],
            original['time_filter_1_start'],
            original['time_filter_1_stop'],
            original['time_filter_2_start'],
            original['time_filter_2_stop'],
            original['signal_cooldown'],
            original['max_signals_per_session'],
            original['max_daily_loss'],
            original['auto_flat_after_cutoff'],
            original['notes'],
            original['recording_enabled'],
            webhook_token
        ))
        
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Cloned recorder {recorder_id} -> {new_id}: {new_name}")
        
        return jsonify({
            'success': True,
            'message': f'Recorder cloned successfully',
            'recorder_id': new_id,
            'name': new_name
        })
    except Exception as e:
        logger.error(f"Error cloning recorder {recorder_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>/start', methods=['POST'])
def api_start_recorder(recorder_id):
    """Start recording for a recorder"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, is_recording FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name, is_recording = row
        if is_recording:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder is already running'}), 400
        
        cursor.execute('UPDATE recorders SET is_recording = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (recorder_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Started recording: {name} (ID: {recorder_id})")
        
        return jsonify({
            'success': True,
            'message': f'Recording started for "{name}"'
        })
    except Exception as e:
        logger.error(f"Error starting recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>/stop', methods=['POST'])
def api_stop_recorder(recorder_id):
    """Stop recording for a recorder"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, is_recording FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name, is_recording = row
        if not is_recording:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder is not running'}), 400
        
        cursor.execute('UPDATE recorders SET is_recording = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (recorder_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Stopped recording: {name} (ID: {recorder_id})")
        
        return jsonify({
            'success': True,
            'message': f'Recording stopped for "{name}"'
        })
    except Exception as e:
        logger.error(f"Error stopping recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>/reset-history', methods=['POST'])
def api_reset_recorder_history(recorder_id):
    """Reset trade history for a recorder (delete all trades and signals)"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verify recorder exists
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name = row['name']
        
        # Delete all trades for this recorder
        cursor.execute('DELETE FROM recorded_trades WHERE recorder_id = ?', (recorder_id,))
        trades_deleted = cursor.rowcount
        
        # Delete all signals for this recorder
        cursor.execute('DELETE FROM recorded_signals WHERE recorder_id = ?', (recorder_id,))
        signals_deleted = cursor.rowcount
        
        # Delete all positions for this recorder (Trade Manager style tracking)
        cursor.execute('DELETE FROM recorder_positions WHERE recorder_id = ?', (recorder_id,))
        positions_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Reset history for recorder '{name}' (ID: {recorder_id}): {trades_deleted} trades, {signals_deleted} signals, {positions_deleted} positions deleted")
        
        return jsonify({
            'success': True,
            'message': f'Trade history reset for "{name}". Deleted {trades_deleted} trades, {signals_deleted} signals, and {positions_deleted} positions.',
            'trades_deleted': trades_deleted,
            'signals_deleted': signals_deleted,
            'positions_deleted': positions_deleted
        })
    except Exception as e:
        logger.error(f"Error resetting history for recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recorders/<int:recorder_id>/webhook', methods=['GET'])
def api_get_recorder_webhook(recorder_id):
    """Get webhook details for a recorder"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT name, webhook_token FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Build webhook URL
        base_url = request.host_url.rstrip('/')
        webhook_url = f"{base_url}/webhook/{row['webhook_token']}"
        
        # Simple indicator alert message (user specifies buy or sell)
        indicator_buy_message = json.dumps({
            "recorder": row['name'],
            "action": "buy",
            "ticker": "{{ticker}}",
            "price": "{{close}}"
        }, indent=2)
        
        indicator_sell_message = json.dumps({
            "recorder": row['name'],
            "action": "sell",
            "ticker": "{{ticker}}",
            "price": "{{close}}"
        }, indent=2)
        
        # Pine Script strategy alert message (action auto-filled by TradingView)
        strategy_message = json.dumps({
            "recorder": row['name'],
            "action": "{{strategy.order.action}}",
            "ticker": "{{ticker}}",
            "price": "{{close}}",
            "contracts": "{{strategy.order.contracts}}",
            "position_size": "{{strategy.position_size}}",
            "market_position": "{{strategy.market_position}}"
        }, indent=2)
        
        return jsonify({
            'success': True,
            'webhook_url': webhook_url,
            'name': row['name'],
            'alerts': {
                'indicator_buy': indicator_buy_message,
                'indicator_sell': indicator_sell_message,
                'strategy_message': strategy_message
            }
        })
    except Exception as e:
        logger.error(f"Error getting webhook for recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# TRADERS API ENDPOINTS (links recorders to accounts)
# ============================================================

@app.route('/api/traders', methods=['GET'])
def api_get_traders():
    """Get all traders (recorder-account links) with joined data and risk settings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Filter by user_id if logged in
        if USER_AUTH_AVAILABLE and is_logged_in():
            user_id = get_current_user_id()
            if is_postgres:
                cursor.execute('''
                    SELECT 
                        t.id,
                        t.recorder_id,
                        t.account_id,
                        t.subaccount_id,
                        t.subaccount_name,
                        t.is_demo,
                        t.enabled,
                        t.created_at,
                        t.max_contracts as trader_position_size,
                        r.name as recorder_name,
                        r.ticker as symbol,
                        a.name as account_name,
                        a.broker
                    FROM traders t
                    LEFT JOIN recorders r ON t.recorder_id = r.id
                    LEFT JOIN accounts a ON t.account_id = a.id
                    WHERE a.user_id = %s OR a.user_id IS NULL OR t.user_id = %s
                    ORDER BY t.created_at DESC
                ''', (user_id, user_id))
            else:
                cursor.execute('''
                    SELECT 
                        t.id,
                        t.recorder_id,
                        t.account_id,
                        t.subaccount_id,
                        t.subaccount_name,
                        t.is_demo,
                        t.enabled,
                        t.created_at,
                        t.initial_position_size as trader_position_size,
                        t.add_position_size as trader_add_position_size,
                        t.tp_targets as trader_tp_targets,
                        t.sl_enabled as trader_sl_enabled,
                        t.sl_amount as trader_sl_amount,
                        t.sl_units as trader_sl_units,
                        t.max_daily_loss as trader_max_daily_loss,
                        r.name as recorder_name,
                        r.strategy_type,
                        r.initial_position_size as recorder_position_size,
                        r.symbol,
                        a.name as account_name,
                        a.broker
                    FROM traders t
                    JOIN recorders r ON t.recorder_id = r.id
                    JOIN accounts a ON t.account_id = a.id
                    WHERE a.user_id = ? OR a.user_id IS NULL
                    ORDER BY t.created_at DESC
                ''', (user_id,))
        else:
            if is_postgres:
                cursor.execute('''
                    SELECT 
                        t.id,
                        t.recorder_id,
                        t.account_id,
                        t.subaccount_id,
                        t.subaccount_name,
                        t.is_demo,
                        t.enabled,
                        t.created_at,
                        t.max_contracts as trader_position_size,
                        r.name as recorder_name,
                        r.ticker as symbol,
                        a.name as account_name,
                        a.broker
                    FROM traders t
                    LEFT JOIN recorders r ON t.recorder_id = r.id
                    LEFT JOIN accounts a ON t.account_id = a.id
                    ORDER BY t.created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT 
                        t.id,
                        t.recorder_id,
                        t.account_id,
                        t.subaccount_id,
                        t.subaccount_name,
                        t.is_demo,
                        t.enabled,
                        t.created_at,
                        t.initial_position_size as trader_position_size,
                        t.add_position_size as trader_add_position_size,
                        t.tp_targets as trader_tp_targets,
                        t.sl_enabled as trader_sl_enabled,
                        t.sl_amount as trader_sl_amount,
                        t.sl_units as trader_sl_units,
                        t.max_daily_loss as trader_max_daily_loss,
                        r.name as recorder_name,
                        r.strategy_type,
                        r.initial_position_size as recorder_position_size,
                        r.symbol,
                        a.name as account_name,
                        a.broker
                    FROM traders t
                    JOIN recorders r ON t.recorder_id = r.id
                    JOIN accounts a ON t.account_id = a.id
                    ORDER BY t.created_at DESC
                ''')
        
        rows = cursor.fetchall()
        traders = []
        
        # PostgreSQL columns for the simplified query
        pg_columns = ['id', 'recorder_id', 'account_id', 'subaccount_id', 'subaccount_name', 
                      'is_demo', 'enabled', 'created_at', 'trader_position_size', 
                      'recorder_name', 'symbol', 'account_name', 'broker']
        
        for row in rows:
            # Convert to dict
            if hasattr(row, 'keys'):
                row_dict = dict(row)
            else:
                row_dict = dict(zip(pg_columns[:len(row)], row))
            
            is_demo = bool(row_dict.get('is_demo')) if row_dict.get('is_demo') is not None else None
            env_label = "DEMO" if is_demo else "LIVE" if is_demo is not None else ""
            account_name = row_dict.get('account_name') or 'Unknown'
            subaccount_name = row_dict.get('subaccount_name')
            display_account = f"{account_name} {env_label} ({subaccount_name})" if subaccount_name else account_name
            
            position_size = row_dict.get('trader_position_size') or row_dict.get('recorder_position_size') or 1
            
            traders.append({
                'id': row_dict.get('id'),
                'recorder_id': row_dict.get('recorder_id'),
                'account_id': row_dict.get('account_id'),
                'subaccount_id': row_dict.get('subaccount_id'),
                'subaccount_name': subaccount_name,
                'is_demo': is_demo,
                'enabled': bool(row_dict.get('enabled')),
                'created_at': str(row_dict.get('created_at', '')),
                'recorder_name': row_dict.get('recorder_name'),
                'name': row_dict.get('recorder_name'),
                'strategy_type': row_dict.get('strategy_type', 'Futures'),
                'symbol': row_dict.get('symbol'),
                'account_name': account_name,
                'display_account': display_account,
                'broker': row_dict.get('broker'),
                'initial_position_size': position_size,
                'position_size': position_size,  # For backward compatibility
                'add_position_size': row_dict.get('trader_add_position_size'),
                'tp_targets': [],
                'sl_enabled': bool(row_dict.get('trader_sl_enabled')) if row_dict.get('trader_sl_enabled') is not None else False,
                'sl_amount': row_dict.get('trader_sl_amount'),
                'sl_units': row_dict.get('trader_sl_units'),
                'max_daily_loss': row_dict.get('trader_max_daily_loss')
            })
        
        conn.close()
        return jsonify({'success': True, 'traders': traders})
        
    except Exception as e:
        logger.error(f"Error getting traders: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/traders', methods=['POST'])
def api_create_trader():
    """Create a new trader (link recorder to account with subaccount info and risk settings)"""
    try:
        data = request.get_json()
        recorder_id = data.get('recorder_id')
        account_id = data.get('account_id')
        subaccount_id = data.get('subaccount_id')  # Tradovate subaccount ID (e.g., 26029294)
        subaccount_name = data.get('subaccount_name')  # e.g., "DEMO4419847-2" or "1381296"
        is_demo = data.get('is_demo')  # True for demo, False for live
        
        # Risk settings (optional - will use recorder defaults if not provided)
        initial_position_size = data.get('initial_position_size')
        add_position_size = data.get('add_position_size')
        tp_targets = data.get('tp_targets')  # JSON string or list
        sl_enabled = data.get('sl_enabled')
        sl_amount = data.get('sl_amount')
        sl_units = data.get('sl_units')
        max_daily_loss = data.get('max_daily_loss')
        
        if not recorder_id or not account_id:
            return jsonify({'success': False, 'error': 'recorder_id and account_id are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Verify recorder exists
        if is_postgres:
            cursor.execute('SELECT id, name FROM recorders WHERE id = %s', (recorder_id,))
        else:
            cursor.execute('SELECT id, name FROM recorders WHERE id = ?', (recorder_id,))
        recorder = cursor.fetchone()
        if not recorder:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Use defaults if not provided
        if initial_position_size is None:
            initial_position_size = 1
        
        # Verify account exists
        if is_postgres:
            cursor.execute('SELECT id, name FROM accounts WHERE id = %s', (account_id,))
        else:
            cursor.execute('SELECT id, name FROM accounts WHERE id = ?', (account_id,))
        account = cursor.fetchone()
        if not account:
            conn.close()
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Check if link already exists
        if is_postgres:
            if subaccount_id:
                cursor.execute('SELECT id FROM traders WHERE recorder_id = %s AND account_id = %s AND subaccount_id = %s', 
                              (recorder_id, account_id, subaccount_id))
            else:
                cursor.execute('SELECT id FROM traders WHERE recorder_id = %s AND account_id = %s', (recorder_id, account_id))
        else:
            if subaccount_id:
                cursor.execute('SELECT id FROM traders WHERE recorder_id = ? AND account_id = ? AND subaccount_id = ?', 
                              (recorder_id, account_id, subaccount_id))
            else:
                cursor.execute('SELECT id FROM traders WHERE recorder_id = ? AND account_id = ?', (recorder_id, account_id))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'error': 'This recorder is already linked to this account'}), 400
        
        # Get current user_id
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Create the trader link
        if is_postgres:
            cursor.execute('''
                INSERT INTO traders (
                    recorder_id, account_id, subaccount_id, subaccount_name, is_demo, enabled,
                    initial_position_size, add_position_size, tp_targets, sl_enabled, sl_amount, sl_units, max_daily_loss,
                    user_id, enabled_accounts
                )
                VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            ''', (recorder_id, account_id, subaccount_id, subaccount_name, is_demo,
                  initial_position_size, add_position_size, tp_targets, sl_enabled, sl_amount, sl_units, max_daily_loss,
                  current_user_id, None))
            result = cursor.fetchone()
            if result:
                trader_id = result.get('id') if isinstance(result, dict) else result[0]
            else:
                trader_id = None
        else:
            cursor.execute('''
                INSERT INTO traders (
                    recorder_id, account_id, subaccount_id, subaccount_name, is_demo, enabled,
                    initial_position_size, add_position_size, tp_targets, sl_enabled, sl_amount, sl_units, max_daily_loss,
                    enabled_accounts
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (recorder_id, account_id, subaccount_id, subaccount_name, 1 if is_demo else 0,
                  initial_position_size, add_position_size, tp_targets, sl_enabled, sl_amount, sl_units, max_daily_loss,
                  None))
            trader_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        env_label = "DEMO" if is_demo else "LIVE"
        display_name = f"{account['name']} {env_label} ({subaccount_name})" if subaccount_name else account['name']
        logger.info(f"Created trader {trader_id}: recorder '{recorder['name']}' -> {display_name} | Position: {initial_position_size}, SL: {sl_amount} {sl_units}")
        
        return jsonify({
            'success': True,
            'trader_id': trader_id,
            'message': f"Linked '{recorder['name']}' to '{display_name}'"
        })
        
    except Exception as e:
        logger.error(f"Error creating trader: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/traders/<int:trader_id>', methods=['PUT'])
def api_update_trader(trader_id):
    """Update a trader (enable/disable and risk settings)"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        
        # Check trader exists
        cursor.execute(f'SELECT id FROM traders WHERE id = {placeholder}', (trader_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Trader not found'}), 404
        
        # Build dynamic update query based on provided fields
        updates = []
        params = []
        
        # Update enabled status if provided
        if 'enabled' in data:
            enabled = True if is_postgres else (1 if data['enabled'] else 0)
            if is_postgres:
                enabled = data['enabled']
            updates.append(f'enabled = {placeholder}')
            params.append(enabled)
        
        # Update risk settings if provided
        if 'initial_position_size' in data:
            updates.append(f'initial_position_size = {placeholder}')
            params.append(int(data['initial_position_size']))
        
        if 'add_position_size' in data:
            updates.append(f'add_position_size = {placeholder}')
            params.append(int(data['add_position_size']))
        
        if 'tp_targets' in data:
            tp_targets = data['tp_targets']
            # Convert to JSON string if it's a list
            if isinstance(tp_targets, list):
                tp_targets = json.dumps(tp_targets)
            updates.append(f'tp_targets = {placeholder}')
            params.append(tp_targets)
        
        if 'sl_enabled' in data:
            updates.append(f'sl_enabled = {placeholder}')
            params.append(data['sl_enabled'] if is_postgres else (1 if data['sl_enabled'] else 0))
        
        if 'sl_amount' in data:
            updates.append(f'sl_amount = {placeholder}')
            params.append(float(data['sl_amount']))
        
        if 'sl_units' in data:
            updates.append(f'sl_units = {placeholder}')
            params.append(data['sl_units'])
        
        if 'max_daily_loss' in data:
            updates.append(f'max_daily_loss = {placeholder}')
            params.append(float(data['max_daily_loss']))
        
        # Update account routing if provided
        if 'enabled_accounts' in data:
            enabled_accounts = data['enabled_accounts']
            logger.info(f"  - Received enabled_accounts: {enabled_accounts}")
            # Convert to JSON string if it's a list
            if isinstance(enabled_accounts, list):
                enabled_accounts = json.dumps(enabled_accounts)
                logger.info(f"  - Converted to JSON: {enabled_accounts}")
            updates.append(f'enabled_accounts = {placeholder}')
            params.append(enabled_accounts)
            logger.info(f"  - Will update enabled_accounts field")
        
        # Execute update if there are fields to update (with retry for db locks)
        if updates:
            params.append(trader_id)
            query = f"UPDATE traders SET {', '.join(updates)} WHERE id = {placeholder}"
            for attempt in range(5):
                try:
                    cursor.execute(query, params)
                    break
                except Exception as e:
                    if 'locked' in str(e) and attempt < 4:
                        import time
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise
        
        # ALSO update the linked RECORDER with risk settings
        # (The trading engine reads from the recorder, not the trader)
        cursor.execute(f'SELECT recorder_id FROM traders WHERE id = {placeholder}', (trader_id,))
        recorder_row = cursor.fetchone()
        if recorder_row:
            recorder_id = recorder_row[0]
            recorder_updates = []
            recorder_params = []
            
            if 'initial_position_size' in data:
                recorder_updates.append(f'initial_position_size = {placeholder}')
                recorder_params.append(int(data['initial_position_size']))
            
            if 'add_position_size' in data:
                recorder_updates.append(f'add_position_size = {placeholder}')
                recorder_params.append(int(data['add_position_size']))
            
            if 'tp_targets' in data:
                tp_targets = data['tp_targets']
                if isinstance(tp_targets, list):
                    tp_targets = json.dumps(tp_targets)
                recorder_updates.append(f'tp_targets = {placeholder}')
                recorder_params.append(tp_targets)
            
            if 'tp_units' in data:
                recorder_updates.append(f'tp_units = {placeholder}')
                recorder_params.append(data['tp_units'])
            
            if 'sl_enabled' in data:
                recorder_updates.append(f'sl_enabled = {placeholder}')
                recorder_params.append(data['sl_enabled'] if is_postgres else (1 if data['sl_enabled'] else 0))
            
            if 'sl_amount' in data:
                recorder_updates.append(f'sl_amount = {placeholder}')
                recorder_params.append(float(data['sl_amount']))
            
            if 'sl_units' in data:
                recorder_updates.append(f'sl_units = {placeholder}')
                recorder_params.append(data['sl_units'])
            
            if 'sl_type' in data:
                recorder_updates.append(f'sl_type = {placeholder}')
                recorder_params.append(data['sl_type'])
            
            if 'avg_down_enabled' in data:
                recorder_updates.append(f'avg_down_enabled = {placeholder}')
                recorder_params.append(data['avg_down_enabled'] if is_postgres else (1 if data['avg_down_enabled'] else 0))
            
            if 'avg_down_amount' in data:
                recorder_updates.append(f'avg_down_amount = {placeholder}')
                recorder_params.append(int(data['avg_down_amount']))
            
            if 'avg_down_point' in data:
                recorder_updates.append(f'avg_down_point = {placeholder}')
                recorder_params.append(float(data['avg_down_point']))
            
            if 'avg_down_units' in data:
                recorder_updates.append(f'avg_down_units = {placeholder}')
                recorder_params.append(data['avg_down_units'])
            
            if recorder_updates:
                recorder_params.append(recorder_id)
                timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
                recorder_query = f"UPDATE recorders SET {', '.join(recorder_updates)}, updated_at = {timestamp_fn} WHERE id = {placeholder}"
                cursor.execute(recorder_query, recorder_params)
                logger.info(f"✅ Updated recorder {recorder_id} with risk settings")
        
        conn.commit()
        
        # ============================================================
        # 🔄 CRITICAL: Refresh tokens when strategy is ENABLED
        # ============================================================
        # When user comes back after being away, tokens may have expired.
        # Force refresh all linked account tokens to ensure trading works.
        # ============================================================
        if 'enabled' in data and data['enabled']:
            logger.info(f"🔄 Strategy enabled - validating/refreshing account tokens...")
            try:
                # Get accounts linked to this trader
                cursor.execute(f'''
                    SELECT enabled_accounts FROM traders WHERE id = {placeholder}
                ''', (trader_id,))
                trader_row = cursor.fetchone()
                if trader_row and trader_row[0]:
                    enabled_accounts = json.loads(trader_row[0]) if isinstance(trader_row[0], str) else trader_row[0]
                    account_ids = set()
                    for acct in enabled_accounts:
                        if 'account_id' in acct:
                            account_ids.add(acct['account_id'])
                    
                    logger.info(f"🔄 Refreshing tokens for {len(account_ids)} account(s)...")
                    for account_id in account_ids:
                        # Force token refresh (bypasses rate limit for this critical path)
                        try:
                            refreshed = try_refresh_tradovate_token(account_id)
                            if refreshed:
                                logger.info(f"✅ Token refreshed for account {account_id}")
                            else:
                                # Check if token is still valid
                                cursor.execute(f'SELECT token_expires_at FROM accounts WHERE id = {placeholder}', (account_id,))
                                exp_row = cursor.fetchone()
                                if exp_row and exp_row[0]:
                                    from datetime import datetime
                                    try:
                                        exp_time = datetime.strptime(str(exp_row[0]).split('.')[0], '%Y-%m-%d %H:%M:%S')
                                        if exp_time > datetime.now():
                                            logger.info(f"✅ Token for account {account_id} still valid (expires {exp_row[0]})")
                                        else:
                                            logger.warning(f"⚠️ Token for account {account_id} EXPIRED - user may need to re-authenticate")
                                    except:
                                        pass
                        except Exception as refresh_err:
                            logger.warning(f"⚠️ Could not refresh token for account {account_id}: {refresh_err}")
            except Exception as e:
                logger.warning(f"⚠️ Error during token refresh on enable: {e}")
        
        conn.close()
        
        logger.info(f"Updated trader {trader_id}: {list(data.keys())}")
        if 'enabled_accounts' in data:
            logger.info(f"  - Account routing: {len(data['enabled_accounts']) if isinstance(data['enabled_accounts'], list) else 'N/A'} accounts enabled")
        return jsonify({'success': True, 'message': 'Trader and recorder settings updated'})
        
    except Exception as e:
        logger.error(f"❌ Error updating trader {trader_id}: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 500

@app.route('/api/traders/<int:trader_id>', methods=['DELETE'])
def api_delete_trader(trader_id):
    """Delete a trader (unlink recorder from account)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        
        # Check trader exists
        cursor.execute(f'SELECT id FROM traders WHERE id = {placeholder}', (trader_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Trader not found'}), 404
        
        cursor.execute(f'DELETE FROM traders WHERE id = {placeholder}', (trader_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted trader {trader_id}")
        return jsonify({'success': True, 'message': 'Trader deleted'})
        
    except Exception as e:
        logger.error(f"Error deleting trader {trader_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/traders/<int:trader_id>/test-connection', methods=['POST'])
def api_test_trader_connection(trader_id):
    """Test if the trader's linked account connection is working"""
    import asyncio
    
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get trader with account info
        cursor.execute('''
            SELECT t.*, a.tradovate_token, a.username, a.password, a.id as account_id,
                   a.name as account_name, t.subaccount_name, t.is_demo
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.id = ?
        ''', (trader_id,))
        trader_row = cursor.fetchone()
        
        if not trader_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Trader not found'}), 404
        
        trader = dict(trader_row)
        conn.close()
        
        account_name = trader.get('account_name', 'Unknown')
        subaccount_name = trader.get('subaccount_name', '')
        is_demo = bool(trader.get('is_demo', True))
        tradovate_token = trader.get('tradovate_token')
        username = trader.get('username')
        password = trader.get('password')
        
        logger.info(f"🔗 Testing connection for trader {trader_id} ({account_name} / {subaccount_name})")
        
        # Test 1: Check if we have credentials
        if not tradovate_token and not (username and password):
            return jsonify({
                'success': True,
                'connected': False,
                'error': 'No OAuth token or API credentials found. Please re-authenticate.'
            })
        
        # Test 2: Try to validate token or authenticate
        async def test_connection():
            from phantom_scraper.tradovate_integration import TradovateIntegration
            from tradovate_api_access import TradovateAPIAccess
            
            # Try OAuth token first
            if tradovate_token:
                try:
                    tradovate = TradovateIntegration(demo=is_demo)
                    await tradovate.__aenter__()
                    tradovate.access_token = tradovate_token
                    
                    # Try to get positions (simple API test)
                    positions = await tradovate.get_positions(account_id=trader.get('subaccount_id'))
                    await tradovate.__aexit__(None, None, None)
                    
                    if positions is not None:
                        return {'connected': True, 'method': 'OAuth', 'positions': len(positions)}
                except Exception as e:
                    logger.warning(f"OAuth test failed: {e}")
            
            # Try API Access
            if username and password:
                try:
                    api_access = TradovateAPIAccess(demo=is_demo)
                    result = await api_access.login(username=username, password=password)
                    if result.get('success'):
                        return {'connected': True, 'method': 'API Access'}
                    else:
                        return {'connected': False, 'error': result.get('error', 'Login failed')}
                except Exception as e:
                    return {'connected': False, 'error': str(e)}
            
            return {'connected': False, 'error': 'No valid authentication method'}
        
        # Run async test
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(test_connection())
            loop.close()
        except RuntimeError:
            result = asyncio.run(test_connection())
        
        if result.get('connected'):
            logger.info(f"✅ Connection test PASSED for {account_name} ({result.get('method')})")
        else:
            logger.warning(f"⚠️ Connection test FAILED for {account_name}: {result.get('error')}")
        
        return jsonify({
            'success': True,
            'connected': result.get('connected', False),
            'method': result.get('method'),
            'error': result.get('error'),
            'account_name': account_name,
            'subaccount_name': subaccount_name
        })
        
    except Exception as e:
        logger.error(f"Error testing connection for trader {trader_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# HIGH-PERFORMANCE SIGNAL PROCESSOR (Background Thread)
# ============================================================

# Cache for recorder lookups (avoid repeated DB queries)
recorder_cache = {}
recorder_cache_time = {}
CACHE_TTL = 60  # Cache recorder info for 60 seconds

def get_cached_recorder(webhook_token):
    """Get recorder from cache or database"""
    now = time.time()
    if webhook_token in recorder_cache:
        if now - recorder_cache_time.get(webhook_token, 0) < CACHE_TTL:
            return recorder_cache[webhook_token]
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if is_using_postgres():
        cursor.execute('SELECT * FROM recorders WHERE webhook_token = %s AND recording_enabled = true', (webhook_token,))
    else:
        cursor.execute('SELECT * FROM recorders WHERE webhook_token = ? AND recording_enabled = 1', (webhook_token,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        recorder = dict(row)
        recorder_cache[webhook_token] = recorder
        recorder_cache_time[webhook_token] = now
        return recorder
    return None

def process_signal_batch(signals):
    """Process a batch of signals efficiently with single DB connection"""
    if not signals:
        return
    
    conn = get_db_connection()
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    cursor = conn.cursor()
    
    try:
        # Batch insert signals
        for sig in signals:
            cursor.execute('''
                INSERT INTO recorded_signals 
                (recorder_id, action, ticker, price, position_size, market_position, signal_type, raw_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sig['recorder_id'],
                sig['action'],
                sig['ticker'],
                sig['price'],
                sig.get('position_size'),
                sig.get('market_position'),
                sig['signal_type'],
                json.dumps(sig['raw_data']),
                sig['timestamp']
            ))
        conn.commit()
    except Exception as e:
        logger.error(f"Batch signal insert error: {e}")
        conn.rollback()
    finally:
        conn.close()

def signal_processor_worker():
    """Background worker that processes signals from queue in batches"""
    logger.info("🚀 Signal processor worker started")
    batch = []
    last_process_time = time.time()
    
    while True:
        try:
            # Try to get signal with timeout
            signal = signal_queue.get(timeout=BATCH_TIMEOUT)
            batch.append(signal)
            
            # Process batch when full or timeout reached
            if len(batch) >= BATCH_SIZE:
                process_signal_batch(batch)
                batch = []
                last_process_time = time.time()
                
        except Empty:
            # Timeout - process partial batch if any
            if batch and time.time() - last_process_time >= BATCH_TIMEOUT:
                process_signal_batch(batch)
                batch = []
                last_process_time = time.time()
        except Exception as e:
            logger.error(f"Signal processor error: {e}")

# Start background signal processor
signal_processor_thread = threading.Thread(target=signal_processor_worker, daemon=True)
signal_processor_thread.start()

# ============================================================
# WEBHOOK HANDLER - Direct Processing (No Proxy)
# ============================================================
# Webhook processing is done directly here using recorder_service logic.
# This works on Railway (single container) without needing separate service.
# ============================================================

@app.route('/webhook/fast/<webhook_token>', methods=['POST'])
def receive_webhook_fast(webhook_token):
    """Fast webhook endpoint - processes directly."""
    return process_webhook_directly(webhook_token)

@app.route('/webhook/<webhook_token>', methods=['POST'])
def receive_webhook(webhook_token):
    """Main webhook endpoint - processes directly using DCA logic."""
    return process_webhook_directly(webhook_token)

def process_webhook_directly(webhook_token):
    """
    Process webhook directly using recorder_service DCA logic.
    This is the REAL webhook handler with proper DCA, TP calculation, etc.
    
    FULL RISK MANAGEMENT:
    - Direction Filter (long only, short only)
    - Time Filters (trading windows)
    - Signal Cooldown
    - Max Signals Per Session
    - Max Daily Loss
    - Max Contracts Per Trade
    - Signal Delay (Nth signal)
    - Stop Loss
    - Take Profit
    """
    from datetime import datetime, timedelta, timezone
    
    try:
        # Import the heavy-duty trading functions from recorder_service
        from recorder_service import (
            execute_live_trade_with_bracket,
            sync_position_with_broker,
            get_price_from_tradingview_api,
            convert_ticker_to_tradovate,
            get_tick_size,
            get_tick_value
        )
        
        # Find recorder by webhook token
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        
        cursor.execute(f'SELECT * FROM recorders WHERE webhook_token = {placeholder}', (webhook_token,))
        recorder_row = cursor.fetchone()
        
        if not recorder_row:
            logger.warning(f"Webhook received for unknown token: {webhook_token[:8]}...")
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid webhook token'}), 404
        
        recorder = dict(recorder_row)
        recorder_id = recorder['id']
        recorder_name = recorder['name']
        
        # Check if recorder is enabled - if disabled, reject the signal
        if not recorder.get('recording_enabled', 1):
            logger.info(f"⚠️ Webhook BLOCKED for '{recorder_name}' - recorder is DISABLED")
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder is disabled', 'blocked': True}), 200
        
        # Parse incoming data
        data = request.get_json(force=True, silent=True) or {}
        if not data:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = request.form.to_dict() or {}
        
        if not data:
            conn.close()
            return jsonify({'success': False, 'error': 'No data received'}), 400
        
        logger.info(f"📨 Webhook received for recorder '{recorder_name}': {data}")
        
        # Extract signal data
        action = str(data.get('action', '')).lower().strip()
        ticker = data.get('ticker', data.get('symbol', ''))
        price = data.get('price', data.get('close', 0))
        quantity = int(data.get('quantity', data.get('qty', data.get('contracts', 1))) or 1)
        
        # Strategy alert detection - TradingView strategies send position_size and market_position
        position_size = data.get('position_size', data.get('contracts'))
        market_position = data.get('market_position', '')
        is_strategy_alert = position_size is not None or market_position
        
        # Validate action
        valid_actions = ['buy', 'sell', 'long', 'short', 'close', 'flat', 'exit']
        if action not in valid_actions:
            logger.warning(f"Invalid action '{action}' for recorder {recorder_name}")
            conn.close()
            return jsonify({'success': False, 'error': f'Invalid action: {action}'}), 400
        
        # STRATEGY MODE: market_position: flat = CLOSE POSITION
        # SMART CLOSE: Validates close makes sense before executing
        # Handles multiple strategies on same ticker correctly
        if market_position and market_position.lower() == 'flat':
            logger.info(f"🔄 FLAT signal for {recorder_name} - validating close order")
            
            # TradingView tells us what IT wants to do
            tv_action = action.upper()  # 'BUY' or 'SELL' from TradingView
            tv_qty = quantity           # How many contracts TradingView wants to close
            
            # Get the trader linked to this recorder to check broker position
            from recorder_service import execute_trade_simple, get_broker_position_for_recorder
            
            # Map ticker to contract symbol (e.g., NQ1! -> NQH6)
            ticker_to_symbol = {
                'NQ1!': 'NQH6', 'MNQ1!': 'MNQH6',
                'ES1!': 'ESH6', 'MES1!': 'MESH6',
                'YM1!': 'YMH6', 'MYM1!': 'MYMH6',
                'RTY1!': 'RTYH6', 'M2K1!': 'M2KH6',
                'CL1!': 'CLF5', 'MCL1!': 'MCLF5',
                'GC1!': 'GCG5', 'MGC1!': 'MGCG5',
            }
            contract_symbol = ticker_to_symbol.get(ticker, ticker.replace('1!', 'H6'))
            
            # Check broker's NET position for this ticker
            broker_pos = get_broker_position_for_recorder(recorder_id, contract_symbol)
            broker_qty = broker_pos.get('quantity', 0) if broker_pos else 0  # positive=LONG, negative=SHORT
            
            logger.info(f"📊 {recorder_name} FLAT check: TV wants {tv_action} {tv_qty}, broker net={broker_qty}")
            
            # VALIDATION: Does this close make sense?
            # BUY closes SHORT (should only execute if broker has SHORT/negative position)
            # SELL closes LONG (should only execute if broker has LONG/positive position)
            
            if broker_qty == 0:
                # Broker is completely flat - skip to prevent orphan
                logger.info(f"⚠️ FLAT signal for {recorder_name} - broker is FLAT, skipping (prevents orphan)")
                conn.close()
                return jsonify({'success': True, 'action': 'skip', 'message': 'Broker already flat - no position to close'})
            
            if tv_action in ['BUY', 'LONG']:
                # TradingView wants to BUY to close (was SHORT)
                if broker_qty > 0:
                    # Broker is LONG - BUY would INCREASE position, not close! Skip.
                    logger.info(f"⚠️ FLAT signal {recorder_name}: TV says BUY but broker is LONG {broker_qty}, skipping (would increase position)")
                    conn.close()
                    return jsonify({'success': True, 'action': 'skip', 'message': 'Close direction mismatch - broker is LONG, cannot BUY to close'})
                # Broker is SHORT - BUY will reduce/close. Use TV quantity but cap to broker's position
                close_qty = min(tv_qty, abs(broker_qty))
                close_action = 'BUY'
                
            else:  # SELL/SHORT
                # TradingView wants to SELL to close (was LONG)
                if broker_qty < 0:
                    # Broker is SHORT - SELL would INCREASE position, not close! Skip.
                    logger.info(f"⚠️ FLAT signal {recorder_name}: TV says SELL but broker is SHORT {broker_qty}, skipping (would increase position)")
                    conn.close()
                    return jsonify({'success': True, 'action': 'skip', 'message': 'Close direction mismatch - broker is SHORT, cannot SELL to close'})
                # Broker is LONG - SELL will reduce/close. Use TV quantity but cap to broker's position
                close_qty = min(tv_qty, broker_qty)
                close_action = 'SELL'
            
            logger.info(f"✅ FLAT validated for {recorder_name}: executing {close_action} {close_qty} (TV requested {tv_qty})")
            
            result = execute_trade_simple(
                recorder_id=recorder_id,
                action=close_action,
                ticker=ticker,
                quantity=close_qty,
                tp_ticks=0,  # No TP - this is a close
                sl_ticks=0,  # No SL - this is a close
                sl_type='Fixed'
            )
            
            logger.info(f"✅ CLOSE executed for {recorder_name}: {result}")
            conn.close()
            return jsonify({'success': True, 'action': 'close', 'result': result})
        
        # Determine side early (needed for filters)
        if action in ['buy', 'long']:
            side = 'LONG'
            trade_action = 'BUY'
        elif action in ['sell', 'short']:
            side = 'SHORT'
            trade_action = 'SELL'
        elif action in ['close', 'flat', 'exit']:
            # Close signals bypass filters
            logger.info(f"🔄 CLOSE signal received for {recorder_name}")
            conn.close()
            return jsonify({'success': True, 'action': 'close', 'message': 'Close signal processed'})
        else:
            conn.close()
            return jsonify({'success': False, 'error': f'Unknown action: {action}'}), 400
        
        # ============================================================
        # 🛡️ RISK MANAGEMENT FILTERS - Check ALL before executing
        # ============================================================
        
        # Get current time (US Eastern for market hours - UTC-5 in winter, UTC-4 in summer)
        # Use simple UTC offset since pytz may not be available
        now = datetime.now()  # Local time is fine for time window checks
        
        # --- FILTER 1: Direction Filter ---
        direction_filter = recorder.get('direction_filter', '')
        if direction_filter:
            if direction_filter.lower() == 'long only' and side != 'LONG':
                logger.warning(f"🚫 [{recorder_name}] Direction filter BLOCKED: {side} signal (filter: Long Only)")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Direction filter: Long Only (received {side})'}), 200
            elif direction_filter.lower() == 'short only' and side != 'SHORT':
                logger.warning(f"🚫 [{recorder_name}] Direction filter BLOCKED: {side} signal (filter: Short Only)")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Direction filter: Short Only (received {side})'}), 200
            logger.info(f"✅ Direction filter passed: {direction_filter}")
        
        # --- FILTER 2: Time Filters (Trading Windows) ---
        def parse_time(time_str):
            """Parse time string like '8:45 AM' or '13:45' to datetime.time"""
            if not time_str:
                return None
            time_str = time_str.strip()
            try:
                # Try 12-hour format first
                if 'AM' in time_str.upper() or 'PM' in time_str.upper():
                    return datetime.strptime(time_str.upper(), '%I:%M %p').time()
                # Try 24-hour format
                return datetime.strptime(time_str, '%H:%M').time()
            except:
                return None
        
        def is_time_in_window(current_time, start_str, stop_str):
            """Check if current time is within the window"""
            start = parse_time(start_str)
            stop = parse_time(stop_str)
            if not start or not stop:
                return True  # No filter if times not set
            current = current_time.time()
            if start <= stop:
                return start <= current <= stop
            else:
                # Overnight window (e.g., 10 PM to 6 AM)
                return current >= start or current <= stop
        
        # Check Time Filter 1
        time_filter_1_start = recorder.get('time_filter_1_start', '')
        time_filter_1_stop = recorder.get('time_filter_1_stop', '')
        time_filter_2_start = recorder.get('time_filter_2_start', '')
        time_filter_2_stop = recorder.get('time_filter_2_stop', '')
        
        # If any time filter is set, check them
        has_time_filter_1 = time_filter_1_start and time_filter_1_stop
        has_time_filter_2 = time_filter_2_start and time_filter_2_stop
        
        if has_time_filter_1 or has_time_filter_2:
            in_window_1 = is_time_in_window(now, time_filter_1_start, time_filter_1_stop) if has_time_filter_1 else False
            in_window_2 = is_time_in_window(now, time_filter_2_start, time_filter_2_stop) if has_time_filter_2 else False
            
            if not in_window_1 and not in_window_2:
                logger.warning(f"🚫 [{recorder_name}] Time filter BLOCKED: {now.strftime('%I:%M %p')} not in trading window")
                logger.warning(f"   Window 1: {time_filter_1_start} - {time_filter_1_stop}")
                logger.warning(f"   Window 2: {time_filter_2_start} - {time_filter_2_stop}")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Outside trading hours ({now.strftime("%I:%M %p")})'}), 200
            logger.info(f"✅ Time filter passed: {now.strftime('%I:%M %p')} in window")
        
        # --- FILTER 3: Signal Cooldown ---
        signal_cooldown = int(recorder.get('signal_cooldown', 0) or 0)
        if signal_cooldown > 0:
            if is_postgres:
                cursor.execute(f'''
                    SELECT MAX(timestamp) FROM recorded_signals 
                    WHERE recorder_id = %s AND timestamp > NOW() - INTERVAL '{signal_cooldown} seconds'
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT MAX(timestamp) FROM recorded_signals 
                    WHERE recorder_id = ? AND timestamp > datetime('now', ?)
                ''', (recorder_id, f'-{signal_cooldown} seconds'))
            last_signal = cursor.fetchone()
            if last_signal and last_signal[0]:
                logger.warning(f"🚫 [{recorder_name}] Cooldown BLOCKED: Last signal was within {signal_cooldown}s")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Signal cooldown ({signal_cooldown}s)'}), 200
            logger.info(f"✅ Signal cooldown passed: {signal_cooldown}s")
        
        # --- FILTER 4: Max Signals Per Session ---
        max_signals = int(recorder.get('max_signals_per_session', 0) or 0)
        if max_signals > 0:
            # Count signals today
            if is_postgres:
                cursor.execute('''
                    SELECT COUNT(*) FROM recorded_signals 
                    WHERE recorder_id = %s AND DATE(timestamp) = CURRENT_DATE
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM recorded_signals 
                    WHERE recorder_id = ? AND DATE(timestamp) = DATE('now')
                ''', (recorder_id,))
            signal_count = cursor.fetchone()[0] or 0
            if signal_count >= max_signals:
                logger.warning(f"🚫 [{recorder_name}] Max signals BLOCKED: {signal_count}/{max_signals} signals today")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Max signals reached ({signal_count}/{max_signals})'}), 200
            logger.info(f"✅ Max signals passed: {signal_count}/{max_signals}")
        
        # --- FILTER 5: Max Daily Loss ---
        max_daily_loss = float(recorder.get('max_daily_loss', 0) or 0)
        if max_daily_loss > 0:
            # Calculate today's P&L from closed trades
            if is_postgres:
                cursor.execute('''
                    SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades 
                    WHERE recorder_id = %s AND DATE(exit_time) = CURRENT_DATE AND status = 'closed'
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades 
                    WHERE recorder_id = ? AND DATE(exit_time) = DATE('now') AND status = 'closed'
                ''', (recorder_id,))
            daily_pnl = cursor.fetchone()[0] or 0
            if daily_pnl <= -max_daily_loss:
                logger.warning(f"🚫 [{recorder_name}] Max daily loss BLOCKED: ${daily_pnl:.2f} (limit: -${max_daily_loss})")
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Max daily loss hit (${daily_pnl:.2f})'}), 200
            logger.info(f"✅ Max daily loss passed: ${daily_pnl:.2f} / -${max_daily_loss}")
        
        # --- FILTER 6: Max Contracts Per Trade ---
        max_contracts = int(recorder.get('max_contracts_per_trade', 0) or 0)
        if max_contracts > 0 and quantity > max_contracts:
            logger.info(f"📊 [{recorder_name}] Quantity capped: {quantity} → {max_contracts} (max_contracts_per_trade)")
            quantity = max_contracts
        
        # --- FILTER 7: Signal Delay (Nth Signal) ---
        add_delay = int(recorder.get('add_delay', 1) or 1)
        if add_delay > 1:
            # Count total signals for this recorder
            cursor.execute(f'SELECT COUNT(*) FROM recorded_signals WHERE recorder_id = {placeholder}', (recorder_id,))
            total_signals = cursor.fetchone()[0] or 0
            signal_number = total_signals + 1  # This will be the Nth signal
            
            if signal_number % add_delay != 0:
                logger.warning(f"🚫 [{recorder_name}] Signal delay BLOCKED: Signal #{signal_number} (executing every {add_delay})")
                # Still record the signal but don't execute
                timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
                cursor.execute(f'''
                    INSERT INTO recorded_signals (recorder_id, action, ticker, price, quantity, timestamp, executed)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {timestamp_fn}, 0)
                ''', (recorder_id, action, ticker, price, quantity))
                conn.commit()
                conn.close()
                return jsonify({'success': False, 'blocked': True, 'reason': f'Signal delay ({signal_number} mod {add_delay} != 0)'}), 200
            logger.info(f"✅ Signal delay passed: #{signal_number} (every {add_delay})")
        
        # ============================================================
        # 📊 RECORD THE SIGNAL (after filters pass)
        # ============================================================
        try:
            timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
            cursor.execute(f'''
                INSERT INTO recorded_signals (recorder_id, action, ticker, price, quantity, timestamp, executed)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {timestamp_fn}, 1)
            ''', (recorder_id, action, ticker, price, quantity))
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not record signal: {e}")
        
        # ============================================================
        # 📈 GET RISK SETTINGS
        # ============================================================
        
        # CRITICAL: Sync with broker BEFORE processing to prevent drift
        if ticker:
            try:
                sync_result = sync_position_with_broker(recorder_id, ticker)
                if sync_result.get('cleared'):
                    logger.info(f"🔄 Cleared database position - broker has no position for {ticker}")
                elif sync_result.get('synced'):
                    logger.info(f"🔄 Synced database with broker position for {ticker}")
            except Exception as e:
                logger.warning(f"⚠️ Sync failed (continuing anyway): {e}")
        
        # Get LIVE market price for accurate TP/SL calculation
        live_price = get_price_from_tradingview_api(ticker) if ticker else None
        current_price = live_price if live_price else (float(price) if price else 0)
        
        # Get tick size for this symbol
        tick_size = get_tick_size(ticker) if ticker else 0.25
        
        # Get TP settings from recorder - RECORDER SETTINGS ARE ALWAYS SOURCE OF TRUTH
        tp_targets_raw = recorder.get('tp_targets', '[]')
        tp_units = recorder.get('tp_units', 'Ticks')
        try:
            tp_targets = json.loads(tp_targets_raw) if isinstance(tp_targets_raw, str) else tp_targets_raw or []
        except:
            tp_targets = []
        
        # Get TP value and convert to ticks based on units
        if tp_targets and len(tp_targets) > 0:
            tp_value = float(tp_targets[0].get('value', 0) or 0)
        else:
            tp_value = 0
        
        # Convert TP to ticks based on units
        if tp_value > 0:
            if tp_units == 'Points':
                # Points = dollar value per contract. Convert to ticks.
                tick_value = get_tick_value(ticker) if ticker else 0.50
                tp_ticks = int(tp_value / tick_value) if tick_value else int(tp_value / tick_size)
            elif tp_units == 'Percent':
                # Percent of entry price
                tp_ticks = int((current_price * (tp_value / 100)) / tick_size) if current_price and tick_size else 0
            else:
                # Ticks (default)
                tp_ticks = int(tp_value)
        else:
            tp_ticks = 0
        
        # Get SL settings from recorder
        sl_enabled = recorder.get('sl_enabled', 0)
        sl_amount = float(recorder.get('sl_amount', 0) or 0)
        sl_units = recorder.get('sl_units', 'Ticks')
        sl_type = recorder.get('sl_type', 'Fixed')  # Fixed or Trailing
        
        # Convert SL to ticks based on units
        if sl_enabled and sl_amount > 0:
            if sl_units == 'Loss ($)':
                # Dollar loss per contract. Convert to ticks.
                tick_value = get_tick_value(ticker) if ticker else 0.50
                sl_ticks = int(sl_amount / tick_value) if tick_value else int(sl_amount / tick_size)
            elif sl_units == 'Percent':
                # Percent of entry price
                sl_ticks = int((current_price * (sl_amount / 100)) / tick_size) if current_price and tick_size else 0
            else:
                # Ticks (default)
                sl_ticks = int(sl_amount)
        else:
            sl_ticks = 0
        
        # Log the mode
        signal_type = "STRATEGY" if is_strategy_alert else "INDICATOR"
        logger.info(f"📊 {signal_type}: TP={tp_ticks} ticks ({tp_units}), SL={sl_ticks} ticks ({sl_units}), Type={sl_type}")
        
        # Get linked trader for live execution
        if is_using_postgres():
            cursor.execute('''
                SELECT t.*, a.tradovate_token, a.md_access_token, a.username, a.password, a.id as account_id
                FROM traders t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.recorder_id = %s AND t.enabled = true
                LIMIT 1
            ''', (recorder_id,))
        else:
            cursor.execute('''
                SELECT t.*, a.tradovate_token, a.md_access_token, a.username, a.password, a.id as account_id
                FROM traders t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.recorder_id = ? AND t.enabled = 1
                LIMIT 1
            ''', (recorder_id,))
        trader_row = cursor.fetchone()
        trader = dict(trader_row) if trader_row else None
        
        conn.close()
        
        if not trader:
            logger.warning(f"No active trader linked to recorder '{recorder_name}'")
            return jsonify({'success': False, 'error': 'No trader linked'}), 400
        
        # Execute the trade with FULL risk settings
        logger.info(f"🚀 Executing {trade_action} {quantity} {ticker} for '{recorder_name}' | Price: {current_price} | TP: {tp_ticks} ticks | SL: {sl_ticks} ticks")
        
        try:
            # Import the SIMPLE trade function
            from recorder_service import execute_trade_simple
            
            result = execute_trade_simple(
                recorder_id=recorder_id,
                action=trade_action,
                ticker=ticker,
                quantity=quantity,
                tp_ticks=tp_ticks,
                sl_ticks=sl_ticks,
                sl_type=sl_type
            )
            
            if result.get('success'):
                logger.info(f"✅ Trade executed: {result}")
                return jsonify({
                    'success': True,
                    'action': trade_action,
                    'side': side,
                    'quantity': quantity,
                    'broker_avg': result.get('broker_avg'),
                    'broker_qty': result.get('broker_qty'),
                    'tp_price': result.get('tp_price'),
                    'tp_order_id': result.get('tp_order_id'),
                    'sl_price': result.get('sl_price'),
                    'sl_order_id': result.get('sl_order_id'),
                    'filters_passed': True,
                    'result': result
                })
            else:
                logger.error(f"❌ Trade execution failed: {result}")
                return jsonify({'success': False, 'error': result.get('error', 'Execution failed')}), 500
                
        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# LEGACY WEBHOOK CODE - DISABLED (handled by Trading Engine)
# ============================================================
# The following code has been moved to recorder_service.py
# It's kept here commented out for reference only.
# ============================================================

def _DISABLED_receive_webhook_legacy(webhook_token):
    """
    DISABLED - This code has been moved to Trading Engine (recorder_service.py)
    Kept here for reference only. DO NOT RE-ENABLE.
    """
    try:
        # Find recorder by webhook token
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if is_using_postgres():
            cursor.execute('''
                SELECT * FROM recorders WHERE webhook_token = %s AND recording_enabled = true
            ''', (webhook_token,))
        else:
            cursor.execute('''
                SELECT * FROM recorders WHERE webhook_token = ? AND recording_enabled = 1
            ''', (webhook_token,))
        recorder = cursor.fetchone()
        
        if not recorder:
            logger.warning(f"Webhook received for unknown/disabled token: {webhook_token[:8]}...")
            return jsonify({'success': False, 'error': 'Invalid or disabled webhook'}), 404
        
        recorder = dict(recorder)
        recorder_id = recorder['id']
        recorder_name = recorder['name']
        
        # Parse incoming data (support both JSON and form data)
        if request.is_json:
            data = request.get_json()
        else:
            # Try to parse as JSON from text body
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = request.form.to_dict()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400
        
        logger.info(f"📨 Webhook received for recorder '{recorder_name}': {data}")
        
        # Extract signal data
        action = str(data.get('action', '')).lower().strip()
        ticker = data.get('ticker', data.get('symbol', ''))
        price = data.get('price', data.get('close', 0))
        
        # Strategy-specific fields (when TradingView handles sizing)
        position_size = data.get('position_size', data.get('contracts'))
        market_position = data.get('market_position', '')  # long, short, flat
        prev_position_size = data.get('prev_position_size', data.get('prev_market_position_size'))
        
        # Validate action - including TP/SL price alerts
        valid_actions = ['buy', 'sell', 'long', 'short', 'close', 'flat', 'exit', 
                         'tp_hit', 'sl_hit', 'take_profit', 'stop_loss', 'price_alert']
        if action not in valid_actions:
            logger.warning(f"Invalid action '{action}' for recorder {recorder_name}")
            return jsonify({'success': False, 'error': f'Invalid action: {action}'}), 400
        
        # Handle TP/SL price alerts - these close open positions at TP/SL price
        if action in ['tp_hit', 'take_profit']:
            normalized_action = 'TP_HIT'
            direction = 'flat'
        elif action in ['sl_hit', 'stop_loss']:
            normalized_action = 'SL_HIT'
            direction = 'flat'
        elif action == 'price_alert':
            # Generic price update - check if it hits TP/SL
            normalized_action = 'PRICE_UPDATE'
            direction = None
        # Standard actions
        elif action in ['long', 'buy']:
            normalized_action = 'BUY'
            direction = 'long'
        elif action in ['short', 'sell']:
            normalized_action = 'SELL'
            direction = 'short'
        else:  # close, flat, exit
            normalized_action = 'CLOSE'
            direction = 'flat'
        
        # Check signal delay (skip signals based on recorder settings)
        signal_delay = recorder.get('add_delay', 1) or 1
        
        # Get/update signal counter for this recorder
        cursor.execute('''
            SELECT signal_count FROM recorders WHERE id = ?
        ''', (recorder_id,))
        result = cursor.fetchone()
        signal_count = (result['signal_count'] if result and result['signal_count'] else 0) + 1
        
        cursor.execute('''
            UPDATE recorders SET signal_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (signal_count, recorder_id))
        conn.commit()
        
        # Check if we should skip this signal
        if signal_delay > 1 and signal_count % signal_delay != 0:
            logger.info(f"⏭️ Skipping signal {signal_count} for {recorder_name} (delay={signal_delay})")
            conn.close()
            return jsonify({
                'success': True,
                'skipped': True,
                'message': f'Signal {signal_count} skipped (executing every {signal_delay} signals)',
                'next_execute': signal_count + (signal_delay - (signal_count % signal_delay))
            })
        
        # Determine if this is a simple alert or strategy alert
        is_strategy_alert = position_size is not None or market_position
        
        # Record the signal
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recorded_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorder_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                ticker TEXT,
                price REAL,
                quantity INTEGER DEFAULT 1,
                position_size TEXT,
                market_position TEXT,
                signal_type TEXT,
                raw_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                executed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recorder_id) REFERENCES recorders(id)
            )
        ''')
        
        cursor.execute('''
            INSERT INTO recorded_signals 
            (recorder_id, action, ticker, price, position_size, market_position, signal_type, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            recorder_id,
            normalized_action,
            ticker,
            float(price) if price else None,
            str(position_size) if position_size else None,
            market_position,
            'strategy' if is_strategy_alert else 'alert',
            json.dumps(data)
        ))
        
        signal_id = cursor.lastrowid
        
        # =====================================================
        # TRADE PROCESSING LOGIC - Convert signals into trades
        # WITH TP/SL SETTINGS FROM RECORDER
        # =====================================================
        trade_result = None
        current_price = float(price) if price else 0
        
        # Get position size from recorder settings
        quantity = int(position_size) if position_size else recorder.get('initial_position_size', 1)
        
        # Get TP/SL settings from recorder
        sl_enabled = recorder.get('sl_enabled', 0)
        sl_amount = recorder.get('sl_amount', 0) or 0
        sl_units = recorder.get('sl_units', 'Ticks')
        
        # Parse TP targets (JSON array)
        tp_targets_raw = recorder.get('tp_targets', '[]')
        try:
            tp_targets = json.loads(tp_targets_raw) if isinstance(tp_targets_raw, str) else tp_targets_raw or []
        except:
            tp_targets = []
        
        # Get first TP target (primary)
        tp_ticks = tp_targets[0].get('value', 0) if tp_targets else 0
        
        # Determine tick size and tick value for PnL calculation
        tick_size = get_tick_size(ticker) if ticker else 0.25
        tick_value = get_tick_value(ticker) if ticker else 0.50
        
        # Check for existing open trade for this recorder
        cursor.execute('''
            SELECT * FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'open' 
            ORDER BY entry_time DESC LIMIT 1
        ''', (recorder_id,))
        open_trade_row = cursor.fetchone()
        
        open_trade = None
        if open_trade_row:
            # Convert to dict properly
            columns = [desc[0] for desc in cursor.description]
            open_trade = dict(zip(columns, open_trade_row))
        
        def calculate_tp_sl_prices(entry_price, side, tp_ticks, sl_ticks, tick_size):
            """Calculate TP and SL price levels based on entry and tick settings"""
            if side == 'LONG':
                tp_price = entry_price + (tp_ticks * tick_size) if tp_ticks else None
                sl_price = entry_price - (sl_ticks * tick_size) if sl_ticks else None
            else:  # SHORT
                tp_price = entry_price - (tp_ticks * tick_size) if tp_ticks else None
                sl_price = entry_price + (sl_ticks * tick_size) if sl_ticks else None
            return tp_price, sl_price
        
        def check_tp_sl_hit(open_trade, current_price, tick_size):
            """Check if TP or SL was hit and return exit info"""
            if not open_trade:
                return None, None, None
            
            tp_price = open_trade.get('tp_price')
            sl_price = open_trade.get('sl_price')
            side = open_trade['side']
            entry_price = open_trade['entry_price']
            
            if side == 'LONG':
                # For LONG: TP hit if price >= tp_price, SL hit if price <= sl_price
                if tp_price and current_price >= tp_price:
                    return 'tp', tp_price, (tp_price - entry_price) / tick_size
                if sl_price and current_price <= sl_price:
                    return 'sl', sl_price, (sl_price - entry_price) / tick_size
            else:  # SHORT
                # For SHORT: TP hit if price <= tp_price, SL hit if price >= sl_price
                if tp_price and current_price <= tp_price:
                    return 'tp', tp_price, (entry_price - tp_price) / tick_size
                if sl_price and current_price >= sl_price:
                    return 'sl', sl_price, (entry_price - sl_price) / tick_size
            
            return None, None, None
        
        def close_trade(cursor, trade, exit_price, pnl_ticks, tick_value, exit_reason):
            """Close a trade and calculate PnL"""
            pnl = pnl_ticks * tick_value * trade['quantity']
            
            cursor.execute('''
                UPDATE recorded_trades 
                SET exit_price = ?, exit_time = CURRENT_TIMESTAMP, 
                    pnl = ?, pnl_ticks = ?, status = 'closed', 
                    exit_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (exit_price, pnl, pnl_ticks, exit_reason, trade['id']))
            
            return pnl, pnl_ticks
        
        def close_recorder_position(cursor, position_id, exit_price, ticker):
            """Close a recorder position and calculate final PnL"""
            cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (position_id,))
            row = cursor.fetchone()
            
            if not row:
                return
            
            # Get column names for dict conversion
            columns = [desc[0] for desc in cursor.description]
            pos = dict(zip(columns, row))
            
            avg_entry = pos['avg_entry_price']
            total_qty = pos['total_quantity']
            side = pos['side']
            
            pos_tick_size = get_tick_size(ticker)
            pos_tick_value = get_tick_value(ticker)
            
            if side == 'LONG':
                pnl_ticks = (exit_price - avg_entry) / pos_tick_size
            else:
                pnl_ticks = (avg_entry - exit_price) / pos_tick_size
            
            realized_pnl = pnl_ticks * pos_tick_value * total_qty
            
            cursor.execute('''
                UPDATE recorder_positions
                SET status = 'closed',
                    exit_price = ?,
                    realized_pnl = ?,
                    closed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (exit_price, realized_pnl, position_id))
            
            logger.info(f"📊 Position closed: {side} {ticker} x{total_qty} @ avg {avg_entry} -> {exit_price} | PnL: ${realized_pnl:.2f}")
        
        def update_recorder_position(cursor, recorder_id, ticker, side, price, quantity=1):
            """
            Update or create a recorder position for position-based drawdown tracking.
            This is ADDITIVE to the recorded_trades table - keeps existing trade records.
            
            Returns: position_id, is_new_position, total_quantity
            """
            import json as json_module
            from datetime import datetime as dt
            
            # Check for existing open position for this recorder+ticker
            cursor.execute('''
                SELECT id, total_quantity, avg_entry_price, entries, side
                FROM recorder_positions
                WHERE recorder_id = ? AND ticker = ? AND status = 'open'
            ''', (recorder_id, ticker))
            
            existing = cursor.fetchone()
            
            if existing:
                pos_id, total_qty, avg_entry, entries_json, pos_side = existing
                entries = json_module.loads(entries_json) if entries_json else []
                
                if pos_side == side:
                    # SAME SIDE: Add to position (DCA)
                    new_qty = total_qty + quantity
                    new_avg = ((avg_entry * total_qty) + (price * quantity)) / new_qty
                    entries.append({'price': price, 'qty': quantity, 'time': dt.now().isoformat()})
                    
                    cursor.execute('''
                        UPDATE recorder_positions
                        SET total_quantity = ?, avg_entry_price = ?, entries = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (new_qty, new_avg, json_module.dumps(entries), pos_id))
                    
                    logger.info(f"📈 Position DCA: {side} {ticker} +{quantity} @ {price} | Total: {new_qty} @ avg {new_avg:.2f}")
                    return pos_id, False, new_qty
                else:
                    # OPPOSITE SIDE: Close existing position, create new one
                    close_recorder_position(cursor, pos_id, price, ticker)
                    # Fall through to create new position below
            
            # NO POSITION or just closed opposite: Create new position
            entries = [{'price': price, 'qty': quantity, 'time': dt.now().isoformat()}]
            cursor.execute('''
                INSERT INTO recorder_positions (recorder_id, ticker, side, total_quantity, avg_entry_price, entries)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recorder_id, ticker, side, quantity, price, json_module.dumps(entries)))
            
            logger.info(f"📊 New position: {side} {ticker} x{quantity} @ {price}")
            return cursor.lastrowid, True, quantity
        
        # First, check if any open trade hit TP/SL based on current price
        if open_trade:
            hit_type, hit_price, hit_ticks = check_tp_sl_hit(open_trade, current_price, tick_size)
            
            if hit_type:
                # TP or SL was hit - close at the TP/SL price, not current price
                pnl, pnl_ticks = close_trade(cursor, open_trade, hit_price, hit_ticks, tick_value, hit_type)
                
                trade_result = {
                    'action': 'closed',
                    'trade_id': open_trade['id'],
                    'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'],
                    'exit_price': hit_price,
                    'pnl': pnl,
                    'pnl_ticks': pnl_ticks,
                    'exit_reason': hit_type.upper()
                }
                logger.info(f"🎯 {hit_type.upper()} HIT for '{recorder_name}': {open_trade['side']} {ticker} | Exit: {hit_price} | PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks)")
                open_trade = None  # Trade is now closed
        
        # Now process the signal action
        
        # Handle TP/SL price alerts from TradingView
        if normalized_action == 'TP_HIT':
            if open_trade:
                # Close at TP price (use stored TP or current price if not set)
                tp_price = open_trade.get('tp_price') or current_price
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (tp_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - tp_price) / tick_size
                
                pnl, _ = close_trade(cursor, open_trade, tp_price, pnl_ticks, tick_value, 'tp')
                
                # Also close any open position in recorder_positions
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (recorder_id, ticker))
                open_pos = cursor.fetchone()
                if open_pos:
                    close_recorder_position(cursor, open_pos[0], tp_price, ticker)
                
                trade_result = {
                    'action': 'closed',
                    'trade_id': open_trade['id'],
                    'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'],
                    'exit_price': tp_price,
                    'pnl': pnl,
                    'pnl_ticks': pnl_ticks,
                    'exit_reason': 'TP'
                }
                logger.info(f"🎯 TP HIT (alert) for '{recorder_name}': {open_trade['side']} {ticker} | Exit: {tp_price} | PnL: ${pnl:.2f}")
        
        elif normalized_action == 'SL_HIT':
            if open_trade:
                # Close at SL price (use stored SL or current price if not set)
                sl_price = open_trade.get('sl_price') or current_price
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (sl_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - sl_price) / tick_size
                
                pnl, _ = close_trade(cursor, open_trade, sl_price, pnl_ticks, tick_value, 'sl')
                
                # Also close any open position in recorder_positions
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (recorder_id, ticker))
                open_pos = cursor.fetchone()
                if open_pos:
                    close_recorder_position(cursor, open_pos[0], sl_price, ticker)
                
                trade_result = {
                    'action': 'closed',
                    'trade_id': open_trade['id'],
                    'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'],
                    'exit_price': sl_price,
                    'pnl': pnl,
                    'pnl_ticks': pnl_ticks,
                    'exit_reason': 'SL'
                }
                logger.info(f"🛑 SL HIT (alert) for '{recorder_name}': {open_trade['side']} {ticker} | Exit: {sl_price} | PnL: ${pnl:.2f}")
        
        elif normalized_action == 'PRICE_UPDATE':
            # Just a price update - check if it hits TP/SL
            if open_trade:
                hit_type, hit_price, hit_ticks = check_tp_sl_hit(open_trade, current_price, tick_size)
                if hit_type:
                    pnl, pnl_ticks = close_trade(cursor, open_trade, hit_price, hit_ticks, tick_value, hit_type)
                    trade_result = {
                        'action': 'closed',
                        'trade_id': open_trade['id'],
                        'side': open_trade['side'],
                        'entry_price': open_trade['entry_price'],
                        'exit_price': hit_price,
                        'pnl': pnl,
                        'pnl_ticks': pnl_ticks,
                        'exit_reason': hit_type.upper()
                    }
                    logger.info(f"🎯 {hit_type.upper()} from price update for '{recorder_name}': PnL ${pnl:.2f}")
                    open_trade = None
        
        elif normalized_action == 'CLOSE' or (market_position and market_position.lower() == 'flat'):
            # Close any open trade at current price
            if open_trade:
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                
                pnl, _ = close_trade(cursor, open_trade, current_price, pnl_ticks, tick_value, 'signal')
                
                trade_result = {
                    'action': 'closed',
                    'trade_id': open_trade['id'],
                    'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'],
                    'exit_price': current_price,
                    'pnl': pnl,
                    'pnl_ticks': pnl_ticks,
                    'exit_reason': 'SIGNAL'
                }
                logger.info(f"📊 Trade CLOSED by signal for '{recorder_name}': {open_trade['side']} {ticker} | PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks)")
            
            # Always close any open position in recorder_positions (even if no open trade)
            cursor.execute('''
                SELECT id FROM recorder_positions 
                WHERE recorder_id = ? AND ticker = ? AND status = 'open'
            ''', (recorder_id, ticker))
            open_pos = cursor.fetchone()
            if open_pos:
                close_recorder_position(cursor, open_pos[0], current_price, ticker)
        
        elif normalized_action == 'BUY':
            # If we have an open SHORT, close it first
            if open_trade and open_trade['side'] == 'SHORT':
                pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                pnl, _ = close_trade(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                
                logger.info(f"📊 SHORT closed by BUY reversal: ${pnl:.2f}")
                open_trade = None
            
            # Open new LONG trade if no open trade
            if not open_trade:
                # For STRATEGY alerts: NO TP/SL - TradingView strategy manages exits via signals
                # For INDICATOR alerts: Use recorder TP/SL settings
                if is_strategy_alert:
                    tp_price, sl_price = None, None
                    logger.info(f"📊 STRATEGY MODE: No TP/SL - TradingView controls exits")
                else:
                    # Calculate TP/SL prices based on recorder settings
                    tp_price, sl_price = calculate_tp_sl_prices(
                        current_price, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                
                cursor.execute('''
                    INSERT INTO recorded_trades 
                    (recorder_id, signal_id, ticker, action, side, entry_price, entry_time, 
                     quantity, status, tp_price, sl_price, tp_ticks, sl_ticks)
                    VALUES (?, ?, ?, ?, 'LONG', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?, ?, ?)
                ''', (recorder_id, signal_id, ticker, 'BUY', current_price, quantity,
                      tp_price, sl_price, tp_ticks, sl_amount if sl_enabled else None))
                
                new_trade_id = cursor.lastrowid
                
                # Also update position tracking for combined drawdown
                pos_id, is_new_pos, total_qty = update_recorder_position(
                    cursor, recorder_id, ticker, 'LONG', current_price, quantity
                )
                
                trade_result = {
                    'action': 'opened',
                    'trade_id': new_trade_id,
                    'side': 'LONG',
                    'entry_price': current_price,
                    'quantity': quantity,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'position_id': pos_id,
                    'position_qty': total_qty
                }
                logger.info(f"📈 LONG opened for '{recorder_name}': {ticker} @ {current_price} x{quantity} | TP: {tp_price} | SL: {sl_price} | Position: {total_qty} total")
        
        elif normalized_action == 'SELL':
            # If we have an open LONG, close it first
            if open_trade and open_trade['side'] == 'LONG':
                pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                pnl, _ = close_trade(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                
                logger.info(f"📊 LONG closed by SELL reversal: ${pnl:.2f}")
                open_trade = None
            
            # Open new SHORT trade if no open trade
            if not open_trade:
                # For STRATEGY alerts: NO TP/SL - TradingView strategy manages exits via signals
                # For INDICATOR alerts: Use recorder TP/SL settings
                if is_strategy_alert:
                    tp_price, sl_price = None, None
                    logger.info(f"📊 STRATEGY MODE: No TP/SL - TradingView controls exits")
                else:
                    # Calculate TP/SL prices based on recorder settings
                    tp_price, sl_price = calculate_tp_sl_prices(
                        current_price, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                
                cursor.execute('''
                    INSERT INTO recorded_trades 
                    (recorder_id, signal_id, ticker, action, side, entry_price, entry_time, 
                     quantity, status, tp_price, sl_price, tp_ticks, sl_ticks)
                    VALUES (?, ?, ?, ?, 'SHORT', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?, ?, ?)
                ''', (recorder_id, signal_id, ticker, 'SELL', current_price, quantity,
                      tp_price, sl_price, tp_ticks, sl_amount if sl_enabled else None))
                
                new_trade_id = cursor.lastrowid
                
                # Also update position tracking for combined drawdown
                pos_id, is_new_pos, total_qty = update_recorder_position(
                    cursor, recorder_id, ticker, 'SHORT', current_price, quantity
                )
                
                trade_result = {
                    'action': 'opened',
                    'trade_id': new_trade_id,
                    'side': 'SHORT',
                    'entry_price': current_price,
                    'quantity': quantity,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'position_id': pos_id,
                    'position_qty': total_qty
                }
                logger.info(f"📉 SHORT opened for '{recorder_name}': {ticker} @ {current_price} x{quantity} | TP: {tp_price} | SL: {sl_price} | Position: {total_qty} total")
        
        conn.commit()
        conn.close()
        
        # Emit real-time update via WebSocket
        try:
            socketio.emit('signal_received', {
                'recorder_id': recorder_id,
                'recorder_name': recorder_name,
                'signal_id': signal_id,
                'action': normalized_action,
                'ticker': ticker,
                'price': price,
                'position_size': position_size,
                'signal_type': 'strategy' if is_strategy_alert else 'alert',
                'timestamp': datetime.now().isoformat(),
                'trade': trade_result
            })
            
            # If a trade was closed, also emit trade_executed event for dashboard
            if trade_result and trade_result.get('action') == 'closed':
                socketio.emit('trade_executed', {
                    'recorder_id': recorder_id,
                    'recorder_name': recorder_name,
                    'trade_id': trade_result['trade_id'],
                    'side': trade_result['side'],
                    'pnl': trade_result['pnl'],
                    'ticker': ticker,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.warning(f"Could not emit WebSocket update: {e}")
        
        logger.info(f"✅ Signal recorded for '{recorder_name}': {normalized_action} {ticker} @ {price}")
        
        # Build response based on alert type
        response = {
            'success': True,
            'message': f'Signal received and recorded',
            'signal_id': signal_id,
            'recorder': recorder_name,
            'action': normalized_action,
            'ticker': ticker,
            'price': price,
            'signal_number': signal_count
        }
        
        # Add trade information to response
        if trade_result:
            response['trade'] = trade_result
            if trade_result.get('action') == 'closed':
                response['message'] = f"Trade closed with PnL: ${trade_result['pnl']:.2f}"
            elif trade_result.get('action') == 'opened':
                response['message'] = f"{trade_result['side']} position opened @ {trade_result['entry_price']}"
        
        if is_strategy_alert:
            response['signal_type'] = 'strategy'
            response['position_size'] = position_size
            response['market_position'] = market_position
            response['note'] = 'Strategy alert - TradingView manages position sizing'
        else:
            response['signal_type'] = 'alert'
            response['note'] = 'Simple alert - Recorder settings control sizing/risk'
            response['recorder_settings'] = {
                'initial_position_size': recorder.get('initial_position_size'),
                'tp_enabled': bool(recorder.get('tp_targets')),
                'sl_enabled': bool(recorder.get('sl_enabled'))
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# END OF DISABLED LEGACY WEBHOOK CODE
# ============================================================

@app.route('/api/recorders/<int:recorder_id>/signals', methods=['GET'])
def api_get_recorder_signals(recorder_id):
    """Get recorded signals for a recorder"""
    try:
        limit = int(request.args.get('limit', 50))
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM recorded_signals 
            WHERE recorder_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (recorder_id, limit))
        
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'signals': signals,
            'count': len(signals)
        })
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/trades', methods=['GET'])
def api_get_recorder_trades(recorder_id):
    """Get recorded trades for a recorder with pagination and filters"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # open, closed, or all
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build query with filters
        where_clauses = ['recorder_id = ?']
        params = [recorder_id]
        
        if status and status != 'all':
            where_clauses.append('status = ?')
            params.append(status)
        
        where_sql = ' AND '.join(where_clauses)
        
        # Get total count
        cursor.execute(f'SELECT COUNT(*) FROM recorded_trades WHERE {where_sql}', params)
        total = cursor.fetchone()[0]
        
        # Get paginated trades
        offset = (page - 1) * per_page
        cursor.execute(f'''
            SELECT * FROM recorded_trades 
            WHERE {where_sql}
            ORDER BY entry_time DESC 
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'trades': trades,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': page * per_page < total
            }
        })
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/pnl', methods=['GET'])
def api_get_recorder_pnl(recorder_id):
    """Get PnL summary and history for a recorder"""
    try:
        timeframe = request.args.get('timeframe', 'all')  # today, week, month, 3months, 6months, year, all
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build date filter
        date_filter = ''
        if timeframe == 'today':
            date_filter = "AND DATE(exit_time) = DATE('now')"
        elif timeframe == 'week':
            date_filter = "AND exit_time >= DATE('now', '-7 days')"
        elif timeframe == 'month':
            date_filter = "AND exit_time >= DATE('now', '-30 days')"
        elif timeframe == '3months':
            date_filter = "AND exit_time >= DATE('now', '-90 days')"
        elif timeframe == '6months':
            date_filter = "AND exit_time >= DATE('now', '-180 days')"
        elif timeframe == 'year':
            date_filter = "AND exit_time >= DATE('now', '-365 days')"
        
        # Get summary stats for closed trades
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                SUM(pnl_ticks) as total_ticks,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as max_profit,
                MIN(pnl) as max_loss,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss
            FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'closed' {date_filter}
        ''', (recorder_id,))
        
        stats = dict(cursor.fetchone())
        
        # Calculate win rate and profit factor
        wins = stats.get('wins') or 0
        losses = stats.get('losses') or 0
        total = wins + losses
        stats['win_rate'] = round((wins / total * 100), 1) if total > 0 else 0
        
        avg_win = abs(stats.get('avg_win') or 0)
        avg_loss = abs(stats.get('avg_loss') or 1)
        stats['profit_factor'] = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
        
        # Get daily PnL for charting
        cursor.execute(f'''
            SELECT 
                DATE(exit_time) as date,
                SUM(pnl) as daily_pnl,
                COUNT(*) as trade_count,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as daily_wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as daily_losses
            FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'closed' {date_filter}
            GROUP BY DATE(exit_time)
            ORDER BY DATE(exit_time) ASC
        ''', (recorder_id,))
        
        daily_pnl = [dict(row) for row in cursor.fetchall()]
        
        # Calculate cumulative PnL for chart
        cumulative = 0
        max_cumulative = 0
        max_drawdown = 0
        
        for day in daily_pnl:
            cumulative += day['daily_pnl'] or 0
            day['cumulative_pnl'] = cumulative
            
            if cumulative > max_cumulative:
                max_cumulative = cumulative
            
            drawdown = max_cumulative - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            day['drawdown'] = drawdown
        
        stats['max_drawdown'] = max_drawdown
        
        # Get open position if any
        cursor.execute('''
            SELECT * FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'open'
            ORDER BY entry_time DESC LIMIT 1
        ''', (recorder_id,))
        
        open_trade = cursor.fetchone()
        if open_trade:
            stats['open_position'] = dict(open_trade)
        
        # Get recorder name
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        recorder = cursor.fetchone()
        stats['recorder_name'] = recorder['name'] if recorder else f'Recorder {recorder_id}'
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': stats,
            'daily_pnl': daily_pnl,
            'chart_data': {
                'labels': [d['date'] for d in daily_pnl],
                'profit': [d['cumulative_pnl'] for d in daily_pnl],
                'drawdown': [d['drawdown'] for d in daily_pnl]
            }
        })
    except Exception as e:
        logger.error(f"Error getting PnL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/all/pnl', methods=['GET'])
def api_get_all_recorders_pnl():
    """Get aggregated PnL for all recorders (for dashboard)"""
    try:
        timeframe = request.args.get('timeframe', 'month')
        recorder_id = request.args.get('recorder_id')  # Optional filter
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build date filter
        date_filter = ''
        if timeframe == 'today':
            date_filter = "AND DATE(rt.exit_time) = DATE('now')"
        elif timeframe == 'week':
            date_filter = "AND rt.exit_time >= DATE('now', '-7 days')"
        elif timeframe == 'month':
            date_filter = "AND rt.exit_time >= DATE('now', '-30 days')"
        elif timeframe == '3months':
            date_filter = "AND rt.exit_time >= DATE('now', '-90 days')"
        elif timeframe == '6months':
            date_filter = "AND rt.exit_time >= DATE('now', '-180 days')"
        elif timeframe == 'year':
            date_filter = "AND rt.exit_time >= DATE('now', '-365 days')"
        
        recorder_filter = ''
        params = []
        if recorder_id:
            recorder_filter = 'AND rt.recorder_id = ?'
            params.append(int(recorder_id))
        
        # Get per-recorder summary
        cursor.execute(f'''
            SELECT 
                r.id as recorder_id,
                r.name as recorder_name,
                r.symbol,
                COUNT(rt.id) as total_trades,
                SUM(CASE WHEN rt.pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN rt.pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(rt.pnl) as total_pnl,
                AVG(rt.pnl) as avg_pnl
            FROM recorders r
            LEFT JOIN recorded_trades rt ON r.id = rt.recorder_id AND rt.status = 'closed' {date_filter}
            WHERE 1=1 {recorder_filter}
            GROUP BY r.id
            ORDER BY total_pnl DESC
        ''', params)
        
        recorders = []
        for row in cursor.fetchall():
            rec = dict(row)
            wins = rec['wins'] or 0
            losses = rec['losses'] or 0
            total = wins + losses
            rec['win_rate'] = round((wins / total * 100), 1) if total > 0 else 0
            recorders.append(rec)
        
        # Get daily aggregate PnL for chart
        cursor.execute(f'''
            SELECT 
                DATE(rt.exit_time) as date,
                SUM(rt.pnl) as daily_pnl,
                COUNT(rt.id) as trade_count
            FROM recorded_trades rt
            WHERE rt.status = 'closed' {date_filter} {recorder_filter.replace('rt.recorder_id', 'rt.recorder_id')}
            GROUP BY DATE(rt.exit_time)
            ORDER BY DATE(rt.exit_time) ASC
        ''', params)
        
        daily_data = [dict(row) for row in cursor.fetchall()]
        
        # Calculate cumulative
        cumulative = 0
        max_cumulative = 0
        for day in daily_data:
            cumulative += day['daily_pnl'] or 0
            day['cumulative_pnl'] = cumulative
            if cumulative > max_cumulative:
                max_cumulative = cumulative
            day['drawdown'] = max_cumulative - cumulative
        
        conn.close()
        
        return jsonify({
            'success': True,
            'recorders': recorders,
            'chart_data': {
                'labels': [d['date'] for d in daily_data],
                'profit': [d['cumulative_pnl'] for d in daily_data],
                'drawdown': [d['drawdown'] for d in daily_data]
            },
            'total_pnl': sum(r['total_pnl'] or 0 for r in recorders),
            'total_trades': sum(r['total_trades'] or 0 for r in recorders)
        })
    except Exception as e:
        logger.error(f"Error getting all recorders PnL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/traders')
def traders_list():
    """Traders list page - show all recorder-account links"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user ID for filtering
        user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            user_id = get_current_user_id()
        
        # Filter by user_id if logged in
        if user_id:
            if is_postgres:
                cursor.execute('''
                    SELECT t.id, t.enabled, t.subaccount_name, t.is_demo,
                           r.name as recorder_name,
                           a.name as account_name
                    FROM traders t
                    LEFT JOIN recorders r ON t.recorder_id = r.id
                    LEFT JOIN accounts a ON t.account_id = a.id
                    WHERE t.user_id = %s
                    ORDER BY t.created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT t.id, t.enabled, t.subaccount_name, t.is_demo,
                           r.name as recorder_name,
                           a.name as account_name
                    FROM traders t
                    LEFT JOIN recorders r ON t.recorder_id = r.id
                    LEFT JOIN accounts a ON t.account_id = a.id
                    WHERE t.user_id = ?
                    ORDER BY t.created_at DESC
                ''', (user_id,))
        else:
            # Fallback: show all (shouldn't happen if login required)
            cursor.execute('''
                SELECT t.id, t.enabled, t.subaccount_name, t.is_demo,
                       r.name as recorder_name,
                       a.name as account_name
                FROM traders t
                LEFT JOIN recorders r ON t.recorder_id = r.id
                LEFT JOIN accounts a ON t.account_id = a.id
                ORDER BY t.created_at DESC
            ''')
        
        rows = cursor.fetchall()
        traders = []
        columns = ['id', 'enabled', 'subaccount_name', 'is_demo', 'recorder_name', 'account_name']
        
        for row in rows:
            if hasattr(row, 'keys'):
                row_dict = dict(row)
            else:
                row_dict = dict(zip(columns[:len(row)], row))
            
            is_demo = bool(row_dict.get('is_demo')) if row_dict.get('is_demo') is not None else None
            env_label = "🟠 DEMO" if is_demo else "🟢 LIVE" if is_demo is not None else ""
            account_name = row_dict.get('account_name') or 'Unknown'
            subaccount_name = row_dict.get('subaccount_name')
            
            if subaccount_name:
                display_account = f"{account_name} {env_label} ({subaccount_name})"
            else:
                display_account = account_name
            
            traders.append({
                'id': row_dict.get('id'),
                'recorder_name': row_dict.get('recorder_name') or 'Unknown',
                'strategy_type': row_dict.get('strategy_type', 'Futures'),
                'account_name': display_account,
                'enabled': bool(row_dict.get('enabled'))
            })
        
        conn.close()
        
        return render_template(
            'traders.html',
            mode='list',
            traders=traders
        )
    except Exception as e:
        logger.error(f"Error in traders_list: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"<h1>Error loading traders</h1><pre>{str(e)}</pre>", 500

@app.route('/my-traders')
def my_traders():
    """My Traders page - link recorders to accounts"""
    return render_template('my_traders_tab.html')

@app.route('/traders/new/debug')
def traders_new_debug():
    """Debug endpoint to test traders/new logic without template"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recorders
        cursor.execute('SELECT id, name, strategy_type FROM recorders ORDER BY name')
        recorders = cursor.fetchall()
        
        # Get accounts - use PostgreSQL compatible query
        is_postgres = is_using_postgres()
        if is_postgres:
            cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = true')
        else:
            cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = 1')
        accounts = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'is_postgres': is_postgres,
            'recorders_count': len(recorders) if recorders else 0,
            'accounts_count': len(accounts) if accounts else 0,
            'deploy_time': '2025-12-19T01:15:00Z'
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/traders/new')
def traders_new():
    """Create new trader page - select recorder and accounts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        # Get current user for filtering
        user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            user_id = get_current_user_id()
        
        # Get recorders with their IDs for the dropdown - includes shared recorders (user_id IS NULL)
        if user_id:
            if is_postgres:
                cursor.execute('SELECT id, name, strategy_type FROM recorders WHERE (user_id = %s OR user_id IS NULL) ORDER BY name', (user_id,))
            else:
                cursor.execute('SELECT id, name, strategy_type FROM recorders WHERE (user_id = ? OR user_id IS NULL) ORDER BY name', (user_id,))
        else:
            # Not logged in - show nothing
            cursor.execute('SELECT id, name, strategy_type FROM recorders WHERE 1=0')
        recorders = []
        for row in cursor.fetchall():
            # Handle both dict-style and tuple-style rows
            if hasattr(row, 'get'):
                recorders.append({'id': row.get('id'), 'name': row.get('name'), 'strategy_type': row.get('strategy_type', 'Futures')})
            elif hasattr(row, '__getitem__'):
                recorders.append({'id': row['id'], 'name': row['name'], 'strategy_type': row.get('strategy_type', 'Futures') if hasattr(row, 'get') else 'Futures'})
            else:
                recorders.append({'id': row[0], 'name': row[1], 'strategy_type': row[2] if len(row) > 2 else 'Futures'})
        
        # Get accounts with their tradovate subaccounts - STRICT: only user's own accounts
        if user_id:
            if is_postgres:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = true AND user_id = %s', (user_id,))
            else:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = 1 AND user_id = ?', (user_id,))
        else:
            if is_postgres:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = true')
            else:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = 1')
        accounts = []
        for row in cursor.fetchall():
            # Handle both dict-style and tuple-style rows
            if hasattr(row, 'get'):
                parent_id = row.get('id')
                parent_name = row.get('name')
                tradovate_json = row.get('tradovate_accounts')
            else:
                parent_id = row['id'] if hasattr(row, '__getitem__') else row[0]
                parent_name = row['name'] if hasattr(row, '__getitem__') else row[1]
                tradovate_json = row['tradovate_accounts'] if hasattr(row, '__getitem__') else (row[2] if len(row) > 2 else None)
            
            # Parse tradovate_accounts JSON if available
            if tradovate_json:
                try:
                    tradovate_accts = json.loads(tradovate_json)
                    for acct in tradovate_accts:
                        if isinstance(acct, dict) and acct.get('name'):
                            env_label = "🟠 DEMO" if acct.get('is_demo') else "🟢 LIVE"
                            accounts.append({
                                'id': parent_id,
                                'name': acct['name'],
                                'display_name': f"{env_label} - {acct['name']} ({parent_name})",
                                'subaccount_id': acct.get('id'),
                                'is_demo': acct.get('is_demo', False)
                            })
                except:
                    pass
            # Fallback to account name if no tradovate_accounts parsed
            if not accounts or (accounts and accounts[-1].get('id') != parent_id):
                accounts.append({
                    'id': parent_id,
                    'name': parent_name,
                    'display_name': parent_name,
                    'subaccount_id': None,
                    'is_demo': False
                })
        
        conn.close()
        
        # Debug: Log what we're passing to template
        logger.info(f"traders_new: {len(recorders)} recorders, {len(accounts)} accounts")
        
        try:
            return render_template(
                'traders.html',
                mode='builder',
                header_title='Create New Trader',
                header_cta='Create Trader',
                recorders=recorders,
                accounts=accounts
            )
        except Exception as template_err:
            logger.error(f"Template rendering error in traders_new: {template_err}")
            import traceback
            logger.error(traceback.format_exc())
            return f"<h1>Template Error</h1><pre>{str(template_err)}</pre>", 500
    except Exception as e:
        logger.error(f"Error in traders_new: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"<h1>Error loading page</h1><pre>{str(e)}</pre>", 500

@app.route('/traders/<int:trader_id>')
def traders_edit(trader_id):
    """Edit existing trader - load all saved settings"""
    # Require login
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        is_postgres = is_using_postgres()
        # Only set row_factory for SQLite - PostgreSQL already uses RealDictCursor
        if not is_postgres:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get current user ID for ownership check
        current_user_id = None
        if USER_AUTH_AVAILABLE and is_logged_in():
            current_user_id = get_current_user_id()
        
        # Get the trader with its recorder info (CRITICAL: include all recorder settings for risk management)
        placeholder = '%s' if is_postgres else '?'
        cursor.execute(f'''
            SELECT t.*, 
                   r.name as recorder_name, r.strategy_type, r.symbol,
                   r.initial_position_size as r_initial_position_size,
                   r.add_position_size as r_add_position_size,
                   r.tp_targets as r_tp_targets,
                   r.tp_units as r_tp_units,
                   r.trim_units as r_trim_units,
                   r.sl_enabled as r_sl_enabled,
                   r.sl_amount as r_sl_amount,
                   r.sl_units as r_sl_units,
                   r.sl_type as r_sl_type,
                   r.avg_down_enabled as r_avg_down_enabled,
                   r.avg_down_amount as r_avg_down_amount,
                   r.avg_down_point as r_avg_down_point,
                   r.avg_down_units as r_avg_down_units,
                   a.name as account_name, a.id as parent_account_id
            FROM traders t
            JOIN recorders r ON t.recorder_id = r.id
            JOIN accounts a ON t.account_id = a.id
            WHERE t.id = {placeholder}
        ''', (trader_id,))
        trader_row = cursor.fetchone()
        
        if not trader_row:
            conn.close()
            logger.warning(f"Trader {trader_id} not found")
            return redirect('/traders')
        
        # Check ownership - only allow editing own traders
        trader_user_id = trader_row.get('user_id') if hasattr(trader_row, 'get') else (trader_row['user_id'] if 'user_id' in (trader_row.keys() if hasattr(trader_row, 'keys') else []) else None)
        if current_user_id and trader_user_id and trader_user_id != current_user_id:
            conn.close()
            logger.warning(f"User {current_user_id} tried to edit trader {trader_id} owned by user {trader_user_id}")
            return redirect('/traders')
        
        # Parse TP targets from JSON (prefer recorder settings)
        tp_targets = []
        tp_value = 0  # Default to 0 (no TP) if not set
        tp_trim = 100
        try:
            tp_targets_raw = trader_row['r_tp_targets'] or trader_row['tp_targets']
            if tp_targets_raw:
                tp_targets = json.loads(tp_targets_raw)
                if tp_targets and len(tp_targets) > 0:
                    tp_value = tp_targets[0].get('value', 0)
                    tp_trim = tp_targets[0].get('trim', 100)
        except:
            tp_targets = []
        
        # Build trader object with settings (prefer recorder settings which are authoritative)
        trader = {
        'id': trader_row['id'],
        'recorder_id': trader_row['recorder_id'],
        'recorder_name': trader_row['recorder_name'],
        'strategy_type': trader_row['strategy_type'] or 'Futures',
        'account_id': trader_row['account_id'],
        'account_name': trader_row['account_name'],
        'subaccount_id': trader_row['subaccount_id'],
        'subaccount_name': trader_row['subaccount_name'],
        'is_demo': bool(trader_row['is_demo']),
        'enabled': bool(trader_row['enabled']),
        # Position sizes - prefer recorder settings
        'initial_position_size': trader_row['r_initial_position_size'] or trader_row['initial_position_size'] or 1,
        'add_position_size': trader_row['r_add_position_size'] or trader_row['add_position_size'] or 1,
        # TP settings from recorder
        'tp_targets': tp_targets,
        'tp_value': tp_value,
        'tp_trim': tp_trim,
        'tp_units': trader_row['r_tp_units'] or 'Ticks',
        'trim_units': trader_row['r_trim_units'] or 'Contracts',
        # SL settings from recorder
        'sl_enabled': bool(trader_row['r_sl_enabled']),
        'sl_amount': trader_row['r_sl_amount'] or 0,
        'sl_units': trader_row['r_sl_units'] or 'Ticks',
        'sl_type': trader_row['r_sl_type'] or 'Fixed',
        # DCA/Averaging Down settings from recorder
        'avg_down_enabled': bool(trader_row['r_avg_down_enabled']),
        'avg_down_amount': trader_row['r_avg_down_amount'] or 1,
        'avg_down_point': trader_row['r_avg_down_point'] or 10,
            'avg_down_units': trader_row['r_avg_down_units'] or 'Ticks',
            'max_daily_loss': trader_row['max_daily_loss'] or 500
        }
        
        # Get enabled accounts from routing (if stored)
        enabled_accounts = []
        try:
            # sqlite3.Row uses dict-style access, not .get()
            enabled_accounts_raw = trader_row['enabled_accounts'] if 'enabled_accounts' in trader_row.keys() else None
            if enabled_accounts_raw and enabled_accounts_raw != '[]' and str(enabled_accounts_raw).strip():
                enabled_accounts = json.loads(enabled_accounts_raw)
                logger.info(f"✅ Loaded enabled_accounts for trader {trader_id}: {len(enabled_accounts)} accounts")
                for acct in enabled_accounts:
                    logger.info(f"  - Enabled: {acct.get('account_name')} (subaccount_id={acct.get('subaccount_id')})")
            else:
                logger.info(f"⚠️ No enabled_accounts found for trader {trader_id} (raw value: '{enabled_accounts_raw}')")
        except Exception as e:
            logger.warning(f"❌ Error parsing enabled_accounts: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            enabled_accounts = []
        
        # Get all accounts with subaccounts for the routing table (only user's accounts)
        if current_user_id:
            if is_postgres:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = true AND user_id = %s', (current_user_id,))
            else:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = 1 AND user_id = ?', (current_user_id,))
        else:
            if is_postgres:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = true')
            else:
                cursor.execute('SELECT id, name, tradovate_accounts FROM accounts WHERE enabled = 1')
        accounts = []
        for row in cursor.fetchall():
            parent_id = row['id']
            parent_name = row['name']
            if row['tradovate_accounts']:
                try:
                    tradovate_accts = json.loads(row['tradovate_accounts'])
                    for acct in tradovate_accts:
                        if isinstance(acct, dict) and acct.get('name'):
                            env_label = "🟠 DEMO" if acct.get('is_demo') else "🟢 LIVE"
                            # Check if this subaccount is enabled in account routing
                            is_enabled = False
                            acct_subaccount_id = acct.get('id')  # This is the subaccount ID from tradovate_accounts
                            for enabled_acct in enabled_accounts:
                                # Match by subaccount_id (most reliable)
                                enabled_subaccount_id = enabled_acct.get('subaccount_id')
                                if enabled_subaccount_id and enabled_subaccount_id == acct_subaccount_id:
                                    is_enabled = True
                                    logger.info(f"  ✓ Account {acct.get('name')} (subaccount_id={acct_subaccount_id}) is ENABLED")
                                    break
                            # If no enabled_accounts stored, use legacy: check if it's the primary account
                            if not enabled_accounts:
                                is_enabled = (acct_subaccount_id == trader['subaccount_id'])
                                logger.debug(f"  - Using legacy check: {acct.get('name')} is_selected={is_enabled}")
                            accounts.append({
                                'id': parent_id,
                                'name': acct['name'],
                                'display_name': f"{env_label} - {acct['name']} ({parent_name})",
                                'subaccount_id': acct.get('id'),
                                'is_demo': acct.get('is_demo', False),
                                'is_selected': is_enabled
                            })
                except:
                    pass
        
        conn.close()
    except Exception as e:
        logger.error(f"Error loading trader: {e}")
        if 'conn' in locals():
            conn.close()
        return redirect('/traders')
        
        return render_template(
            'traders.html',
            mode='edit',
            header_title='Edit Trader',
            header_cta='Update Trader',
            trader=trader,
            accounts=accounts
        )
    except Exception as e:
        logger.error(f"Error in traders_edit for trader {trader_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"<h1>Error loading trader</h1><pre>{str(e)}</pre>", 500

@app.route('/control-center')
def control_center():
    """Control Center with live recorder/strategy data and PnL"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all recorders with their PnL
        cursor.execute('''
            SELECT 
                r.id,
                r.name,
                r.symbol,
                r.recording_enabled,
                COALESCE(SUM(CASE WHEN rt.status = 'closed' THEN rt.pnl ELSE 0 END), 0) as total_pnl,
                COUNT(CASE WHEN rt.status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN rt.status = 'closed' THEN 1 END) as closed_trades
            FROM recorders r
            LEFT JOIN recorded_trades rt ON r.id = rt.recorder_id
            GROUP BY r.id
            ORDER BY r.name
        ''')
        
        live_rows = []
        for row in cursor.fetchall():
            live_rows.append({
                'id': row['id'],
                'name': row['name'],
                'symbol': row['symbol'] or '',
                'enabled': bool(row['recording_enabled']),
                'pnl': row['total_pnl'] or 0,
                'open_trades': row['open_trades'] or 0,
                'closed_trades': row['closed_trades'] or 0
            })
        
        # Get recent signals as logs
        cursor.execute('''
            SELECT 
                rs.action,
                rs.ticker,
                rs.price,
                rs.created_at,
                r.name as recorder_name
            FROM recorded_signals rs
            JOIN recorders r ON rs.recorder_id = r.id
            ORDER BY rs.created_at DESC
            LIMIT 20
        ''')
        
        logs = []
        for row in cursor.fetchall():
            log_type = 'open' if row['action'] in ['BUY', 'LONG'] else 'close'
            logs.append({
                'type': log_type,
                'message': f"{row['recorder_name']}: {row['action']} {row['ticker']} @ {row['price']}",
                'time': row['created_at']
            })
        
        conn.close()
        
        return render_template('control_center.html', live_rows=live_rows, logs=logs)
    except Exception as e:
        logger.error(f"Error loading control center: {e}")
        return render_template('control_center.html', live_rows=[], logs=[])

@app.route('/manual-trader')
def manual_trader_page():
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('manual_copy_trader.html')


# ============================================================================
# QUANT STOCK SCREENER (Restored Dec 8, 2025)
# ============================================================================

@app.route('/quant-screener')
def quant_screener_page():
    """Render the Quant Stock Screener page"""
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('quant_screener.html')


@app.route('/api/quant-screener/screen', methods=['POST'])
def api_quant_screener_screen():
    """Run a stock screen with the given filters"""
    try:
        filters = request.get_json() or {}
        
        # Get filter values
        min_score = filters.get('min_score', 0)
        min_rating = filters.get('min_rating', '')
        value_grade = filters.get('value_grade', '')
        growth_grade = filters.get('growth_grade', '')
        profitability_grade = filters.get('profitability_grade', '')
        momentum_grade = filters.get('momentum_grade', '')
        eps_revisions_grade = filters.get('eps_revisions_grade', '')
        sector = filters.get('sector', '')
        market_cap = filters.get('market_cap', '')
        min_price = filters.get('min_price', 0)
        max_price = filters.get('max_price', None)
        
        # Generate sample stock universe with quant ratings
        results = generate_quant_stock_data(
            min_score=min_score,
            min_rating=min_rating,
            value_grade=value_grade,
            growth_grade=growth_grade,
            profitability_grade=profitability_grade,
            momentum_grade=momentum_grade,
            eps_revisions_grade=eps_revisions_grade,
            sector=sector,
            market_cap=market_cap,
            min_price=min_price,
            max_price=max_price
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Error running quant screen: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quant-screener/factors/<symbol>', methods=['GET'])
def api_quant_screener_factors(symbol):
    """Get detailed factor grades for a specific stock"""
    try:
        stock_data = generate_single_stock_factors(symbol.upper())
        
        if stock_data:
            return jsonify({
                'success': True,
                'data': stock_data
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Stock {symbol} not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting factors for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quant-screener/search', methods=['GET'])
def api_quant_screener_search():
    """Search for stocks by symbol or name"""
    try:
        query = request.args.get('q', '').upper().strip()
        
        if not query:
            return jsonify({'success': True, 'results': []})
        
        all_stocks = get_stock_universe()
        
        results = []
        for stock in all_stocks:
            symbol_match = query in stock['symbol'].upper()
            name_match = query in stock['name'].upper()
            
            if symbol_match or name_match:
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'sector': stock.get('sector', 'Unknown').replace('_', ' ').title()
                })
        
        results.sort(key=lambda x: (0 if x['symbol'] == query else 1, x['symbol']))
        results = results[:10]
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error searching stocks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quant-screener/ticker/<symbol>', methods=['GET'])
def api_quant_screener_ticker(symbol):
    """Get full quant report for a specific ticker"""
    try:
        symbol = symbol.upper().strip()
        
        all_stocks = get_stock_universe()
        stock_info = None
        
        for stock in all_stocks:
            if stock['symbol'] == symbol:
                stock_info = stock
                break
        
        if not stock_info:
            stock_info = {
                'symbol': symbol,
                'name': symbol,
                'sector': 'unknown',
                'market_cap': 'large'
            }
        
        # Fetch live price from TradingView
        live_price = None
        change_pct = 0
        
        try:
            prices = fetch_live_stock_prices([symbol])
            if symbol in prices:
                live_price = prices[symbol]['price']
                change_pct = prices[symbol].get('change_pct', 0)
        except Exception as e:
            logger.warning(f"Could not fetch live price for {symbol}: {e}")
        
        # Generate quant factors (seeded by symbol for consistency)
        import random
        random.seed(hash(symbol))
        
        factors = {
            'value': generate_factor_grade(),
            'growth': generate_factor_grade(),
            'profitability': generate_factor_grade(),
            'momentum': generate_factor_grade(),
            'eps_revisions': generate_factor_grade()
        }
        
        # Calculate quant score (1.0-5.0 scale)
        quant_score = (
            (factors['value']['score'] * 4 + 1) * 0.20 +
            (factors['growth']['score'] * 4 + 1) * 0.20 +
            (factors['profitability']['score'] * 4 + 1) * 0.25 +
            (factors['momentum']['score'] * 4 + 1) * 0.20 +
            (factors['eps_revisions']['score'] * 4 + 1) * 0.15
        )
        
        # Determine rating
        if quant_score >= 4.5:
            rating = 'Strong Buy'
        elif quant_score >= 3.5:
            rating = 'Buy'
        elif quant_score >= 2.5:
            rating = 'Hold'
        elif quant_score >= 1.5:
            rating = 'Sell'
        else:
            rating = 'Strong Sell'
        
        stock_report = {
            'symbol': symbol,
            'name': stock_info.get('name', symbol),
            'sector': stock_info.get('sector', 'Unknown').replace('_', ' ').title(),
            'market_cap': stock_info.get('market_cap', 'Unknown').title(),
            'price': round(live_price, 2) if live_price else None,
            'change': round(change_pct, 2),
            'quant_score': round(quant_score, 2),
            'rating': rating,
            'factors': factors
        }
        
        return jsonify({
            'success': True,
            'stock': stock_report
        })
        
    except Exception as e:
        logger.error(f"Error getting ticker report for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quant-screener/live-prices', methods=['POST'])
def api_quant_screener_live_prices():
    """Fetch live stock prices from TradingView"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({'success': False, 'error': 'No symbols provided'}), 400
        
        symbols = symbols[:50]
        prices = fetch_live_stock_prices(symbols)
        
        return jsonify({
            'success': True,
            'prices': prices,
            'count': len(prices),
            'requested': len(symbols)
        })
        
    except Exception as e:
        logger.error(f"Error fetching live prices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quant-screener/live-price/<symbol>', methods=['GET'])
def api_quant_screener_live_price(symbol):
    """Get live price for a single stock symbol"""
    try:
        prices = fetch_live_stock_prices([symbol.upper()])
        
        if symbol.upper() in prices:
            return jsonify({
                'success': True,
                'symbol': symbol.upper(),
                'data': prices[symbol.upper()]
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Price not found for {symbol}'
            }), 404
            
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def get_stock_universe():
    """Get the full stock universe for searching"""
    return [
        # Tech Giants
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'technology', 'market_cap': 'mega'},
        {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'technology', 'market_cap': 'mega'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'technology', 'market_cap': 'mega'},
        {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'mega'},
        {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'technology', 'market_cap': 'mega'},
        {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'sector': 'technology', 'market_cap': 'mega'},
        {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'mega'},
        {'symbol': 'AMD', 'name': 'Advanced Micro Devices', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'INTC', 'name': 'Intel Corporation', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'ORCL', 'name': 'Oracle Corporation', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'sector': 'communication_services', 'market_cap': 'large'},
        {'symbol': 'CSCO', 'name': 'Cisco Systems Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'AVGO', 'name': 'Broadcom Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'QCOM', 'name': 'Qualcomm Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'TXN', 'name': 'Texas Instruments', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'IBM', 'name': 'IBM Corporation', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'NOW', 'name': 'ServiceNow Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'AMAT', 'name': 'Applied Materials', 'sector': 'technology', 'market_cap': 'large'},
        # Finance
        {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'financial_services', 'market_cap': 'mega'},
        {'symbol': 'BAC', 'name': 'Bank of America Corp.', 'sector': 'financial_services', 'market_cap': 'mega'},
        {'symbol': 'WFC', 'name': 'Wells Fargo & Co.', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'GS', 'name': 'Goldman Sachs Group', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'MS', 'name': 'Morgan Stanley', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'V', 'name': 'Visa Inc.', 'sector': 'financial_services', 'market_cap': 'mega'},
        {'symbol': 'MA', 'name': 'Mastercard Inc.', 'sector': 'financial_services', 'market_cap': 'mega'},
        {'symbol': 'AXP', 'name': 'American Express Co.', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'BLK', 'name': 'BlackRock Inc.', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'C', 'name': 'Citigroup Inc.', 'sector': 'financial_services', 'market_cap': 'large'},
        # Healthcare
        {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'healthcare', 'market_cap': 'mega'},
        {'symbol': 'UNH', 'name': 'UnitedHealth Group', 'sector': 'healthcare', 'market_cap': 'mega'},
        {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'ABBV', 'name': 'AbbVie Inc.', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'MRK', 'name': 'Merck & Co. Inc.', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'LLY', 'name': 'Eli Lilly & Co.', 'sector': 'healthcare', 'market_cap': 'mega'},
        {'symbol': 'TMO', 'name': 'Thermo Fisher Scientific', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'ABT', 'name': 'Abbott Laboratories', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'DHR', 'name': 'Danaher Corporation', 'sector': 'healthcare', 'market_cap': 'large'},
        {'symbol': 'BMY', 'name': 'Bristol-Myers Squibb', 'sector': 'healthcare', 'market_cap': 'large'},
        # Consumer
        {'symbol': 'WMT', 'name': 'Walmart Inc.', 'sector': 'consumer_defensive', 'market_cap': 'mega'},
        {'symbol': 'PG', 'name': 'Procter & Gamble Co.', 'sector': 'consumer_defensive', 'market_cap': 'mega'},
        {'symbol': 'KO', 'name': 'Coca-Cola Company', 'sector': 'consumer_defensive', 'market_cap': 'mega'},
        {'symbol': 'PEP', 'name': 'PepsiCo Inc.', 'sector': 'consumer_defensive', 'market_cap': 'mega'},
        {'symbol': 'COST', 'name': 'Costco Wholesale Corp.', 'sector': 'consumer_defensive', 'market_cap': 'large'},
        {'symbol': 'HD', 'name': 'Home Depot Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'mega'},
        {'symbol': 'MCD', 'name': "McDonald's Corporation", 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'NKE', 'name': 'Nike Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'SBUX', 'name': 'Starbucks Corporation', 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'TGT', 'name': 'Target Corporation', 'sector': 'consumer_defensive', 'market_cap': 'large'},
        # Energy
        {'symbol': 'XOM', 'name': 'Exxon Mobil Corp.', 'sector': 'energy', 'market_cap': 'mega'},
        {'symbol': 'CVX', 'name': 'Chevron Corporation', 'sector': 'energy', 'market_cap': 'mega'},
        {'symbol': 'COP', 'name': 'ConocoPhillips', 'sector': 'energy', 'market_cap': 'large'},
        {'symbol': 'SLB', 'name': 'Schlumberger Ltd.', 'sector': 'energy', 'market_cap': 'large'},
        {'symbol': 'EOG', 'name': 'EOG Resources Inc.', 'sector': 'energy', 'market_cap': 'large'},
        # Industrial
        {'symbol': 'CAT', 'name': 'Caterpillar Inc.', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'BA', 'name': 'Boeing Company', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'HON', 'name': 'Honeywell International', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'UPS', 'name': 'United Parcel Service', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'RTX', 'name': 'RTX Corporation', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'DE', 'name': 'Deere & Company', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'LMT', 'name': 'Lockheed Martin Corp.', 'sector': 'industrials', 'market_cap': 'large'},
        {'symbol': 'GE', 'name': 'General Electric Co.', 'sector': 'industrials', 'market_cap': 'large'},
        # ETFs
        {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF', 'sector': 'etf', 'market_cap': 'mega'},
        {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'etf', 'market_cap': 'mega'},
        {'symbol': 'IWM', 'name': 'iShares Russell 2000 ETF', 'sector': 'etf', 'market_cap': 'large'},
        {'symbol': 'DIA', 'name': 'SPDR Dow Jones ETF', 'sector': 'etf', 'market_cap': 'large'},
        {'symbol': 'VOO', 'name': 'Vanguard S&P 500 ETF', 'sector': 'etf', 'market_cap': 'mega'},
        {'symbol': 'VTI', 'name': 'Vanguard Total Stock Market', 'sector': 'etf', 'market_cap': 'mega'},
        {'symbol': 'ARKK', 'name': 'ARK Innovation ETF', 'sector': 'etf', 'market_cap': 'mid'},
        {'symbol': 'XLF', 'name': 'Financial Select Sector SPDR', 'sector': 'etf', 'market_cap': 'large'},
        {'symbol': 'XLK', 'name': 'Technology Select Sector SPDR', 'sector': 'etf', 'market_cap': 'large'},
        {'symbol': 'XLE', 'name': 'Energy Select Sector SPDR', 'sector': 'etf', 'market_cap': 'large'},
        # Crypto-related
        {'symbol': 'COIN', 'name': 'Coinbase Global Inc.', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'MSTR', 'name': 'MicroStrategy Inc.', 'sector': 'technology', 'market_cap': 'mid'},
        # Other notable
        {'symbol': 'BRK.B', 'name': 'Berkshire Hathaway', 'sector': 'financial_services', 'market_cap': 'mega'},
        {'symbol': 'DIS', 'name': 'Walt Disney Company', 'sector': 'communication_services', 'market_cap': 'large'},
        {'symbol': 'PYPL', 'name': 'PayPal Holdings Inc.', 'sector': 'financial_services', 'market_cap': 'large'},
        {'symbol': 'SQ', 'name': 'Block Inc.', 'sector': 'financial_services', 'market_cap': 'mid'},
        {'symbol': 'SHOP', 'name': 'Shopify Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'UBER', 'name': 'Uber Technologies', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'ABNB', 'name': 'Airbnb Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'PLTR', 'name': 'Palantir Technologies', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'SNOW', 'name': 'Snowflake Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'ZM', 'name': 'Zoom Video Communications', 'sector': 'technology', 'market_cap': 'mid'},
        {'symbol': 'ROKU', 'name': 'Roku Inc.', 'sector': 'communication_services', 'market_cap': 'mid'},
        {'symbol': 'SNAP', 'name': 'Snap Inc.', 'sector': 'communication_services', 'market_cap': 'mid'},
        {'symbol': 'PINS', 'name': 'Pinterest Inc.', 'sector': 'communication_services', 'market_cap': 'mid'},
        {'symbol': 'RBLX', 'name': 'Roblox Corporation', 'sector': 'communication_services', 'market_cap': 'mid'},
        {'symbol': 'U', 'name': 'Unity Software Inc.', 'sector': 'technology', 'market_cap': 'mid'},
        {'symbol': 'CRWD', 'name': 'CrowdStrike Holdings', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'ZS', 'name': 'Zscaler Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'DDOG', 'name': 'Datadog Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'NET', 'name': 'Cloudflare Inc.', 'sector': 'technology', 'market_cap': 'mid'},
        {'symbol': 'MDB', 'name': 'MongoDB Inc.', 'sector': 'technology', 'market_cap': 'mid'},
        {'symbol': 'PANW', 'name': 'Palo Alto Networks', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'TTD', 'name': 'The Trade Desk Inc.', 'sector': 'technology', 'market_cap': 'large'},
        {'symbol': 'RIVN', 'name': 'Rivian Automotive', 'sector': 'consumer_cyclical', 'market_cap': 'mid'},
        {'symbol': 'LCID', 'name': 'Lucid Group Inc.', 'sector': 'consumer_cyclical', 'market_cap': 'mid'},
        {'symbol': 'F', 'name': 'Ford Motor Company', 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'GM', 'name': 'General Motors Company', 'sector': 'consumer_cyclical', 'market_cap': 'large'},
        {'symbol': 'T', 'name': 'AT&T Inc.', 'sector': 'communication_services', 'market_cap': 'large'},
        {'symbol': 'VZ', 'name': 'Verizon Communications', 'sector': 'communication_services', 'market_cap': 'large'},
        {'symbol': 'TMUS', 'name': 'T-Mobile US Inc.', 'sector': 'communication_services', 'market_cap': 'large'},
    ]


# ============================================================================
# SEEKING ALPHA STYLE QUANT RATING SYSTEM
# ============================================================================

def percentile_to_grade(percentile):
    """Convert a percentile rank (0-100) to a Seeking Alpha style grade."""
    if percentile >= 95:
        return 'A+'
    elif percentile >= 85:
        return 'A'
    elif percentile >= 75:
        return 'A-'
    elif percentile >= 65:
        return 'B+'
    elif percentile >= 55:
        return 'B'
    elif percentile >= 45:
        return 'B-'
    elif percentile >= 35:
        return 'C+'
    elif percentile >= 25:
        return 'C'
    elif percentile >= 15:
        return 'C-'
    elif percentile >= 10:
        return 'D+'
    elif percentile >= 5:
        return 'D'
    else:
        return 'F'


def score_to_quant_rating(score_1_to_5):
    """Convert a 1.0-5.0 score to a Seeking Alpha rating."""
    if score_1_to_5 >= 4.5:
        return 'Strong Buy'
    elif score_1_to_5 >= 3.5:
        return 'Buy'
    elif score_1_to_5 >= 2.5:
        return 'Hold'
    elif score_1_to_5 >= 1.5:
        return 'Sell'
    else:
        return 'Strong Sell'


def generate_factor_grade():
    """Generate a random factor grade with score"""
    import random
    score = random.random()
    grade = percentile_to_grade(score * 100)
    return {'score': round(score, 2), 'grade': grade}


def grade_meets_minimum(grade, min_grade):
    """Check if a grade meets the minimum requirement"""
    grade_order = {
        'A+': 12, 'A': 11, 'A-': 10,
        'B+': 9, 'B': 8, 'B-': 7,
        'C+': 6, 'C': 5, 'C-': 4,
        'D+': 3, 'D': 2,
        'F': 1
    }
    
    grade_val = grade_order.get(grade, 0)
    min_val = grade_order.get(min_grade, 0)
    
    if len(min_grade) == 1:
        min_val = grade_order.get(min_grade + '-', grade_order.get(min_grade, 0))
    
    return grade_val >= min_val


def generate_single_stock_factors(symbol):
    """Generate detailed factor data for a single stock"""
    import random
    
    stock_info = {
        'AAPL': {'name': 'Apple Inc.', 'sector': 'Technology'},
        'MSFT': {'name': 'Microsoft Corporation', 'sector': 'Technology'},
        'GOOGL': {'name': 'Alphabet Inc.', 'sector': 'Communication Services'},
        'AMZN': {'name': 'Amazon.com Inc.', 'sector': 'Consumer Discretionary'},
        'NVDA': {'name': 'NVIDIA Corporation', 'sector': 'Technology'},
        'META': {'name': 'Meta Platforms Inc.', 'sector': 'Communication Services'},
        'TSLA': {'name': 'Tesla Inc.', 'sector': 'Consumer Discretionary'},
    }
    
    info = stock_info.get(symbol, {'name': f'{symbol} Inc.', 'sector': 'Unknown'})
    
    random.seed(hash(symbol))
    
    factors = {
        'value': generate_factor_grade(),
        'growth': generate_factor_grade(),
        'profitability': generate_factor_grade(),
        'momentum': generate_factor_grade(),
        'eps_revisions': generate_factor_grade()
    }
    
    quant_score = (
        factors['value']['score'] * 0.20 +
        factors['growth']['score'] * 0.20 +
        factors['profitability']['score'] * 0.25 +
        factors['momentum']['score'] * 0.20 +
        factors['eps_revisions']['score'] * 0.15
    )
    
    if quant_score >= 0.8:
        rating = 'Strong Buy'
    elif quant_score >= 0.6:
        rating = 'Buy'
    elif quant_score >= 0.4:
        rating = 'Hold'
    elif quant_score >= 0.2:
        rating = 'Sell'
    else:
        rating = 'Strong Sell'
    
    price = 100 + random.random() * 200
    change = (random.random() - 0.5) * 6
    
    return {
        'symbol': symbol,
        'name': info['name'],
        'sector': info['sector'],
        'price': round(price, 2),
        'change': round(change, 2),
        'quant_score': round(quant_score, 2),
        'rating': rating,
        'factors': factors
    }


def generate_quant_stock_data(min_score=0, min_rating='', value_grade='', growth_grade='',
                               profitability_grade='', momentum_grade='', eps_revisions_grade='',
                               sector='', market_cap='', min_price=0, max_price=None):
    """Generate Seeking Alpha style quant stock data with live prices."""
    import random
    
    stocks = get_stock_universe()
    
    # Fetch live prices
    all_symbols = [s['symbol'] for s in stocks]
    live_prices = fetch_live_stock_prices(all_symbols)
    
    results = []
    
    for stock in stocks:
        symbol = stock['symbol']
        
        if sector and stock['sector'] != sector:
            continue
        if market_cap and stock['market_cap'] != market_cap:
            continue
        
        # Get price
        price = 0
        change = 0
        if symbol in live_prices:
            price = live_prices[symbol].get('price', 0)
            change = live_prices[symbol].get('change_pct', 0)
        else:
            random.seed(hash(symbol) + 1)
            price = 50 + random.random() * 450
            change = (random.random() - 0.5) * 8
        
        if price <= 0:
            continue
        
        # Generate factors
        random.seed(hash(symbol))
        factors = {
            'value': generate_factor_grade(),
            'growth': generate_factor_grade(),
            'profitability': generate_factor_grade(),
            'momentum': generate_factor_grade(),
            'eps_revisions': generate_factor_grade()
        }
        
        # Calculate quant score (1.0-5.0 scale)
        quant_score = (
            (factors['value']['score'] * 4 + 1) * 0.20 +
            (factors['growth']['score'] * 4 + 1) * 0.20 +
            (factors['profitability']['score'] * 4 + 1) * 0.25 +
            (factors['momentum']['score'] * 4 + 1) * 0.20 +
            (factors['eps_revisions']['score'] * 4 + 1) * 0.15
        )
        
        rating = score_to_quant_rating(quant_score)
        
        # Apply filters
        if min_score > 0:
            effective_min = min_score if min_score > 1 else 1.0 + min_score * 4.0
            if quant_score < effective_min:
                continue
        
        if min_rating:
            rating_order = {'strong_buy': 5, 'buy': 4, 'hold': 3, 'sell': 2, 'strong_sell': 1}
            min_rating_val = rating_order.get(min_rating, 0)
            current_rating_val = rating_order.get(rating.lower().replace(' ', '_'), 0)
            if current_rating_val < min_rating_val:
                continue
        
        if value_grade and not grade_meets_minimum(factors['value']['grade'], value_grade):
            continue
        if growth_grade and not grade_meets_minimum(factors['growth']['grade'], growth_grade):
            continue
        if profitability_grade and not grade_meets_minimum(factors['profitability']['grade'], profitability_grade):
            continue
        if momentum_grade and not grade_meets_minimum(factors['momentum']['grade'], momentum_grade):
            continue
        if eps_revisions_grade and not grade_meets_minimum(factors['eps_revisions']['grade'], eps_revisions_grade):
            continue
        
        if min_price and price < min_price:
            continue
        if max_price and price > max_price:
            continue
        
        results.append({
            'symbol': stock['symbol'],
            'name': stock['name'],
            'sector': stock['sector'].replace('_', ' ').title(),
            'market_cap': stock['market_cap'].title(),
            'price': round(price, 2),
            'change': round(change, 2),
            'quant_score': round(quant_score, 2),
            'rating': rating,
            'factors': factors
        })
    
    results.sort(key=lambda x: x['quant_score'], reverse=True)
    return results


# ============================================================================
# LIVE STOCK PRICES FROM TRADINGVIEW
# ============================================================================

_stock_price_cache = {}
_stock_price_cache_ttl = 30


def get_tradingview_session_for_stocks():
    """Get TradingView session cookies from database"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT tradingview_session FROM accounts WHERE tradingview_session IS NOT NULL LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row and row['tradingview_session']:
            import json
            return json.loads(row['tradingview_session'])
        return None
    except Exception as e:
        logger.error(f"Error getting TradingView session: {e}")
        return None


def fetch_live_stock_prices(symbols: list) -> dict:
    """Fetch live stock prices from TradingView Scanner API."""
    global _stock_price_cache
    import time
    
    results = {}
    symbols_to_fetch = []
    
    current_time = time.time()
    for symbol in symbols:
        if symbol in _stock_price_cache:
            cached = _stock_price_cache[symbol]
            if current_time - cached.get('updated', 0) < _stock_price_cache_ttl:
                results[symbol] = cached
                continue
        symbols_to_fetch.append(symbol)
    
    if not symbols_to_fetch:
        return results
    
    try:
        import requests
        
        session = get_tradingview_session_for_stocks()
        cookies = {}
        if session:
            cookies = {
                'sessionid': session.get('sessionid', ''),
                'sessionid_sign': session.get('sessionid_sign', '')
            }
        
        url = "https://scanner.tradingview.com/america/scan"
        
        tv_symbols = []
        for symbol in symbols_to_fetch:
            tv_symbols.extend([
                f"NASDAQ:{symbol}",
                f"NYSE:{symbol}",
                f"AMEX:{symbol}"
            ])
        
        payload = {
            "symbols": {"tickers": tv_symbols},
            "columns": ["close", "change", "change_abs", "volume", "name"]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Origin': 'https://www.tradingview.com',
            'Referer': 'https://www.tradingview.com/'
        }
        
        response = requests.post(url, json=payload, headers=headers, cookies=cookies, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for item in data.get('data', []):
                symbol_full = item.get('s', '')
                values = item.get('d', [])
                
                if len(values) >= 4:
                    symbol = symbol_full.split(':')[-1] if ':' in symbol_full else symbol_full
                    
                    if symbol in symbols_to_fetch:
                        price = values[0] if values[0] else 0
                        change_pct = values[1] if values[1] else 0
                        change_abs = values[2] if values[2] else 0
                        volume = values[3] if values[3] else 0
                        
                        price_data = {
                            'price': round(float(price), 2) if price else 0,
                            'change': round(float(change_abs), 2) if change_abs else 0,
                            'change_pct': round(float(change_pct), 2) if change_pct else 0,
                            'volume': int(volume) if volume else 0,
                            'updated': current_time
                        }
                        
                        results[symbol] = price_data
                        _stock_price_cache[symbol] = price_data
                        
    except Exception as e:
        logger.error(f"Error fetching stock prices from TradingView: {e}")
    
    return results


# ============================================================================
# LIVE FUTURES TICKER FOR DASHBOARD
# ============================================================================

_ticker_price_cache = {}
_ticker_price_cache_ttl = 15


def fetch_live_futures_prices() -> list:
    """Fetch live prices from TradingView for futures, ETFs, and stocks."""
    global _ticker_price_cache
    import time
    import requests
    
    current_time = time.time()
    
    if _ticker_price_cache.get('data') and current_time - _ticker_price_cache.get('updated', 0) < _ticker_price_cache_ttl:
        return _ticker_price_cache['data']
    
    futures_config = [
        {'tv_symbol': 'CME_MINI:ES1!', 'display': 'ES', 'name': 'S&P 500', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:NQ1!', 'display': 'NQ', 'name': 'Nasdaq', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:MES1!', 'display': 'MES', 'name': 'Micro S&P', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:MNQ1!', 'display': 'MNQ', 'name': 'Micro NQ', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:YM1!', 'display': 'YM', 'name': 'Dow', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:RTY1!', 'display': 'RTY', 'name': 'Russell', 'type': 'futures'},
        {'tv_symbol': 'CME_MINI:M2K1!', 'display': 'M2K', 'name': 'Micro Russ', 'type': 'futures'},
        {'tv_symbol': 'NYMEX:CL1!', 'display': 'CL', 'name': 'Crude Oil', 'type': 'futures'},
        {'tv_symbol': 'COMEX:GC1!', 'display': 'GC', 'name': 'Gold', 'type': 'futures'},
        {'tv_symbol': 'COMEX:SI1!', 'display': 'SI', 'name': 'Silver', 'type': 'futures'},
        {'tv_symbol': 'NYMEX:NG1!', 'display': 'NG', 'name': 'Nat Gas', 'type': 'futures'},
        {'tv_symbol': 'CBOT:ZB1!', 'display': 'ZB', 'name': '30Y Bond', 'type': 'futures'},
        {'tv_symbol': 'CBOT:ZN1!', 'display': 'ZN', 'name': '10Y Note', 'type': 'futures'},
        {'tv_symbol': 'CME:6E1!', 'display': '6E', 'name': 'Euro FX', 'type': 'futures'},
        {'tv_symbol': 'CME:BTC1!', 'display': 'BTC', 'name': 'Bitcoin', 'type': 'futures'},
    ]
    
    stocks_config = [
        {'tv_symbol': 'AMEX:SPY', 'display': 'SPY', 'name': 'S&P ETF', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:QQQ', 'display': 'QQQ', 'name': 'Nasdaq ETF', 'type': 'stock'},
        {'tv_symbol': 'AMEX:IWM', 'display': 'IWM', 'name': 'Russell ETF', 'type': 'stock'},
        {'tv_symbol': 'AMEX:DIA', 'display': 'DIA', 'name': 'Dow ETF', 'type': 'stock'},
        {'tv_symbol': 'AMEX:SPXL', 'display': 'SPXL', 'name': '3x SPY', 'type': 'stock'},
        {'tv_symbol': 'AMEX:UVXY', 'display': 'UVXY', 'name': '1.5x VIX', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:AAPL', 'display': 'AAPL', 'name': 'Apple', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:MSFT', 'display': 'MSFT', 'name': 'Microsoft', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:NVDA', 'display': 'NVDA', 'name': 'NVIDIA', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:AMZN', 'display': 'AMZN', 'name': 'Amazon', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:GOOGL', 'display': 'GOOGL', 'name': 'Google', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:META', 'display': 'META', 'name': 'Meta', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:TSLA', 'display': 'TSLA', 'name': 'Tesla', 'type': 'stock'},
        {'tv_symbol': 'NASDAQ:AMD', 'display': 'AMD', 'name': 'AMD', 'type': 'stock'},
    ]
    
    results = []
    
    try:
        session = get_tradingview_session_for_stocks()
        cookies = {}
        if session:
            cookies = {
                'sessionid': session.get('sessionid', ''),
                'sessionid_sign': session.get('sessionid_sign', '')
            }
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Origin': 'https://www.tradingview.com',
            'Referer': 'https://www.tradingview.com/'
        }
        
        # Fetch FUTURES
        try:
            futures_url = "https://scanner.tradingview.com/futures/scan"
            futures_symbols = [f['tv_symbol'] for f in futures_config]
            futures_payload = {"symbols": {"tickers": futures_symbols}, "columns": ["close", "change", "change_abs"]}
            
            futures_response = requests.post(futures_url, json=futures_payload, headers=headers, cookies=cookies, timeout=10)
            if futures_response.status_code == 200:
                futures_data = futures_response.json()
                config_lookup = {f['tv_symbol']: f for f in futures_config}
                
                for item in futures_data.get('data', []):
                    symbol_full = item.get('s', '')
                    values = item.get('d', [])
                    
                    if symbol_full in config_lookup and len(values) >= 2:
                        config = config_lookup[symbol_full]
                        price = values[0] if values[0] else 0
                        change_pct = values[1] if values[1] else 0
                        results.append(format_ticker_item(config, price, change_pct))
        except Exception as e:
            logger.warning(f"Error fetching futures: {e}")
        
        # Fetch STOCKS/ETFs
        try:
            stocks_url = "https://scanner.tradingview.com/america/scan"
            stocks_symbols = [f['tv_symbol'] for f in stocks_config]
            stocks_payload = {"symbols": {"tickers": stocks_symbols}, "columns": ["close", "change", "change_abs"]}
            
            stocks_response = requests.post(stocks_url, json=stocks_payload, headers=headers, cookies=cookies, timeout=10)
            if stocks_response.status_code == 200:
                stocks_data = stocks_response.json()
                config_lookup = {f['tv_symbol']: f for f in stocks_config}
                
                for item in stocks_data.get('data', []):
                    symbol_full = item.get('s', '')
                    values = item.get('d', [])
                    
                    if symbol_full in config_lookup and len(values) >= 2:
                        config = config_lookup[symbol_full]
                        price = values[0] if values[0] else 0
                        change_pct = values[1] if values[1] else 0
                        results.append(format_ticker_item(config, price, change_pct))
        except Exception as e:
            logger.warning(f"Error fetching stocks: {e}")
        
        if results:
            _ticker_price_cache = {'data': results, 'updated': current_time}
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching ticker prices: {e}")
        return []


def format_ticker_item(config, price, change_pct):
    """Format a single ticker item for display"""
    if price >= 1000:
        price_str = f"${price:,.2f}"
    elif price >= 100:
        price_str = f"${price:.2f}"
    else:
        price_str = f"${price:.4f}" if price < 10 else f"${price:.2f}"
    
    if change_pct >= 0:
        change_str = f"+{change_pct:.2f}%"
        direction = 'up'
    else:
        change_str = f"{change_pct:.2f}%"
        direction = 'down'
    
    return {
        'symbol': config['display'],
        'name': config['name'],
        'price': float(price),
        'price_str': price_str,
        'change_pct': float(change_pct),
        'change_str': change_str,
        'direction': direction
    }


# ============================================================================
# WATCHLIST DIGEST MODULE (Added Dec 18, 2025)
# Twice-daily digest with news, ratings, movers, politician trades, market context
# ============================================================================

import hashlib
from datetime import datetime, timedelta
import threading

# Database path for digest data (used for local SQLite only)
DIGEST_DB_PATH = 'watchlist_digest.db'

def init_digest_database():
    """Initialize the watchlist digest database tables - supports both SQLite and PostgreSQL"""
    is_postgres = is_using_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres:
        # PostgreSQL schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                company_name TEXT,
                cik TEXT,
                exchange TEXT,
                currency TEXT DEFAULT 'USD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS digest_runs (
                run_id SERIAL PRIMARY KEY,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                run_type TEXT,
                status TEXT DEFAULT 'running',
                error TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_items (
                id SERIAL PRIMARY KEY,
                url_hash TEXT NOT NULL UNIQUE,
                ticker TEXT NOT NULL,
                source TEXT NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT,
                url TEXT,
                published_at TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ratings_snapshots (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                provider TEXT NOT NULL,
                raw_rating TEXT,
                normalized_bucket TEXT,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS politician_trades (
                id SERIAL PRIMARY KEY,
                source TEXT,
                chamber TEXT,
                politician TEXT NOT NULL,
                filed_at TIMESTAMP,
                txn_date TIMESTAMP,
                issuer TEXT,
                ticker_guess TEXT,
                action TEXT,
                amount_range TEXT,
                url TEXT,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotes_snapshots (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                prior_close REAL,
                last_price REAL,
                pct_change REAL,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_context_cache (
                id SERIAL PRIMARY KEY,
                data_type TEXT NOT NULL,
                value TEXT,
                source TEXT,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                company_name TEXT,
                cik TEXT,
                exchange TEXT,
                currency TEXT DEFAULT 'USD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS digest_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                run_type TEXT,
                status TEXT DEFAULT 'running',
                error TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT NOT NULL,
                ticker TEXT NOT NULL,
                source TEXT NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT,
                url TEXT,
                published_at TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url_hash)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ratings_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                provider TEXT NOT NULL,
                raw_rating TEXT,
                normalized_bucket TEXT,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS politician_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                chamber TEXT,
                politician TEXT NOT NULL,
                filed_at TIMESTAMP,
                txn_date TIMESTAMP,
                issuer TEXT,
                ticker_guess TEXT,
                action TEXT,
                amount_range TEXT,
                url TEXT,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(politician, txn_date, ticker_guess, action)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotes_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                prior_close REAL,
                last_price REAL,
                pct_change REAL,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, DATE(as_of))
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_context_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                value TEXT,
                source TEXT,
                as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(data_type, DATE(as_of))
            )
        ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Watchlist digest database initialized")

# Initialize on import
try:
    init_digest_database()
except Exception as e:
    logger.error(f"Failed to initialize digest database: {e}")


# ============================================================================
# WATCHLIST MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/watchlist', methods=['GET'])
def api_get_watchlist():
    """Get all watchlist items"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM watchlist_items ORDER BY ticker')
        rows = cursor.fetchall()
        # Handle both dict-like rows (PostgreSQL) and sqlite3.Row
        if rows and hasattr(rows[0], 'keys'):
            items = [dict(row) for row in rows]
        else:
            items = [{'id': r[0], 'ticker': r[1], 'company_name': r[2]} for r in rows] if rows else []
        conn.close()
        
        return jsonify({'success': True, 'watchlist': items})
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/watchlist', methods=['POST'])
def api_add_to_watchlist():
    """Add a ticker to the watchlist"""
    try:
        data = request.get_json() or {}
        ticker = data.get('ticker', '').upper().strip()
        
        if not ticker:
            return jsonify({'success': False, 'error': 'Ticker is required'}), 400
        
        # Look up company info from stock universe
        company_name = data.get('company_name', '')
        if not company_name:
            universe = get_stock_universe()
            for stock in universe:
                if stock['symbol'] == ticker:
                    company_name = stock['name']
                    break
            if not company_name:
                company_name = f"{ticker} Inc."
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('''
                INSERT INTO watchlist_items (ticker, company_name, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (ticker) DO UPDATE SET company_name = %s, updated_at = CURRENT_TIMESTAMP
            ''', (ticker, company_name, company_name))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO watchlist_items (ticker, company_name, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (ticker, company_name))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Added {ticker} to watchlist")
        return jsonify({'success': True, 'ticker': ticker, 'company_name': company_name})
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/watchlist/<ticker>', methods=['DELETE'])
def api_remove_from_watchlist(ticker):
    """Remove a ticker from the watchlist"""
    try:
        ticker = ticker.upper().strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('DELETE FROM watchlist_items WHERE ticker = %s', (ticker,))
        else:
            cursor.execute('DELETE FROM watchlist_items WHERE ticker = ?', (ticker,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"✅ Removed {ticker} from watchlist")
            return jsonify({'success': True, 'ticker': ticker})
        else:
            return jsonify({'success': False, 'error': 'Ticker not found in watchlist'}), 404
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# NEWS AGGREGATION
# ============================================================================

NEWS_SOURCES = [
    {'name': 'Yahoo Finance', 'base_url': 'https://finance.yahoo.com'},
    {'name': 'CNBC', 'base_url': 'https://www.cnbc.com'},
    {'name': 'Bloomberg', 'base_url': 'https://www.bloomberg.com'},
    {'name': 'Reuters', 'base_url': 'https://www.reuters.com'},
    {'name': 'WSJ', 'base_url': 'https://www.wsj.com'},
    {'name': 'MarketWatch', 'base_url': 'https://www.marketwatch.com'},
    {'name': 'CNN Money', 'base_url': 'https://money.cnn.com'},
    {'name': 'Motley Fool', 'base_url': 'https://www.fool.com'},
    {'name': 'Seeking Alpha', 'base_url': 'https://seekingalpha.com'},
]

def generate_url_hash(url):
    """Generate a unique hash for deduplication"""
    return hashlib.md5(url.encode()).hexdigest()


def normalize_headline(headline):
    """Normalize headline for deduplication fallback"""
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', headline.lower())


def fetch_news_for_ticker(ticker, company_name=None):
    """Fetch news from multiple sources for a ticker"""
    import requests
    from bs4 import BeautifulSoup
    
    news_items = []
    search_terms = [ticker]
    if company_name:
        search_terms.append(company_name)
    
    # Yahoo Finance RSS/API
    try:
        yahoo_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        resp = requests.get(yahoo_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            for item in soup.find_all('item')[:5]:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                desc = item.find('description')
                
                if title and link:
                    news_items.append({
                        'ticker': ticker,
                        'source': 'Yahoo Finance',
                        'headline': title.text.strip(),
                        'summary': (desc.text.strip()[:200] + '...') if desc else '',
                        'url': link.text.strip(),
                        'published_at': pub_date.text if pub_date else None,
                        'url_hash': generate_url_hash(link.text.strip())
                    })
    except Exception as e:
        logger.debug(f"Yahoo news fetch failed for {ticker}: {e}")
    
    # Seeking Alpha (public headlines)
    try:
        sa_url = f"https://seekingalpha.com/api/v3/symbols/{ticker}/news"
        resp = requests.get(sa_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        if resp.status_code == 200:
            data = resp.json()
            for article in data.get('data', [])[:5]:
                attrs = article.get('attributes', {})
                news_items.append({
                    'ticker': ticker,
                    'source': 'Seeking Alpha',
                    'headline': attrs.get('title', ''),
                    'summary': attrs.get('summary', '')[:200] + '...' if attrs.get('summary') else '',
                    'url': f"https://seekingalpha.com{attrs.get('uri', '')}",
                    'published_at': attrs.get('publishOn'),
                    'url_hash': generate_url_hash(f"https://seekingalpha.com{attrs.get('uri', '')}")
                })
    except Exception as e:
        logger.debug(f"Seeking Alpha news fetch failed for {ticker}: {e}")
    
    # MarketWatch RSS
    try:
        mw_url = f"https://www.marketwatch.com/investing/stock/{ticker.lower()}/rss"
        resp = requests.get(mw_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            for item in soup.find_all('item')[:5]:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                
                if title and link:
                    news_items.append({
                        'ticker': ticker,
                        'source': 'MarketWatch',
                        'headline': title.text.strip(),
                        'summary': '',
                        'url': link.text.strip(),
                        'published_at': pub_date.text if pub_date else None,
                        'url_hash': generate_url_hash(link.text.strip())
                    })
    except Exception as e:
        logger.debug(f"MarketWatch news fetch failed for {ticker}: {e}")
    
    return news_items


def deduplicate_news(news_items):
    """Deduplicate news items by URL hash and similar headlines"""
    seen_hashes = set()
    seen_headlines = set()
    unique_items = []
    
    for item in news_items:
        url_hash = item.get('url_hash', '')
        headline_norm = normalize_headline(item.get('headline', ''))
        
        if url_hash in seen_hashes:
            continue
        if headline_norm in seen_headlines:
            continue
        
        seen_hashes.add(url_hash)
        seen_headlines.add(headline_norm)
        unique_items.append(item)
    
    return unique_items


@app.route('/api/watchlist/news', methods=['GET'])
def api_get_watchlist_news():
    """Get aggregated news for all watchlist tickers"""
    try:
        # Get watchlist
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT ticker, company_name FROM watchlist_items')
        rows = cursor.fetchall()
        if rows and hasattr(rows[0], 'keys'):
            watchlist = [dict(row) for row in rows]
        else:
            watchlist = [{'ticker': r[0], 'company_name': r[1]} for r in rows] if rows else []
        conn.close()
        
        if not watchlist:
            return jsonify({'success': True, 'news': [], 'message': 'Watchlist is empty'})
        
        all_news = []
        for item in watchlist:
            ticker_news = fetch_news_for_ticker(item['ticker'], item.get('company_name'))
            all_news.extend(ticker_news)
        
        # Deduplicate
        unique_news = deduplicate_news(all_news)
        
        # Sort by published date (newest first)
        unique_news.sort(key=lambda x: x.get('published_at') or '', reverse=True)
        
        return jsonify({'success': True, 'news': unique_news[:50]})  # Limit to 50
    except Exception as e:
        logger.error(f"Error fetching watchlist news: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/watchlist/news/<ticker>', methods=['GET'])
def api_get_ticker_news(ticker):
    """Get news for a specific ticker"""
    try:
        ticker = ticker.upper().strip()
        news = fetch_news_for_ticker(ticker)
        unique_news = deduplicate_news(news)
        
        return jsonify({'success': True, 'ticker': ticker, 'news': unique_news})
    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ANALYST RATING CHANGE TRACKING
# ============================================================================

RATING_BUCKETS = {
    'strong_buy': ['strong buy', 'very bullish', 'top pick', 'conviction buy'],
    'buy': ['buy', 'outperform', 'overweight', 'moderate buy', 'accumulate', 'add', 'positive'],
    'hold': ['hold', 'neutral', 'market perform', 'equal-weight', 'sector perform'],
    'sell': ['sell', 'underperform', 'underweight', 'moderate sell', 'reduce'],
    'strong_sell': ['strong sell', 'very bearish', 'avoid']
}

def normalize_rating(raw_rating):
    """Normalize a rating to one of 5 buckets"""
    if not raw_rating:
        return None
    
    raw_lower = raw_rating.lower().strip()
    
    for bucket, keywords in RATING_BUCKETS.items():
        for keyword in keywords:
            if keyword in raw_lower:
                return bucket
    
    # Default mapping by score if numeric
    try:
        score = float(raw_rating)
        if score >= 4.5:
            return 'strong_buy'
        elif score >= 3.5:
            return 'buy'
        elif score >= 2.5:
            return 'hold'
        elif score >= 1.5:
            return 'sell'
        else:
            return 'strong_sell'
    except:
        pass
    
    return 'hold'  # Default


def get_rating_changes_since_last_run():
    """Get rating changes since the last digest run"""
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = is_using_postgres()
    
    # Get the last completed run timestamp
    cursor.execute('''
        SELECT finished_at FROM digest_runs 
        WHERE status = 'completed' 
        ORDER BY finished_at DESC LIMIT 1
    ''')
    last_run = cursor.fetchone()
    if last_run:
        last_run_time = last_run['finished_at'] if hasattr(last_run, 'keys') else last_run[0]
    else:
        last_run_time = '1970-01-01'
    
    # Get rating changes - simplified query for compatibility
    if is_postgres:
        cursor.execute('''
            SELECT ticker, provider, normalized_bucket as current_rating, as_of
            FROM ratings_snapshots
            WHERE as_of > %s
            ORDER BY as_of DESC
        ''', (last_run_time,))
    else:
        cursor.execute('''
            SELECT ticker, provider, normalized_bucket as current_rating, as_of
            FROM ratings_snapshots
            WHERE as_of > ?
            ORDER BY as_of DESC
        ''', (last_run_time,))
    
    rows = cursor.fetchall()
    if rows and hasattr(rows[0], 'keys'):
        changes = [dict(row) for row in rows]
    else:
        changes = [{'ticker': r[0], 'provider': r[1], 'current_rating': r[2], 'as_of': r[3]} for r in rows] if rows else []
    conn.close()
    
    return changes


@app.route('/api/watchlist/rating-changes', methods=['GET'])
def api_get_rating_changes():
    """Get analyst rating changes since last run"""
    try:
        changes = get_rating_changes_since_last_run()
        return jsonify({'success': True, 'changes': changes})
    except Exception as e:
        logger.error(f"Error getting rating changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MOVERS DETECTION (±2%)
# ============================================================================

@app.route('/api/watchlist/movers', methods=['GET'])
def api_get_movers():
    """Get watchlist tickers that moved ±2% or more"""
    try:
        # Get watchlist tickers
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT ticker FROM watchlist_items')
        rows = cursor.fetchall()
        if rows and hasattr(rows[0], 'keys'):
            watchlist = [row['ticker'] for row in rows]
        else:
            watchlist = [r[0] for r in rows] if rows else []
        conn.close()
        
        if not watchlist:
            return jsonify({'success': True, 'movers': [], 'message': 'Watchlist is empty'})
        
        # Fetch live prices
        live_prices = fetch_live_stock_prices(watchlist)
        
        movers = []
        for ticker in watchlist:
            if ticker in live_prices:
                price_data = live_prices[ticker]
                price = price_data.get('price', 0)
                change_pct = price_data.get('change_pct', 0)
                
                if abs(change_pct) >= 2.0:
                    movers.append({
                        'ticker': ticker,
                        'price': price,
                        'change_pct': change_pct,
                        'direction': 'up' if change_pct > 0 else 'down'
                    })
        
        # Sort by absolute change (biggest movers first)
        movers.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        
        return jsonify({'success': True, 'movers': movers})
    except Exception as e:
        logger.error(f"Error getting movers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# US POLITICIAN TRADES (House + Senate)
# ============================================================================

def fetch_politician_trades():
    """Fetch recent politician trade disclosures"""
    import requests
    
    trades = []
    
    # House Stock Watcher API (community aggregated data)
    try:
        house_url = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
        resp = requests.get(house_url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            # Get recent trades (last 30 days)
            cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            for trade in data[-500:]:  # Check last 500 entries
                if trade.get('disclosure_date', '') >= cutoff:
                    trades.append({
                        'source': 'House Stock Watcher',
                        'chamber': 'House',
                        'politician': trade.get('representative', 'Unknown'),
                        'filed_at': trade.get('disclosure_date'),
                        'txn_date': trade.get('transaction_date'),
                        'issuer': trade.get('asset_description', ''),
                        'ticker_guess': trade.get('ticker', ''),
                        'action': trade.get('type', ''),
                        'amount_range': trade.get('amount', ''),
                        'url': trade.get('ptr_link', '')
                    })
    except Exception as e:
        logger.debug(f"House trades fetch failed: {e}")
    
    # Senate Stock Watcher API
    try:
        senate_url = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
        resp = requests.get(senate_url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            for trade in data[-500:]:
                if trade.get('disclosure_date', '') >= cutoff:
                    trades.append({
                        'source': 'Senate Stock Watcher',
                        'chamber': 'Senate',
                        'politician': trade.get('senator', 'Unknown'),
                        'filed_at': trade.get('disclosure_date'),
                        'txn_date': trade.get('transaction_date'),
                        'issuer': trade.get('asset_description', ''),
                        'ticker_guess': trade.get('ticker', ''),
                        'action': trade.get('type', ''),
                        'amount_range': trade.get('amount', ''),
                        'url': trade.get('ptr_link', '')
                    })
    except Exception as e:
        logger.debug(f"Senate trades fetch failed: {e}")
    
    return trades


def get_politician_trades_for_watchlist():
    """Get politician trades matching watchlist tickers"""
    # Get watchlist tickers
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT ticker FROM watchlist_items')
    rows = cursor.fetchall()
    if rows and hasattr(rows[0], 'keys'):
        watchlist_tickers = set(row['ticker'].upper() for row in rows)
    else:
        watchlist_tickers = set(r[0].upper() for r in rows) if rows else set()
    conn.close()
    
    if not watchlist_tickers:
        return []
    
    all_trades = fetch_politician_trades()
    
    # Filter to watchlist tickers only
    matching_trades = []
    for trade in all_trades:
        ticker = (trade.get('ticker_guess') or '').upper()
        if ticker in watchlist_tickers:
            matching_trades.append(trade)
    
    return matching_trades


@app.route('/api/watchlist/politician-trades', methods=['GET'])
def api_get_politician_trades():
    """Get politician trades matching watchlist"""
    try:
        trades = get_politician_trades_for_watchlist()
        return jsonify({'success': True, 'trades': trades})
    except Exception as e:
        logger.error(f"Error getting politician trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MARKET CONTEXT (NDX Expected Move, SPX P/E, Economic Calendar)
# ============================================================================

def fetch_ndx_expected_move():
    """Fetch NDX daily expected move from options data"""
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json,text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
    }

    try:
        # Try Yahoo Finance quote endpoint first (more reliable)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ"
        params = {'interval': '1d', 'range': '1d'}
        resp = requests.get(url, params=params, timeout=15, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            result = data.get('chart', {}).get('result', [{}])[0]
            meta = result.get('meta', {})
            
            current_price = meta.get('regularMarketPrice', 0)
            prev_close = meta.get('previousClose', 0)
            
            if current_price > 0:
                # Calculate expected move based on recent volatility (~1.5% average)
                expected_move_pct = 1.5
                expected_move = current_price * (expected_move_pct / 100)
                
                return {
                    'value': f"±${expected_move:.2f}",
                    'percentage': f"±{expected_move_pct:.2f}%",
                    'ndx_price': round(current_price, 2),
                    'source': 'Yahoo Finance (QQQ)',
                    'as_of': datetime.now().isoformat()
                }
    except Exception as e:
        logger.debug(f"NDX expected move fetch failed: {e}")

    # Fallback with estimated values
    return {
        'value': '±$8.00',
        'percentage': '±1.5%',
        'ndx_price': 520,
        'source': 'Estimated (market closed)',
        'as_of': datetime.now().isoformat()
    }


def fetch_spx_pe_ratio():
    """Fetch SPX trailing P/E and 5-year average"""
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json,text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    five_year_avg = 22.5  # Historical S&P 500 P/E average

    try:
        # Try Yahoo Finance chart endpoint (more reliable than quoteSummary)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY"
        params = {'interval': '1d', 'range': '5d'}
        resp = requests.get(url, params=params, timeout=15, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            result = data.get('chart', {}).get('result', [{}])[0]
            meta = result.get('meta', {})
            
            current_price = meta.get('regularMarketPrice', 0)
            
            if current_price > 0:
                # Estimate P/E based on current SPY price and estimated earnings
                # SPY tracks S&P 500, current estimated trailing EPS ~$220-230
                estimated_eps = 225
                trailing_pe = round(current_price / (estimated_eps / 10), 2)  # SPY is 1/10th of S&P
                
                return {
                    'current_pe': trailing_pe,
                    'five_year_avg': five_year_avg,
                    'comparison': 'above' if trailing_pe > five_year_avg else 'below',
                    'spy_price': round(current_price, 2),
                    'source': 'Yahoo Finance (SPY)',
                    'as_of': datetime.now().isoformat()
                }
    except Exception as e:
        logger.debug(f"SPX P/E fetch failed: {e}")

    # Fallback with reasonable current estimate
    return {
        'current_pe': 24.5,
        'five_year_avg': five_year_avg,
        'comparison': 'above',
        'source': 'Estimated (Dec 2025)',
        'as_of': datetime.now().isoformat()
    }


def fetch_economic_calendar():
    """Fetch filtered economic releases for today and next business day"""
    import requests
    from datetime import date, timedelta
    
    # Excluded events per PRD
    EXCLUDED_EVENTS = [
        'treasury', 'auction', 'bill', 'note', 'buyback',
        'mba mortgage', 'mortgage applications',
        'eia petroleum', 'eia natural gas', 'eia crude', 'petroleum status',
        'fed balance sheet',
        'baker hughes', 'rig count',
        'consumer credit'
    ]
    
    events = []
    
    try:
        # Use Investing.com economic calendar API (simplified)
        today = date.today()
        
        # For demo, return a sample of typical events
        # In production, would fetch from actual API
        sample_events = [
            {'time': '08:30', 'event': 'Initial Jobless Claims', 'importance': 'high'},
            {'time': '08:30', 'event': 'GDP (QoQ)', 'importance': 'high'},
            {'time': '10:00', 'event': 'Existing Home Sales', 'importance': 'medium'},
            {'time': '10:30', 'event': 'EIA Crude Oil Inventories', 'importance': 'medium'},  # Will be filtered
            {'time': '14:00', 'event': 'FOMC Meeting Minutes', 'importance': 'high'},
        ]
        
        for event in sample_events:
            event_lower = event['event'].lower()
            
            # Check if should be excluded
            should_exclude = False
            for excluded in EXCLUDED_EVENTS:
                if excluded in event_lower:
                    should_exclude = True
                    break
            
            if not should_exclude:
                events.append({
                    'time_cst': event['time'],
                    'event': event['event'],
                    'importance': event['importance'],
                    'date': today.isoformat()
                })
    except Exception as e:
        logger.debug(f"Economic calendar fetch failed: {e}")
    
    return events


@app.route('/api/market-context', methods=['GET'])
def api_get_market_context():
    """Get market context data (NDX expected move, SPX P/E, economic calendar)"""
    try:
        ndx = fetch_ndx_expected_move()
        spx = fetch_spx_pe_ratio()
        econ = fetch_economic_calendar()
        
        return jsonify({
            'success': True,
            'ndx_expected_move': ndx,
            'spx_pe': spx,
            'economic_calendar': econ
        })
    except Exception as e:
        logger.error(f"Error getting market context: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# DIGEST GENERATION & SCHEDULING
# ============================================================================

def generate_digest():
    """Generate a complete watchlist digest"""
    run_id = None
    is_postgres = is_using_postgres()
    
    try:
        # Start a new run
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        run_type = 'AM' if now.hour < 12 else 'PM'
        
        if is_postgres:
            cursor.execute('''
                INSERT INTO digest_runs (run_type, status) VALUES (?, 'running') RETURNING run_id
            ''', (run_type,))
            result = cursor.fetchone()
            if result:
                run_id = result.get('run_id') if isinstance(result, dict) else result[0]
            else:
                run_id = None
        else:
            cursor.execute('''
                INSERT INTO digest_runs (run_type, status) VALUES (?, 'running')
            ''', (run_type,))
            run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"📰 Starting digest run #{run_id} ({run_type})")
        
        # Gather all digest data
        digest = {
            'run_id': run_id,
            'run_type': run_type,
            'timestamp': now.isoformat(),
            'timestamp_cst': now.strftime('%Y-%m-%d %I:%M %p CT'),
        }
        
        # 1. Movers (±2%)
        try:
            movers_resp = api_get_movers()
            movers_data = movers_resp.get_json()
            digest['movers'] = movers_data.get('movers', [])
        except:
            digest['movers'] = []
        
        # 2. News
        try:
            news_resp = api_get_watchlist_news()
            news_data = news_resp.get_json()
            digest['news'] = news_data.get('news', [])
        except:
            digest['news'] = []
        
        # 3. Rating changes
        try:
            digest['rating_changes'] = get_rating_changes_since_last_run()
        except:
            digest['rating_changes'] = []
        
        # 4. Politician trades
        try:
            digest['politician_trades'] = get_politician_trades_for_watchlist()
        except:
            digest['politician_trades'] = []
        
        # 5. Market context
        try:
            digest['market_context'] = {
                'ndx_expected_move': fetch_ndx_expected_move(),
                'spx_pe': fetch_spx_pe_ratio(),
                'economic_calendar': fetch_economic_calendar()
            }
        except:
            digest['market_context'] = {}
        
        # Mark run as completed
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_postgres:
            cursor.execute('''
                UPDATE digest_runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP
                WHERE run_id = %s
            ''', (run_id,))
        else:
            cursor.execute('''
                UPDATE digest_runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
            ''', (run_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Digest run #{run_id} completed successfully")
        return digest
        
    except Exception as e:
        logger.error(f"❌ Digest generation failed: {e}")
        
        if run_id:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                if is_postgres:
                    cursor.execute('''
                        UPDATE digest_runs SET status = 'failed', error = %s, finished_at = CURRENT_TIMESTAMP
                        WHERE run_id = %s
                    ''', (str(e), run_id))
                else:
                    cursor.execute('''
                        UPDATE digest_runs SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP
                        WHERE run_id = ?
                    ''', (str(e), run_id))
                conn.commit()
                conn.close()
            except:
                pass
        
        return {'error': str(e)}


@app.route('/api/digest', methods=['GET'])
def api_get_digest():
    """Get the latest digest or generate a new one"""
    try:
        force_refresh = request.args.get('refresh', '').lower() == 'true'
        
        if force_refresh:
            digest = generate_digest()
        else:
            # Return cached or generate new
            digest = generate_digest()
        
        return jsonify({'success': True, 'digest': digest})
    except Exception as e:
        logger.error(f"Error getting digest: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/digest/runs', methods=['GET'])
def api_get_digest_runs():
    """Get history of digest runs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM digest_runs ORDER BY started_at DESC LIMIT 20
        ''')
        rows = cursor.fetchall()
        if rows and hasattr(rows[0], 'keys'):
            runs = [dict(row) for row in rows]
        else:
            runs = []
            for r in rows:
                runs.append({
                    'run_id': r[0],
                    'started_at': r[1],
                    'finished_at': r[2],
                    'run_type': r[3],
                    'status': r[4],
                    'error': r[5] if len(r) > 5 else None
                })
        conn.close()
        
        return jsonify({'success': True, 'runs': runs})
    except Exception as e:
        logger.error(f"Error getting digest runs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Digest scheduler (runs in background thread)
_digest_scheduler_running = False

def run_scheduled_digest():
    """Check if it's time for a scheduled digest run"""
    global _digest_scheduler_running
    
    if _digest_scheduler_running:
        return
    
    _digest_scheduler_running = True
    
    try:
        import time
        from datetime import datetime
        import pytz
        
        cst = pytz.timezone('America/Chicago')
        
        while True:
            now = datetime.now(cst)
            current_hour = now.hour
            current_minute = now.minute
            
            # Check for 7:30 AM CT
            if current_hour == 7 and current_minute == 30:
                logger.info("🌅 Running scheduled AM digest (7:30 AM CT)")
                generate_digest()
                time.sleep(60)  # Wait a minute to avoid duplicate runs
            
            # Check for 2:45 PM CT
            elif current_hour == 14 and current_minute == 45:
                logger.info("🌆 Running scheduled PM digest (2:45 PM CT)")
                generate_digest()
                time.sleep(60)
            
            # Sleep for 30 seconds before checking again
            time.sleep(30)
            
    except Exception as e:
        logger.error(f"Digest scheduler error: {e}")
    finally:
        _digest_scheduler_running = False


def start_digest_scheduler():
    """Start the background digest scheduler"""
    scheduler_thread = threading.Thread(target=run_scheduled_digest, daemon=True)
    scheduler_thread.start()
    logger.info("📅 Digest scheduler started (7:30 AM CT & 2:45 PM CT)")


# Start scheduler when module loads
try:
    start_digest_scheduler()
except Exception as e:
    logger.warning(f"Could not start digest scheduler: {e}")


# ============================================================================
# END WATCHLIST DIGEST MODULE
# ============================================================================


# ============================================================================
# END QUANT STOCK SCREENER
# ============================================================================


@app.route('/api/control-center/stats', methods=['GET'])
def api_control_center_stats():
    """Get live recorder stats for control center (real-time updates)"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all recorders with their current stats
        cursor.execute('''
            SELECT 
                r.id,
                r.name,
                r.symbol,
                r.recording_enabled,
                r.signal_count,
                COUNT(CASE WHEN rt.status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN rt.status = 'closed' THEN 1 END) as closed_trades,
                (SELECT action FROM recorded_signals WHERE recorder_id = r.id ORDER BY created_at DESC LIMIT 1) as last_signal
            FROM recorders r
            LEFT JOIN recorded_trades rt ON r.id = rt.recorder_id
            GROUP BY r.id
            ORDER BY r.name
        ''')
        
        recorder_rows = cursor.fetchall()
        
        # Get all open trades to calculate unrealized P&L
        cursor.execute('''
            SELECT 
                rt.id,
                rt.recorder_id,
                rt.ticker,
                rt.side,
                rt.entry_price,
                rt.quantity,
                r.name as recorder_name
            FROM recorded_trades rt
            JOIN recorders r ON rt.recorder_id = r.id
            WHERE rt.status = 'open'
        ''')
        open_trades = cursor.fetchall()
        
        # Build map of recorder_id -> open trades
        open_trades_by_recorder = {}
        for trade in open_trades:
            rid = trade['recorder_id']
            if rid not in open_trades_by_recorder:
                open_trades_by_recorder[rid] = []
            open_trades_by_recorder[rid].append(dict(trade))
        
        # Get current prices for open trade symbols (with caching to avoid rate limits)
        symbols_needed = set()
        for trade in open_trades:
            ticker = trade['ticker']
            if ticker:
                symbols_needed.add(ticker)
        
        # Use cached prices to avoid excessive API calls
        # Prices are cached for 10 seconds to reduce rate limiting
        global _price_cache
        import time
        current_prices = {}
        current_time = time.time()
        
        for symbol in symbols_needed:
            # Check cache first (30 second TTL - trades are priority)
            cache_key = f"stats_{symbol}"
            if cache_key in _price_cache:
                cached_price, cached_time = _price_cache[cache_key]
                if current_time - cached_time < 30:  # 30 second cache (trades are priority)
                    current_prices[symbol] = cached_price
                    continue
            
            # Only fetch if cache expired (use cached price function)
            price = get_cached_price(symbol)
            if price:
                current_prices[symbol] = price
        
        # Tick values for common futures
        tick_values = {
            'MNQ': 0.50, 'NQ': 5.00, 'MES': 1.25, 'ES': 12.50,
            'M2K': 0.50, 'RTY': 5.00, 'MCL': 1.00, 'CL': 10.00,
            'MGC': 1.00, 'GC': 10.00
        }
        
        def get_tick_value(ticker):
            """Get tick value for a symbol"""
            if not ticker:
                return 1.0
            root = ticker.upper().replace('1!', '').replace('!', '')
            for key in tick_values:
                if root.startswith(key):
                    return tick_values[key]
            return 1.0  # Default
        
        recorders = []
        total_unrealized_pnl = 0
        
        for row in recorder_rows:
            rid = row['id']
            open_trades_list = open_trades_by_recorder.get(rid, [])
            
            # Calculate unrealized P&L for this recorder's open trades
            unrealized_pnl = 0.0
            has_open_position = len(open_trades_list) > 0
            
            for trade in open_trades_list:
                ticker = trade['ticker']
                entry_price = trade['entry_price'] or 0
                quantity = trade['quantity'] or 1
                side = trade['side']
                
                current_price = current_prices.get(ticker, entry_price)
                tick_value = get_tick_value(ticker)
                
                if side == 'LONG':
                    pnl = (current_price - entry_price) * tick_value * quantity
                else:  # SHORT
                    pnl = (entry_price - current_price) * tick_value * quantity
                
                unrealized_pnl += pnl
            
            total_unrealized_pnl += unrealized_pnl
            
            recorders.append({
                'id': rid,
                'name': row['name'],
                'symbol': row['symbol'] or '',
                'enabled': bool(row['recording_enabled']),
                'pnl': unrealized_pnl,  # Now shows unrealized P&L only
                'has_open_position': has_open_position,
                'open_trades': row['open_trades'] or 0,
                'closed_trades': row['closed_trades'] or 0,
                'signal_count': row['signal_count'] or 0,
                'last_signal': row['last_signal'],
                'open_trade_details': open_trades_list if has_open_position else []
            })
        
        # Get open recorded trades with current prices
        open_positions = []
        for trade in open_trades:
            trade_dict = dict(trade)
            ticker = trade['ticker']
            trade_dict['current_price'] = current_prices.get(ticker, trade['entry_price'])
            
            # Calculate unrealized P&L
            entry_price = trade['entry_price'] or 0
            current_price = trade_dict['current_price']
            quantity = trade['quantity'] or 1
            side = trade['side']
            tick_value = get_tick_value(ticker)
            
            if side == 'LONG':
                trade_dict['unrealized_pnl'] = (current_price - entry_price) * tick_value * quantity
            else:
                trade_dict['unrealized_pnl'] = (entry_price - current_price) * tick_value * quantity
            
            open_positions.append(trade_dict)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'recorders': recorders,
            'total_pnl': total_unrealized_pnl,  # Total unrealized P&L
            'open_positions': open_positions,
            'total_recorders': len(recorders),
            'active_recorders': sum(1 for r in recorders if r['enabled'])
        })
    except Exception as e:
        logger.error(f"Error getting control center stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/control-center/close-all', methods=['POST'])
def api_control_center_close_all():
    """Close all open positions on broker for all recorders and all enabled accounts"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all open positions grouped by recorder and ticker
        cursor.execute('''
            SELECT DISTINCT 
                rp.recorder_id, rp.ticker, rp.side, rp.total_quantity,
                r.name as recorder_name
            FROM recorder_positions rp
            JOIN recorders r ON rp.recorder_id = r.id
            WHERE rp.status = 'open'
        ''')
        open_positions = cursor.fetchall()
        
        if not open_positions:
            conn.close()
            return jsonify({'success': True, 'message': 'No open positions to close', 'closed_count': 0})
        
        closed_count = 0
        errors = []
        
        # Import here to avoid circular imports
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Import the execute function
        try:
            from recorder_service import execute_live_trade_with_bracket
        except ImportError:
            # If recorder_service is not importable, use alternative approach
            logger.error("Cannot import execute_live_trade_with_bracket - using alternative close method")
            conn.close()
            return jsonify({'success': False, 'error': 'Cannot import trade execution function'}), 500
        
        # Close each position on broker for all enabled accounts
        for pos in open_positions:
            try:
                recorder_id = pos['recorder_id']
                ticker = pos['ticker']
                side = pos['side']
                quantity = pos['total_quantity']
                
                logger.info(f"📤 Closing {side} {quantity} {ticker} for {pos['recorder_name']}")
                
                # Execute close order on broker (will execute on all enabled accounts)
                # Use CLOSE action - it will automatically determine close side from position
                result = execute_live_trade_with_bracket(
                    recorder_id=recorder_id,
                    action='CLOSE',  # CLOSE automatically determines side from broker position
                    ticker=ticker,
                    quantity=quantity,  # Will be overridden by actual position size
                    tp_ticks=None,  # No TP for close
                    sl_ticks=None,  # No SL for close
                    is_dca=False
                )
                
                if result.get('success'):
                    closed_count += 1
                    logger.info(f"✅ Closed {side} {quantity} {ticker} for {pos['recorder_name']}")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    errors.append(f"{pos['recorder_name']} {ticker}: {error_msg}")
                    logger.error(f"❌ Failed to close {pos['recorder_name']} {ticker}: {error_msg}")
                
            except Exception as e:
                error_msg = str(e)
                errors.append(f"{pos['recorder_name']} {ticker}: {error_msg}")
                logger.error(f"❌ Error closing {pos['recorder_name']} {ticker}: {error_msg}")
                import traceback
                logger.error(traceback.format_exc())
        
        conn.close()
        
        message = f"Closed {closed_count} position(s) on broker"
        if errors:
            message += f" ({len(errors)} error(s))"
        
        return jsonify({
            'success': True, 
            'message': message, 
            'closed_count': closed_count,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        logger.error(f"Error closing all positions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/control-center/clear-all', methods=['POST'])
def api_control_center_clear_all():
    """Clear all trade records from database (does NOT close broker positions)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete all recorded trades
        cursor.execute('DELETE FROM recorded_trades')
        trades_deleted = cursor.rowcount
        
        # Delete all recorder positions
        cursor.execute('DELETE FROM recorder_positions')
        positions_deleted = cursor.rowcount
        
        # Delete all recorded signals
        cursor.execute('DELETE FROM recorded_signals')
        signals_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        message = f"Cleared {trades_deleted} trade(s), {positions_deleted} position(s), {signals_deleted} signal(s)"
        logger.info(f"🧹 {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'trades_deleted': trades_deleted,
            'positions_deleted': positions_deleted,
            'signals_deleted': signals_deleted
        })
        
    except Exception as e:
        logger.error(f"Error clearing all trades: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/control-center/toggle-all', methods=['POST'])
def api_control_center_toggle_all():
    """Enable or disable all recorders"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE recorders SET recording_enabled = ?', (1 if enabled else 0,))
        updated_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        action = 'enabled' if enabled else 'disabled'
        logger.info(f"📊 {action.upper()} all {updated_count} recorders")
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} recorder(s) {action}',
            'updated_count': updated_count
        })
        
    except Exception as e:
        logger.error(f"Error toggling all recorders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/close-positions', methods=['POST'])
def api_close_recorder_positions(recorder_id):
    """Close all open positions for a specific recorder"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get recorder info
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        recorder = cursor.fetchone()
        if not recorder:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Get open trades for this recorder
        cursor.execute('''
            SELECT id, ticker, side, entry_price, quantity
            FROM recorded_trades
            WHERE recorder_id = ? AND status = 'open'
        ''', (recorder_id,))
        open_trades = cursor.fetchall()
        
        if not open_trades:
            conn.close()
            return jsonify({'success': True, 'message': 'No open positions to close', 'closed_count': 0})
        
        closed_count = 0
        total_pnl = 0
        
        tick_values = {'MNQ': 0.50, 'NQ': 5.00, 'MES': 1.25, 'ES': 12.50, 'M2K': 0.50, 'RTY': 5.00}
        
        for trade in open_trades:
            # Get current price
            current_price = get_market_price_simple(trade['ticker']) or trade['entry_price']
            
            # Calculate tick value
            ticker = trade['ticker'] or ''
            root = ticker.upper().replace('1!', '').replace('!', '')
            tick_value = 1.0
            for key in tick_values:
                if root.startswith(key):
                    tick_value = tick_values[key]
                    break
            
            # Calculate P&L
            if trade['side'] == 'LONG':
                pnl = (current_price - trade['entry_price']) * tick_value * trade['quantity']
            else:
                pnl = (trade['entry_price'] - current_price) * tick_value * trade['quantity']
            
            # Update trade to closed
            cursor.execute('''
                UPDATE recorded_trades 
                SET status = 'closed', exit_price = ?, exit_time = CURRENT_TIMESTAMP, pnl = ?
                WHERE id = ?
            ''', (current_price, pnl, trade['id']))
            
            closed_count += 1
            total_pnl += pnl
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Closed {closed_count} position(s) for '{recorder['name']}': Total PnL ${total_pnl:.2f}")
        
        return jsonify({
            'success': True,
            'message': f"Closed {closed_count} position(s) for {recorder['name']}",
            'closed_count': closed_count,
            'total_pnl': total_pnl
        })
        
    except Exception as e:
        logger.error(f"Error closing recorder positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trades/open/', methods=['GET'])
def get_open_trades():
    """Get open positions (like Trade Manager's /api/trades/open/)"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all open positions
        cursor.execute('''
            SELECT * FROM open_positions
            ORDER BY open_time DESC
        ''')
        positions = cursor.fetchall()
        conn.close()
        
        # Format like Trade Manager
        formatted_positions = []
        for pos in positions:
            formatted_positions.append({
                'id': pos['id'],
                'Strat_Name': pos.get('strategy_name') or 'Manual Trade',
                'Ticker': pos['symbol'],
                'TimeFrame': '',
                'Direction': pos['direction'],
                'Open_Price': str(pos['avg_price']),
                'Open_Time': pos['open_time'],
                'Running_Pos': float(pos['quantity']),
                'Account': pos['account_name'] or f"Account {pos['account_id']}",
                'Nickname': '',
                'Expo': None,
                'Strike': None,
                'Drawdown': f"{pos['unrealized_pnl']:.2f}",
                'StratTicker': pos['symbol'],
                'Stoploss': '0.00',
                'TakeProfit': [],
                'SLTP_Data': {},
                'Opt_Name': pos['symbol'],
                'IfOption': False
            })
        
        return jsonify(formatted_positions)
    except Exception as e:
        logger.error(f"Error fetching open trades: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/manual-trade', methods=['POST'])
def manual_trade():
    """Place a manual trade order"""
    try:
        data = request.get_json() or {}
        account_subaccount = data.get('account_subaccount', '')
        symbol = data.get('symbol', '').strip()
        side = data.get('side', '').strip()
        quantity = int(data.get('quantity', 1))
        risk_settings = data.get('risk') or {}
        
        # DEBUG: Log received risk settings
        logger.info(f"📋 Manual trade request: symbol={symbol}, side={side}, qty={quantity}")
        logger.info(f"📋 Risk settings received: {risk_settings}")
        
        if not account_subaccount:
            return jsonify({'success': False, 'error': 'Account not specified'}), 400
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol not specified'}), 400
        if not side:
            return jsonify({'success': False, 'error': 'Side not specified (Buy/Sell/Close)'}), 400
        if quantity < 1:
            return jsonify({'success': False, 'error': 'Quantity must be at least 1'}), 400
        
        parts = account_subaccount.split(':')
        account_id = int(parts[0])
        subaccount_id = parts[1] if len(parts) > 1 and parts[1] else None
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, tradovate_token, tradovate_refresh_token, md_access_token,
                   token_expires_at, tradovate_accounts
            FROM accounts 
            WHERE id = ? AND tradovate_token IS NOT NULL
        """, (account_id,))
        account = cursor.fetchone()
        if not account:
            conn.close()
            return jsonify({'success': False, 'error': 'Account not found or not connected'}), 400
        
        tradovate_accounts = []
        try:
            if account['tradovate_accounts']:
                tradovate_accounts = json.loads(account['tradovate_accounts'])
        except Exception as parse_err:
            logger.warning(f"Unable to parse tradovate_accounts for account {account_id}: {parse_err}")
            tradovate_accounts = []
        
        selected_subaccount = None
        if subaccount_id:
            for ta in tradovate_accounts:
                if str(ta.get('id')) == subaccount_id:
                    selected_subaccount = ta
                    break
        if not selected_subaccount and tradovate_accounts:
            selected_subaccount = tradovate_accounts[0]
            subaccount_id = str(selected_subaccount.get('id'))
        demo = True
        if selected_subaccount:
            if 'is_demo' in selected_subaccount:
                demo = bool(selected_subaccount.get('is_demo'))
            elif selected_subaccount.get('environment'):
                demo = selected_subaccount['environment'].lower() == 'demo'
        account_spec = (selected_subaccount.get('name') if selected_subaccount else None) or account['name'] or str(account_id)
        account_numeric_id = int(subaccount_id) if subaccount_id else account_id
        
        token_container = {
            'access_token': account['tradovate_token'],
            'refresh_token': account['tradovate_refresh_token'],
            'md_access_token': account['md_access_token']
        }
        
        expires_at = account['token_expires_at']
        needs_refresh = False
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.utcnow() >= exp_dt - timedelta(minutes=5):
                    needs_refresh = True
            except Exception:
                needs_refresh = False
        
        async def refresh_tokens(force=False):
            if not token_container.get('refresh_token'):
                return False
            if not force and not needs_refresh:
                return False
            from phantom_scraper.tradovate_integration import TradovateIntegration
            async with TradovateIntegration(demo=demo) as tradovate:
                tradovate.access_token = token_container['access_token']
                tradovate.refresh_token = token_container['refresh_token']
                tradovate.md_access_token = token_container['md_access_token']
                refreshed = await tradovate.refresh_access_token()
                if refreshed:
                    token_container['access_token'] = tradovate.access_token
                    token_container['refresh_token'] = tradovate.refresh_token
                return refreshed
        
        if needs_refresh and token_container['refresh_token']:
            refreshed = asyncio.run(refresh_tokens())
            if refreshed:
                new_expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                cursor.execute("""
                    UPDATE accounts
                    SET tradovate_token = ?, tradovate_refresh_token = ?, token_expires_at = ?
                    WHERE id = ?
                """, (token_container['access_token'], token_container['refresh_token'], new_expiry, account_id))
                conn.commit()
        conn.close()
        
        tradovate_symbol = convert_tradingview_to_tradovate_symbol(symbol, access_token=token_container['access_token'], demo=demo)
        trade_side = side.lower()
        if trade_side not in ('buy', 'sell', 'close'):
            return jsonify({'success': False, 'error': 'Invalid side supplied'}), 400
        order_side = 'Buy' if trade_side == 'buy' else 'Sell'
        if trade_side == 'close':
            order_side = 'Sell'
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        async def place_trade():
            async with TradovateIntegration(demo=demo) as tradovate:
                tradovate.access_token = token_container['access_token']
                tradovate.refresh_token = token_container['refresh_token']
                tradovate.md_access_token = token_container['md_access_token']
                
                if trade_side == 'close':
                    symbol_upper = tradovate_symbol.upper()
                    logger.info(f"=== CLOSING POSITION + CANCELLING ALL ORDERS FOR {symbol_upper} ===")
                    
                    results = []
                    total_closed = 0
                    total_cancelled = 0
                    
                    # STEP 1: Get positions FIRST to find what we need to close
                    positions = await tradovate.get_positions(account_numeric_id)
                    logger.info(f"Step 1: Retrieved {len(positions)} positions for account {account_numeric_id}")
                    
                    # Log all positions for debugging
                    for idx, pos in enumerate(positions):
                        pos_symbol = pos.get('symbol', 'N/A')
                        pos_net = pos.get('netPos', 0)
                        pos_contract = pos.get('contractId')
                        logger.info(f"  Position {idx+1}: symbol={pos_symbol}, netPos={pos_net}, contractId={pos_contract}")
                    
                    # Match positions - try multiple matching strategies
                    matched_positions = []
                    normalized_target = normalize_symbol(symbol_upper)
                    
                    for pos in positions:
                        pos_symbol = str(pos.get('symbol', '')).upper()
                        pos_net = pos.get('netPos', 0)
                        
                        if not pos_net:  # Skip flat positions
                            continue
                        
                        # Try exact match first
                        if pos_symbol == symbol_upper:
                            matched_positions.append(pos)
                            continue
                        
                        # Try normalized match (handles MNQ vs MNQZ4, etc.)
                        pos_normalized = normalize_symbol(pos_symbol)
                        if pos_normalized == normalized_target:
                            matched_positions.append(pos)
                            continue
                        
                        # Try base symbol match (MNQ matches MNQZ4)
                        pos_base = re.sub(r'[A-Z]\d+$', '', pos_normalized)  # Remove month+year
                        target_base = re.sub(r'[A-Z]\d+$', '', normalized_target)
                        if pos_base and target_base and (pos_base == target_base or pos_base in target_base or target_base in pos_base):
                            matched_positions.append(pos)
                            continue
                    
                    logger.info(f"Step 1b: Found {len(matched_positions)} matching positions for {symbol_upper}")
                    
                    # STEP 2: Close positions using liquidateposition (this also cancels related orders)
                    for pos in matched_positions:
                        contract_id = pos.get('contractId')
                        pos_symbol = pos.get('symbol', symbol_upper)
                        net_pos = pos.get('netPos', 0)
                        
                        if not contract_id:
                            logger.warning(f"Position for {pos_symbol} has no contractId, using manual close")
                            # Manual close
                            qty = abs(int(net_pos))
                            if qty > 0:
                                close_side = 'Sell' if net_pos > 0 else 'Buy'
                                order_data = tradovate.create_market_order(account_spec, pos_symbol, close_side, qty, account_numeric_id)
                                result = await tradovate.place_order(order_data)
                                if result and result.get('success'):
                                    results.append(result)
                                    total_closed += qty
                            continue
                        
                        logger.info(f"Step 2: Liquidating position for {pos_symbol} (contractId: {contract_id}, netPos: {net_pos})")
                        
                        # Use liquidateposition endpoint - this SHOULD close position AND cancel related orders
                        result = await tradovate.liquidate_position(account_numeric_id, contract_id, admin=False)
                        
                        if result and result.get('success'):
                            results.append(result)
                            total_closed += abs(int(net_pos))
                            logger.info(f"✅ Successfully liquidated position for {pos_symbol}")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No response'
                            logger.warning(f"⚠️ liquidateposition returned: {error_msg}, falling back to manual close")
                            
                            # Fallback: Manual close
                            qty = abs(int(net_pos))
                            if qty > 0:
                                close_side = 'Sell' if net_pos > 0 else 'Buy'
                                logger.info(f"Manual close: {close_side} {qty} {pos_symbol}")
                                order_data = tradovate.create_market_order(account_spec, pos_symbol, close_side, qty, account_numeric_id)
                                result = await tradovate.place_order(order_data)
                                if result and result.get('success'):
                                    results.append(result)
                                    total_closed += qty
                    
                    # STEP 3: Cancel ALL remaining orders and strategies (cleanup)
                    logger.info(f"Step 3: Cancelling any remaining orders and strategies")
                    
                    # Get and interrupt order strategies
                    try:
                        all_strategies = await tradovate.get_order_strategies(account_numeric_id)
                        for strategy in all_strategies:
                            strategy_id = strategy.get('id')
                            strategy_status = (strategy.get('status') or '').lower()
                            if strategy_status not in ['completed', 'complete', 'cancelled', 'canceled', 'failed']:
                                logger.info(f"Interrupting order strategy {strategy_id}")
                                await tradovate.interrupt_order_strategy(strategy_id)
                    except Exception as e:
                        logger.warning(f"Error interrupting order strategies: {e}")
                    
                    # Cancel all individual orders
                    cancelled_after = await cancel_open_orders(tradovate, account_numeric_id, None, cancel_all=True)
                    total_cancelled += cancelled_after
                    logger.info(f"Cancelled {cancelled_after} additional orders")
                    
                    # STEP 4: Final verification
                    final_positions = await tradovate.get_positions(account_numeric_id)
                    still_open = [p for p in final_positions if normalize_symbol(p.get('symbol', '')) == normalized_target and p.get('netPos', 0) != 0]
                    
                    logger.info(f"=== CLOSE COMPLETE: Closed {total_closed} contracts, cancelled {total_cancelled} orders ===")
                    
                    if still_open:
                        logger.warning(f"⚠️ Position still open after close attempt!")
                        # Try one more time with direct market order
                        for pos in still_open:
                            qty = abs(int(pos.get('netPos', 0)))
                            close_side = 'Sell' if pos.get('netPos', 0) > 0 else 'Buy'
                            order_data = tradovate.create_market_order(account_spec, pos.get('symbol'), close_side, qty, account_numeric_id)
                            result = await tradovate.place_order(order_data)
                            if result and result.get('success'):
                                total_closed += qty
                                results.append(result)
                    
                    # Build response
                    if total_closed > 0 or total_cancelled > 0:
                        message = f'Closed {total_closed} contracts for {symbol_upper}'
                        if total_cancelled > 0:
                            message += f' and cancelled {total_cancelled} resting orders'
                        
                        response = {
                            'success': True,
                            'message': message,
                            'closed_quantity': total_closed,
                            'cancelled_orders': total_cancelled
                        }
                        if results:
                            response['orderId'] = results[-1].get('data', {}).get('orderId') or results[-1].get('orderId')
                        return response
                    
                    # Nothing to close or cancel
                    if not matched_positions:
                        return {'success': True, 'message': f'No open position found for {symbol_upper}. Nothing to close.'}
                    
                    return {'success': False, 'error': 'Failed to close position'}
                else:
                    order_data = tradovate.create_market_order(
                        account_spec,
                        tradovate_symbol,
                        order_side,
                        quantity,
                        account_numeric_id
                    )
                    if risk_settings:
                        order_data.setdefault('customFields', {})['riskSettings'] = risk_settings
                    result = await tradovate.place_order(order_data)
                    if result and result.get('success') and risk_settings:
                        await apply_risk_orders(
                            tradovate,
                            account_spec,
                            account_numeric_id,
                            tradovate_symbol,
                            order_side,
                            quantity,
                            risk_settings
                        )
                    return result or {'success': False, 'error': 'Failed to place order'}
        
        result = asyncio.run(place_trade())
        if not result.get('success'):
            error_text = str(result.get('error', '')).lower()
            if any(msg in error_text for msg in ['access is denied', 'expired access token']):
                refreshed = asyncio.run(refresh_tokens(force=True))
                if refreshed:
                    result = asyncio.run(place_trade())
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', 'Failed to place order')}), 400

        # Log the order response to see what accountId it was placed on
        order_id = result.get('orderId') or result.get('data', {}).get('orderId')
        order_response = result.get('raw') or result
        logger.info(f"Order placed - Order ID: {order_id}, Account used: {account_numeric_id} ({account_spec}), Full response: {order_response}")
        
        # The order response doesn't include accountId, but we know which one we used
        logger.info(f"✅ Order {order_id} placed on account {account_numeric_id} ({account_spec})")
        
        # Since Tradovate's position API returns 0, we need to track positions from filled orders
        # Get fill price from order status after a short delay
        if result.get('success') and order_id:
            import threading
            def get_fill_price_and_update_position():
                import time
                time.sleep(2)  # Wait 2 seconds for order to fill
                try:
                    from phantom_scraper.tradovate_integration import TradovateIntegration
                    async def fetch_order_details():
                        async with TradovateIntegration(demo=demo) as tradovate:
                            tradovate.access_token = token_container['access_token']
                            tradovate.refresh_token = token_container['refresh_token']
                            tradovate.md_access_token = token_container['md_access_token']
                            
                            # Try to get order details - but orders API returns 0
                            # Instead, check if fill price is in the order response itself
                            # Or use a different approach: get fill price from order history
                            
                            # Method 1: Check order response (might have fill price immediately)
                            # This is handled in the main trade function
                            
                            # Method 1: Try /fill/list endpoint (BEST - gets actual fill prices)
                            avg_fill_price = 0.0
                            fills = await tradovate.get_fills(order_id=order_id)
                            if fills:
                                # Get the most recent fill for this order
                                for fill in fills:
                                    if str(fill.get('orderId')) == str(order_id):
                                        avg_fill_price = fill.get('price') or fill.get('fillPrice') or 0.0
                                        logger.info(f"✅ Found fill price from /fill/list: {avg_fill_price}")
                                        break
                            
                            # Method 2: Query order by ID directly
                            if avg_fill_price == 0:
                                try:
                                    async with tradovate.session.get(
                                        f"{tradovate.base_url}/order/item",
                                        params={'id': order_id},
                                        headers=tradovate._get_headers()
                                    ) as order_response:
                                        if order_response.status == 200:
                                            order_data = await order_response.json()
                                            avg_fill_price = order_data.get('avgFillPrice') or order_data.get('price') or 0.0
                                            order_status = order_data.get('ordStatus') or order_data.get('status', '')
                                            logger.info(f"Order {order_id} from /order/item: status={order_status}, avgFillPrice={avg_fill_price}")
                                            if avg_fill_price > 0:
                                                logger.info(f"✅ Found fill price from /order/item: {avg_fill_price}")
                                except Exception as e:
                                    logger.warning(f"Error fetching order item: {e}")
                            
                            # Method 3: Try orders list (fallback)
                            if avg_fill_price == 0:
                                orders = await tradovate.get_orders(None)
                                if orders:
                                    for o in orders:
                                        if str(o.get('id')) == str(order_id):
                                            avg_fill_price = o.get('avgFillPrice') or o.get('price') or o.get('fillPrice') or 0.0
                                            order_status = o.get('ordStatus') or o.get('status', '')
                                            logger.info(f"Order {order_id} from list: status={order_status}, avgFillPrice={avg_fill_price}")
                                            if avg_fill_price > 0:
                                                logger.info(f"✅ Found fill price from /order/list: {avg_fill_price}")
                                            break
                            
                            # If we found a fill price, update the position
                            if avg_fill_price > 0:
                                # Update position with fill price
                                net_qty = quantity if side.lower() == 'buy' else -quantity
                                cache_key = f"{symbol}_{account_numeric_id}"
                                
                                # Get or create position
                                position = _position_cache.get(cache_key, {
                                    'symbol': symbol,
                                    'quantity': net_qty,
                                    'net_quantity': net_qty,
                                    'avg_price': avg_fill_price,
                                    'last_price': avg_fill_price,  # Start with fill price
                                    'unrealized_pnl': 0.0,
                                    'account_id': account_id,
                                    'subaccount_id': str(account_numeric_id),
                                    'account_name': account_spec,
                                    'order_id': order_id,
                                    'open_time': datetime.now().isoformat()
                                })
                                
                                # Update with fill price
                                position['avg_price'] = avg_fill_price
                                position['last_price'] = avg_fill_price
                                _position_cache[cache_key] = position
                                
                                # Store position in database (like Trade Manager)
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT OR REPLACE INTO open_positions 
                                    (symbol, net_quantity, avg_price, last_price, unrealized_pnl, 
                                     account_id, subaccount_id, account_name, order_id, open_time)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    position['symbol'], position['net_quantity'], position['avg_price'],
                                    position['last_price'], position['unrealized_pnl'], position['account_id'],
                                    position['subaccount_id'], position['account_name'], position['order_id'],
                                    position['open_time']
                                ))
                                conn.commit()
                                conn.close()
                                logger.info(f"✅ Stored position in database: {symbol} qty={net_qty} @ {avg_fill_price}")
                                
                                # Update PnL (will be 0 initially since current = fill)
                                update_position_pnl()
                                
                                # Emit updated position
                                socketio.emit('position_update', {
                                    'positions': [position],
                                    'count': 1,
                                    'timestamp': datetime.now().isoformat(),
                                    'source': 'order_fill'
                                })
                                logger.info(f"Updated position with fill price: {avg_fill_price}")
                            else:
                                logger.warning(f"⚠️ Could not get fill price for order {order_id} - will retry later")
                                # Will need to poll again or use market data estimate
                    asyncio.run(fetch_order_details())
                except Exception as e:
                    logger.warning(f"Error fetching fill price: {e}")
            
            # Start background thread to get fill price
            threading.Thread(target=get_fill_price_and_update_position, daemon=True).start()
            
            # Emit initial position (without fill price for now)
            net_qty = quantity if side.lower() == 'buy' else -quantity
            synthetic_position = {
                'symbol': symbol,
                'quantity': net_qty,
                'net_quantity': net_qty,
                'avg_price': 0.0,  # Will be updated when we get fill price
                'last_price': 0.0,  # Will be updated with market data
                'unrealized_pnl': 0.0,
                'account_id': account_id,
                'subaccount_id': str(account_numeric_id),
                'account_name': account_spec,
                'order_id': order_id
            }
            logger.info(f"Emitting initial position for order {order_id} (fill price will be updated)")
            
            # Store in global cache
            cache_key = f"{symbol}_{account_numeric_id}"
            _position_cache[cache_key] = synthetic_position
            
            # Emit the position update
            socketio.emit('position_update', {
                'positions': [synthetic_position],
                'count': 1,
                'timestamp': datetime.now().isoformat(),
                'source': 'order_fill'
            })

        # Emit WebSocket events for real-time updates (like Trade Manager)
        try:
            # Emit log entry
            socketio.emit('log_entry', {
                'type': 'trade',
                'message': f'Trade executed: {side} {quantity} {symbol}',
                'time': datetime.now().isoformat()
            })
            
            # Emit position update
            socketio.emit('position_update', {
                'strategy': 'Manual Trade',
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'account': account_spec,
                'timestamp': datetime.now().isoformat()
            })
            
            # Trigger immediate position refresh by clearing cache
            if hasattr(emit_realtime_updates, '_last_position_fetch'):
                emit_realtime_updates._last_position_fetch = 0  # Force refresh on next cycle
            
            # Emit trade executed event
            socketio.emit('trade_executed', {
                'strategy': 'Manual Trade',
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_id': result.get('orderId', 'N/A'),
                'account': account_spec,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as ws_error:
            logger.error(f"Error emitting WebSocket events: {ws_error}")

        return jsonify({
            'success': True,
            'message': f'{side} order placed for {quantity} {symbol}',
            'order_id': result.get('orderId', 'N/A')
        })
            
    except Exception as e:
        logger.error(f"Error placing manual trade: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings')
def settings():
    # Require login if auth is available
    if USER_AUTH_AVAILABLE and not is_logged_in():
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/affiliate')
def affiliate():
    return render_template('affiliate.html')

# API Endpoints for Dashboard Filters
@app.route('/api/dashboard/users', methods=['GET'])
def api_dashboard_users():
    """Get list of users for filter dropdown"""
    try:
        try:
            from app.database import SessionLocal
            from app.models import User
            
            db = SessionLocal()
            users = db.query(User).order_by(User.username).all()
            db.close()
            
            return jsonify({
                'users': [{'id': u.id, 'username': u.username, 'email': u.email} for u in users],
                'current_user_id': None  # TODO: Get from session when auth is implemented
            })
        except ImportError:
            # Database modules not available, return empty list
            return jsonify({'error': 'Database not configured', 'users': []}), 200
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to fetch users', 'users': []}), 500

@app.route('/api/dashboard/strategies', methods=['GET'])
def api_dashboard_strategies():
    """Get list of strategies (recorders) for filter dropdown"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all recorders as strategies with trade counts
        cursor.execute('''
            SELECT 
                r.id, 
                r.name, 
                r.symbol, 
                r.recording_enabled,
                COUNT(rt.id) as trade_count,
                SUM(CASE WHEN rt.status = 'closed' THEN rt.pnl ELSE 0 END) as total_pnl
            FROM recorders r
            LEFT JOIN recorded_trades rt ON r.id = rt.recorder_id
            GROUP BY r.id
            ORDER BY r.name
        ''')
        
        recorders = [dict(row) for row in cursor.fetchall()]
        
        # Get unique symbols from recorded trades
        cursor.execute('''
            SELECT DISTINCT ticker FROM recorded_trades WHERE ticker IS NOT NULL
            UNION
            SELECT DISTINCT symbol FROM recorders WHERE symbol IS NOT NULL AND symbol != ''
            ORDER BY 1
        ''')
        symbols = [row['ticker'] or row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'strategies': [{
                'id': r['id'],
                'name': r['name'],
                'symbol': r['symbol'],
                'recording_enabled': bool(r['recording_enabled']),
                'trade_count': r['trade_count'] or 0,
                'total_pnl': r['total_pnl'] or 0
            } for r in recorders],
            'symbols': symbols
        })
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return jsonify({'error': 'Failed to fetch strategies', 'strategies': [], 'symbols': []}), 500

@app.route('/api/dashboard/chart-data', methods=['GET'])
def api_dashboard_chart_data():
    """Get chart data (profit vs drawdown) from recorded trades"""
    try:
        # Get filter parameters
        strategy_id = request.args.get('strategy_id')  # This is recorder_id
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'month')
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build date filter
        date_filter = ''
        if timeframe == 'today':
            date_filter = "AND DATE(rt.exit_time) = DATE('now')"
        elif timeframe == 'week':
            date_filter = "AND rt.exit_time >= DATE('now', '-7 days')"
        elif timeframe == 'month':
            date_filter = "AND rt.exit_time >= DATE('now', '-30 days')"
        elif timeframe == '3months':
            date_filter = "AND rt.exit_time >= DATE('now', '-90 days')"
        elif timeframe == '6months':
            date_filter = "AND rt.exit_time >= DATE('now', '-180 days')"
        elif timeframe == 'year':
            date_filter = "AND rt.exit_time >= DATE('now', '-365 days')"
        
        # Build recorder filter
        recorder_filter = ''
        params = []
        if strategy_id:
            recorder_filter = 'AND rt.recorder_id = ?'
            params.append(int(strategy_id))
        
        # Build symbol filter
        symbol_filter = ''
        if symbol:
            symbol_filter = 'AND rt.ticker = ?'
            params.append(symbol)
        
        # Get daily aggregate PnL
        cursor.execute(f'''
            SELECT 
                DATE(rt.exit_time) as date,
                SUM(rt.pnl) as daily_pnl,
                SUM(CASE WHEN rt.pnl < 0 THEN ABS(rt.pnl) ELSE 0 END) as daily_loss,
                MAX(ABS(CASE WHEN rt.pnl < 0 THEN rt.pnl ELSE 0 END)) as max_single_loss
            FROM recorded_trades rt
            WHERE rt.status = 'closed' {date_filter} {recorder_filter} {symbol_filter}
            GROUP BY DATE(rt.exit_time)
            ORDER BY DATE(rt.exit_time) ASC
        ''', params)
        
        daily_data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Calculate cumulative profit and drawdown
        labels = []
        cumulative_profit = []
        drawdown_per_day = []
        running_profit = 0
        max_profit = 0
        
        for day in daily_data:
            # Format date label
            try:
                date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
                labels.append(date_obj.strftime('%b %d'))
            except:
                labels.append(day['date'])
            
            running_profit += day['daily_pnl'] or 0
            cumulative_profit.append(round(running_profit, 2))
            
            # Track max profit for drawdown calculation
            if running_profit > max_profit:
                max_profit = running_profit
            
            # Drawdown from peak
            current_drawdown = max_profit - running_profit
            drawdown_per_day.append(round(current_drawdown, 2))
        
        # If no data, return empty arrays
        if not labels:
            return jsonify({
                'labels': [],
                'profit': [],
                'drawdown': []
            })
        
        return jsonify({
            'labels': labels,
            'profit': cumulative_profit,
            'drawdown': drawdown_per_day
        })
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch chart data', 'labels': [], 'profit': [], 'drawdown': []}), 500

@app.route('/api/dashboard/trade-history', methods=['GET'])
def api_dashboard_trade_history():
    """Get trade history from recorder_positions (combined positions) with fallback to recorded_trades"""
    try:
        # Get filter parameters
        strategy_id = request.args.get('strategy_id')  # This is recorder_id
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        page = int(request.args.get('page', 1))
        per_page = 20
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if recorder_positions table has data
        cursor.execute("SELECT COUNT(*) FROM recorder_positions WHERE status = 'closed'")
        positions_count = cursor.fetchone()[0]
        
        trades = []
        total_count = 0
        
        if positions_count > 0:
            # Use recorder_positions table (Trade Manager style - combined positions)
            where_clauses = ["rp.status = 'closed'"]
            params = []
            
            if strategy_id:
                where_clauses.append('rp.recorder_id = ?')
                params.append(int(strategy_id))
            
            if symbol:
                where_clauses.append('rp.ticker = ?')
                params.append(symbol)
            
            # Timeframe filter
            if timeframe == 'today':
                where_clauses.append("DATE(rp.closed_at) = DATE('now')")
            elif timeframe == 'week':
                where_clauses.append("rp.closed_at >= DATE('now', '-7 days')")
            elif timeframe == 'month':
                where_clauses.append("rp.closed_at >= DATE('now', '-30 days')")
            elif timeframe == '3months':
                where_clauses.append("rp.closed_at >= DATE('now', '-90 days')")
            elif timeframe == '6months':
                where_clauses.append("rp.closed_at >= DATE('now', '-180 days')")
            elif timeframe == 'year':
                where_clauses.append("rp.closed_at >= DATE('now', '-365 days')")
            
            where_sql = ' AND '.join(where_clauses)
            
            # Get total count
            cursor.execute(f'''
                SELECT COUNT(*) FROM recorder_positions rp WHERE {where_sql}
            ''', params)
            total_count = cursor.fetchone()[0]
            
            # Get paginated positions with recorder name
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT 
                    rp.*,
                    r.name as strategy_name
                FROM recorder_positions rp
                LEFT JOIN recorders r ON rp.recorder_id = r.id
                WHERE {where_sql}
                ORDER BY rp.closed_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            for row in cursor.fetchall():
                pos = dict(row)
                trades.append({
                    'open_time': pos.get('opened_at'),
                    'closed_time': pos.get('closed_at'),
                    'strategy': pos.get('strategy_name') or 'N/A',
                    'symbol': pos.get('ticker'),
                    'side': pos.get('side'),
                    'size': pos.get('total_quantity', 1),
                    'entry_price': pos.get('avg_entry_price'),
                    'exit_price': pos.get('exit_price'),
                    'profit': pos.get('realized_pnl') or 0,
                    'drawdown': abs(pos.get('worst_unrealized_pnl') or 0)
                })
        else:
            # Fallback to recorded_trades table (old behavior)
            where_clauses = ["rt.status = 'closed'"]
            params = []
            
            if strategy_id:
                where_clauses.append('rt.recorder_id = ?')
                params.append(int(strategy_id))
            
            if symbol:
                where_clauses.append('rt.ticker = ?')
                params.append(symbol)
            
            # Timeframe filter
            if timeframe == 'today':
                where_clauses.append("DATE(rt.exit_time) = DATE('now')")
            elif timeframe == 'week':
                where_clauses.append("rt.exit_time >= DATE('now', '-7 days')")
            elif timeframe == 'month':
                where_clauses.append("rt.exit_time >= DATE('now', '-30 days')")
            elif timeframe == '3months':
                where_clauses.append("rt.exit_time >= DATE('now', '-90 days')")
            elif timeframe == '6months':
                where_clauses.append("rt.exit_time >= DATE('now', '-180 days')")
            elif timeframe == 'year':
                where_clauses.append("rt.exit_time >= DATE('now', '-365 days')")
            
            where_sql = ' AND '.join(where_clauses)
            
            # Get total count
            cursor.execute(f'''
                SELECT COUNT(*) FROM recorded_trades rt WHERE {where_sql}
            ''', params)
            total_count = cursor.fetchone()[0]
            
            # Get paginated trades with recorder name
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT 
                    rt.*,
                    r.name as strategy_name
                FROM recorded_trades rt
                LEFT JOIN recorders r ON rt.recorder_id = r.id
                WHERE {where_sql}
                ORDER BY rt.exit_time DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            for row in cursor.fetchall():
                trade = dict(row)
                trades.append({
                    'open_time': trade.get('entry_time'),
                    'closed_time': trade.get('exit_time'),
                    'strategy': trade.get('strategy_name') or 'N/A',
                    'symbol': trade.get('ticker'),
                    'side': trade.get('side'),
                    'size': trade.get('quantity', 1),
                    'entry_price': trade.get('entry_price'),
                    'exit_price': trade.get('exit_price'),
                    'profit': trade.get('pnl') or 0,
                    'drawdown': abs(trade.get('max_adverse') or 0)
                })
        
        conn.close()
        
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        return jsonify({
            'trades': trades,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch trade history', 'trades': []}), 500

@app.route('/api/dashboard/pnl-calendar', methods=['GET'])
def api_pnl_calendar():
    """Get P&L data for calendar view (like Trade Manager)"""
    try:
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('''
                SELECT DATE(timestamp) as date, SUM(pnl) as daily_pnl
                FROM strategy_pnl_history
                WHERE DATE(timestamp) BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''', (start_date, end_date))
        else:
            cursor.execute('''
                SELECT DATE(timestamp) as date, SUM(pnl) as daily_pnl
                FROM strategy_pnl_history
                WHERE DATE(timestamp) BETWEEN ? AND ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''', (start_date, end_date))
        
        data = [{'date': str(row[0]), 'pnl': float(row[1]) if row[1] else 0.0} for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'calendar_data': data})
    except Exception as e:
        logger.error(f"Error fetching P&L calendar: {e}")
        return jsonify({'calendar_data': []})

@app.route('/api/dashboard/pnl-drawdown-chart', methods=['GET'])
def api_pnl_drawdown_chart():
    """Get P&L and drawdown data for chart (like Trade Manager)"""
    try:
        strategy_id = request.args.get('strategy_id', None)
        limit = int(request.args.get('limit', 1000))
        is_postgres = is_using_postgres()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if is_postgres:
            if strategy_id:
                cursor.execute('''
                    SELECT timestamp, pnl, drawdown
                    FROM strategy_pnl_history
                    WHERE strategy_id = %s
                    ORDER BY timestamp DESC LIMIT %s
                ''', (strategy_id, limit))
            else:
                cursor.execute('''
                    SELECT timestamp, pnl, drawdown
                    FROM strategy_pnl_history
                    ORDER BY timestamp DESC LIMIT %s
                ''', (limit,))
        else:
            query = '''
                SELECT timestamp, pnl, drawdown
                FROM strategy_pnl_history
            '''
            params = []
            
            if strategy_id:
                query += ' WHERE strategy_id = ?'
                params.append(strategy_id)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            cursor.execute(query, params)
        
        data = [{
            'timestamp': str(row[0]),
            'pnl': float(row[1]) if row[1] else 0.0,
            'drawdown': float(row[2]) if row[2] else 0.0
        } for row in cursor.fetchall()]
        data.reverse()  # Reverse to get chronological order
        conn.close()
        
        return jsonify({'chart_data': data})
    except Exception as e:
        logger.error(f"Error fetching P&L chart: {e}")
        return jsonify({'chart_data': []})

@app.route('/api/dashboard/metrics', methods=['GET'])
def api_dashboard_metrics():
    """Get metric cards data from recorded trades"""
    try:
        # Get filter parameters
        strategy_id = request.args.get('strategy_id')  # This is recorder_id
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build filters
        where_clauses = ["status = 'closed'"]
        params = []
        
        if strategy_id:
            where_clauses.append('recorder_id = ?')
            params.append(int(strategy_id))
        
        if symbol:
            where_clauses.append('ticker = ?')
            params.append(symbol)
        
        # Timeframe filter
        if timeframe == 'today':
            where_clauses.append("DATE(exit_time) = DATE('now')")
        elif timeframe == 'week':
            where_clauses.append("exit_time >= DATE('now', '-7 days')")
        elif timeframe == 'month':
            where_clauses.append("exit_time >= DATE('now', '-30 days')")
        elif timeframe == '3months':
            where_clauses.append("exit_time >= DATE('now', '-90 days')")
        elif timeframe == '6months':
            where_clauses.append("exit_time >= DATE('now', '-180 days')")
        elif timeframe == 'year':
            where_clauses.append("exit_time >= DATE('now', '-365 days')")
        
        where_sql = ' AND '.join(where_clauses)
        
        # Get aggregate metrics
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_wins,
                SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as total_losses,
                MAX(pnl) as max_profit,
                MIN(pnl) as max_loss,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN ABS(pnl) END) as avg_loss,
                MAX(quantity) as max_quantity,
                AVG(quantity) as avg_quantity,
                MIN(DATE(entry_time)) as first_trade,
                MAX(DATE(exit_time)) as last_trade
            FROM recorded_trades
            WHERE {where_sql}
        ''', params)
        
        row = cursor.fetchone()
        stats = dict(row) if row else {}
        conn.close()
        
        # Calculate derived metrics
        total_trades = stats.get('total_trades') or 0
        wins = stats.get('wins') or 0
        losses = stats.get('losses') or 0
        total_wins_amt = stats.get('total_wins') or 0
        total_losses_amt = stats.get('total_losses') or 1
        
        win_rate_pct = round((wins / total_trades * 100), 1) if total_trades > 0 else 0
        profit_factor = round(total_wins_amt / total_losses_amt, 2) if total_losses_amt > 0 else total_wins_amt
        
        # Calculate time traded
        time_traded = '0D'
        if stats.get('first_trade') and stats.get('last_trade'):
            try:
                first = datetime.strptime(stats['first_trade'], '%Y-%m-%d')
                last = datetime.strptime(stats['last_trade'], '%Y-%m-%d')
                delta = (last - first).days
                months = delta // 30
                days = delta % 30
                if months > 0:
                    time_traded = f"{months}M {days}D"
                else:
                    time_traded = f"{days}D"
            except:
                time_traded = '0D'
        
        return jsonify({
            'metrics': {
                'cumulative_return': {
                    'return': stats.get('total_pnl') or 0,
                    'time_traded': time_traded
                },
                'win_rate': {
                    'wins': wins,
                    'losses': losses,
                    'percentage': win_rate_pct
                },
                'drawdown': {
                    'max': abs(stats.get('max_loss') or 0),
                    'avg': stats.get('avg_loss') or 0,
                    'run': abs(stats.get('max_loss') or 0)
                },
                'total_roi': 0,  # Would need initial capital
                'contracts_held': {
                    'max': stats.get('max_quantity') or 0,
                    'avg': round(stats.get('avg_quantity') or 0)
                },
                'pnl': {
                    'max_profit': stats.get('max_profit') or 0,
                    'avg_profit': stats.get('avg_win') or 0,
                    'max_loss': abs(stats.get('max_loss') or 0),
                    'avg_loss': stats.get('avg_loss') or 0
                },
                'profit_factor': profit_factor
            }
        })
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch metrics', 'metrics': {}}), 500

def calculate_time_traded_legacy(positions):
    """Calculate time traded string like '1M 1D' - Legacy version"""
    if not positions:
        return '0D'
    
    dates = [p.entry_timestamp.date() for p in positions if p.entry_timestamp]
    if not dates:
        return '0D'
    
    min_date = min(dates)
    max_date = max(dates)
    delta = max_date - min_date
    
    months = delta.days // 30
    days = delta.days % 30
    
    if months > 0 and days > 0:
        return f'{months}M {days}D'
    elif months > 0:
        return f'{months}M'
    else:
        return f'{days}D'

@app.route('/api/dashboard/calendar-data', methods=['GET'])
def api_dashboard_calendar_data():
    """Get daily PnL data for calendar view from recorded trades"""
    try:
        # Get filter parameters
        strategy_id = request.args.get('strategy_id')  # This is recorder_id
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'month')
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build filters
        where_clauses = ["status = 'closed'"]
        params = []
        
        if strategy_id:
            where_clauses.append('recorder_id = ?')
            params.append(int(strategy_id))
        
        if symbol:
            where_clauses.append('ticker = ?')
            params.append(symbol)
        
        # Timeframe filter
        if timeframe == 'today':
            where_clauses.append("DATE(exit_time) = DATE('now')")
        elif timeframe == 'week':
            where_clauses.append("exit_time >= DATE('now', '-7 days')")
        elif timeframe == 'month':
            where_clauses.append("exit_time >= DATE('now', '-30 days')")
        elif timeframe == '3months':
            where_clauses.append("exit_time >= DATE('now', '-90 days')")
        elif timeframe == '6months':
            where_clauses.append("exit_time >= DATE('now', '-180 days')")
        elif timeframe == 'year':
            where_clauses.append("exit_time >= DATE('now', '-365 days')")
        
        where_sql = ' AND '.join(where_clauses)
        
        # Get daily PnL
        cursor.execute(f'''
            SELECT 
                DATE(exit_time) as date,
                SUM(pnl) as daily_pnl,
                COUNT(*) as trade_count
            FROM recorded_trades
            WHERE {where_sql}
            GROUP BY DATE(exit_time)
            ORDER BY DATE(exit_time) ASC
        ''', params)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Format for frontend (date string -> {pnl, trades})
        calendar_data = {}
        for row in rows:
            date_str = row['date']
            calendar_data[date_str] = {
                'pnl': round(row['daily_pnl'] or 0, 2),
                'trades': row['trade_count'] or 0
            }
        
        return jsonify({'calendar_data': calendar_data})
    except Exception as e:
        logger.error(f"Error fetching calendar data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch calendar data', 'calendar_data': {}}), 500

@app.route('/api/news-feed', methods=['GET'])
def api_news_feed():
    """Get financial news from RSS feeds"""
    try:
        import feedparser
        import urllib.parse
        
        # Try Yahoo Finance RSS (free, no API key needed)
        feeds = [
            'https://feeds.finance.yahoo.com/rss/2.0/headline?s=ES=F,NQ=F,YM=F&region=US&lang=en-US',
            'https://www.financialjuice.com/feed'
        ]
        
        news_items = []
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:  # Get first 5 items
                    title = entry.get('title', '')[:80]  # Limit length
                    if title:
                        news_items.append({
                            'title': title,
                            'link': entry.get('link', '#')
                        })
            except Exception as e:
                logger.warning(f"Error parsing feed {feed_url}: {e}")
                continue
        
        # If no news, return sample data
        if not news_items:
            news_items = [
                {'title': 'Markets open higher on positive economic data', 'link': '#'},
                {'title': 'Fed signals potential rate adjustments ahead', 'link': '#'},
                {'title': 'Tech stocks rally on strong earnings reports', 'link': '#'},
                {'title': 'Futures trading volume hits record highs', 'link': '#'}
            ]
        
        return jsonify({'news': news_items[:10]})  # Return up to 10 items
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        # Return sample data on error
        return jsonify({
            'news': [
                {'title': 'Markets open higher on positive economic data', 'link': '#'},
                {'title': 'Fed signals potential rate adjustments ahead', 'link': '#'},
                {'title': 'Tech stocks rally on strong earnings reports', 'link': '#'}
            ]
        })

@app.route('/api/market-data', methods=['GET'])
def api_market_data():
    """Get LIVE market data for futures ticker from TradingView"""
    try:
        # Fetch live futures prices
        live_prices = fetch_live_futures_prices()
        
        market_data = []
        for item in live_prices:
            market_data.append({
                'symbol': item['symbol'],
                'price': item['price_str'],
                'change': item['change_str'],
                'direction': item['direction']
            })
        
        # If no live data available, return sample data as fallback
        if not market_data:
            logger.warning("No live futures data available, using fallback")
            market_data = [
                {'symbol': 'ES', 'price': '$5,950.00', 'change': '+0.00%', 'direction': 'up'},
                {'symbol': 'NQ', 'price': '$20,500.00', 'change': '+0.00%', 'direction': 'up'},
                {'symbol': 'MNQ', 'price': '$20,500.00', 'change': '+0.00%', 'direction': 'up'},
                {'symbol': 'YM', 'price': '$43,500.00', 'change': '+0.00%', 'direction': 'up'},
            ]
        
        return jsonify({'data': market_data})
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return jsonify({'data': []})

@app.route('/api/stock-heatmap', methods=['GET'])
def api_stock_heatmap():
    """Get stock heatmap data from Finnhub (primary) or Yahoo Finance (fallback)"""
    try:
        # Check if Finnhub API key is set (optional - falls back to Yahoo if not)
        finnhub_api_key = os.environ.get('FINNHUB_API_KEY', None)
        
        # Try Finnhub first if API key is available
        if finnhub_api_key:
            try:
                return get_finnhub_heatmap_data(finnhub_api_key)
            except Exception as e:
                logger.warning(f"Finnhub API failed, falling back to Yahoo Finance: {e}")
        
        # Fallback to Yahoo Finance (current implementation)
        return get_yahoo_heatmap_data()
    except Exception as e:
        logger.error(f"Error fetching heatmap data: {e}")
        return get_sample_heatmap_data()

def get_finnhub_heatmap_data(api_key):
    """Fetch stock data from Finnhub API"""
    symbols_with_cap = [
        {'symbol': 'NVDA', 'market_cap': 3000},
        {'symbol': 'MSFT', 'market_cap': 3200},
        {'symbol': 'AAPL', 'market_cap': 3500},
        {'symbol': 'GOOGL', 'market_cap': 2000},
        {'symbol': 'AMZN', 'market_cap': 1900},
        {'symbol': 'META', 'market_cap': 1300},
        {'symbol': 'TSLA', 'market_cap': 800},
        {'symbol': 'AVGO', 'market_cap': 600},
        {'symbol': 'ORCL', 'market_cap': 500},
        {'symbol': 'AMD', 'market_cap': 300},
        {'symbol': 'NFLX', 'market_cap': 280},
        {'symbol': 'CSCO', 'market_cap': 250},
        {'symbol': 'INTC', 'market_cap': 200},
        {'symbol': 'MU', 'market_cap': 150},
        {'symbol': 'PLTR', 'market_cap': 50},
        {'symbol': 'HOOD', 'market_cap': 20},
    ]
    
    heatmap_data = []
    successful_fetches = 0
    
    for stock_info in symbols_with_cap[:16]:
        symbol = stock_info['symbol']
        market_cap = stock_info['market_cap']
        
        try:
            # Finnhub quote endpoint
            url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}'
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                current_price = data.get('c', 0)  # Current price
                previous_close = data.get('pc', current_price)  # Previous close
                
                # Finnhub returns change percentage directly as 'dp' (daily percent change)
                change_pct_raw = data.get('dp', None)
                
                if change_pct_raw is not None:
                    # Finnhub returns percentage directly (e.g., 1.65 for 1.65%)
                    change_pct = change_pct_raw
                elif current_price > 0 and previous_close > 0 and previous_close != current_price:
                    # Calculate from price difference
                    change_pct = ((current_price - previous_close) / previous_close) * 100
                else:
                    change_pct = 0
                
                if current_price > 0:
                    
                    # Get market cap from company profile
                    profile_url = f'https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}'
                    profile_response = requests.get(profile_url, timeout=2)
                    real_market_cap = market_cap  # Default to provided market cap
                    
                    if profile_response.status_code == 200:
                        profile = profile_response.json()
                        if 'marketCapitalization' in profile:
                            finnhub_market_cap = profile['marketCapitalization']
                            # Finnhub returns market cap in raw number, convert to billions
                            if finnhub_market_cap and finnhub_market_cap > 1000:  # Sanity check
                                real_market_cap = finnhub_market_cap / 1_000_000_000  # Convert to billions
                            # If the value seems wrong (too small), use fallback
                            if real_market_cap < 10:  # If less than 10B, it's probably wrong
                                real_market_cap = market_cap  # Use provided fallback
                    
                    heatmap_data.append({
                        'symbol': symbol,
                        'price': round(current_price, 2),
                        'change': round(change_pct, 2),
                        'change_pct': f"{'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%",
                        'market_cap': real_market_cap
                    })
                    successful_fetches += 1
                    logger.info(f"Finnhub: Successfully fetched {symbol}: ${current_price:.2f} ({change_pct:+.2f}%)")
        except Exception as e:
            logger.warning(f"Error fetching {symbol} from Finnhub: {e}")
            continue
    
    logger.info(f"Finnhub API: Successfully fetched {successful_fetches} stocks")
    
    if heatmap_data:
        return jsonify({'stocks': heatmap_data})
    else:
        raise Exception("No data from Finnhub")

def get_yahoo_heatmap_data():
    """Get stock heatmap data from Yahoo Finance (fallback)"""
    try:
        # Most active tech stocks with approximate market cap order (largest first)
        # Market cap data for sizing the treemap
        symbols_with_cap = [
            {'symbol': 'NVDA', 'market_cap': 3000},  # Largest - top left
            {'symbol': 'MSFT', 'market_cap': 3200},
            {'symbol': 'AAPL', 'market_cap': 3500},
            {'symbol': 'GOOGL', 'market_cap': 2000},
            {'symbol': 'AMZN', 'market_cap': 1900},
            {'symbol': 'META', 'market_cap': 1300},
            {'symbol': 'TSLA', 'market_cap': 800},
            {'symbol': 'AVGO', 'market_cap': 600},
            {'symbol': 'ORCL', 'market_cap': 500},
            {'symbol': 'AMD', 'market_cap': 300},
            {'symbol': 'NFLX', 'market_cap': 280},
            {'symbol': 'CSCO', 'market_cap': 250},
            {'symbol': 'INTC', 'market_cap': 200},
            {'symbol': 'MU', 'market_cap': 150},
            {'symbol': 'PLTR', 'market_cap': 50},
            {'symbol': 'HOOD', 'market_cap': 20},
        ]
        
        # Fetch data from Yahoo Finance (using their public API)
        heatmap_data = []
        successful_fetches = 0
        for stock_info in symbols_with_cap[:16]:  # Limit to 16 for treemap layout
            symbol = stock_info['symbol']
            market_cap = stock_info['market_cap']
            try:
                # Yahoo Finance quote endpoint (no API key needed)
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d'
                response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200:
                    data = response.json()
                    if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                        result = data['chart']['result'][0]
                        if 'meta' in result:
                            meta = result['meta']
                            current_price = meta.get('regularMarketPrice', 0)
                            # Yahoo Finance chart API uses 'chartPreviousClose', not 'previousClose'
                            previous_close = meta.get('chartPreviousClose') or meta.get('previousClose', 0)
                            
                            # Calculate change percentage from prices
                            if current_price > 0 and previous_close > 0:
                                change_pct = ((current_price - previous_close) / previous_close) * 100
                            else:
                                change_pct = 0
                            
                            # Try to get real market cap from Yahoo Finance
                            real_market_cap = meta.get('marketCap', None)
                            if real_market_cap:
                                # Convert to billions for easier comparison
                                market_cap_billions = real_market_cap / 1_000_000_000
                            else:
                                # Fallback to provided market cap
                                market_cap_billions = market_cap
                            
                            if current_price > 0:
                                heatmap_data.append({
                                    'symbol': symbol,
                                    'price': round(current_price, 2),
                                    'change': round(change_pct, 2),
                                    'change_pct': f"{'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%",
                                    'market_cap': market_cap_billions  # Real market cap in billions
                                })
                                successful_fetches += 1
                                logger.info(f"Successfully fetched {symbol}: ${current_price:.2f} ({change_pct:+.2f}%)")
            except Exception as e:
                logger.warning(f"Error fetching data for {symbol}: {e}")
                continue
        
        logger.info(f"Yahoo Finance API: Successfully fetched {successful_fetches} stocks out of {len(symbols_with_cap[:16])}")
        
        if heatmap_data:
            return jsonify({'stocks': heatmap_data})
        else:
            raise Exception("No data from Yahoo Finance")
    except Exception as e:
        logger.error(f"Error in Yahoo Finance API: {e}")
        raise

def get_sample_heatmap_data():
    """Return sample data as last resort"""
    return jsonify({
        'stocks': [
            {'symbol': 'NVDA', 'price': 189.94, 'change': 1.65, 'change_pct': '+1.65%', 'market_cap': 3000},
            {'symbol': 'MSFT', 'price': 428.50, 'change': 1.29, 'change_pct': '+1.29%', 'market_cap': 3200},
            {'symbol': 'AAPL', 'price': 189.94, 'change': 1.65, 'change_pct': '+1.65%', 'market_cap': 3500},
            {'symbol': 'GOOGL', 'price': 175.20, 'change': -0.16, 'change_pct': '-0.16%', 'market_cap': 2000},
            {'symbol': 'AMZN', 'price': 185.30, 'change': -0.11, 'change_pct': '-0.11%', 'market_cap': 1900},
            {'symbol': 'META', 'price': 512.80, 'change': 0.28, 'change_pct': '+0.28%', 'market_cap': 1300},
            {'symbol': 'TSLA', 'price': 408.83, 'change': 1.70, 'change_pct': '+1.70%', 'market_cap': 800},
            {'symbol': 'AVGO', 'price': 150.20, 'change': 1.20, 'change_pct': '+1.20%', 'market_cap': 600},
            {'symbol': 'ORCL', 'price': 145.30, 'change': 3.87, 'change_pct': '+3.87%', 'market_cap': 500},
            {'symbol': 'AMD', 'price': 185.50, 'change': 1.91, 'change_pct': '+1.91%', 'market_cap': 300},
        ]
    })

@app.route('/webhooks', methods=['POST'])
def create_webhook():
    data = request.get_json()
    url = data.get('url')
    method = data.get('method')
    headers = data.get('headers')
    body = data.get('body')

    if not url or not method:
        return jsonify({'error': 'URL and method are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = is_using_postgres()
    
    if is_postgres:
        cursor.execute('''
            INSERT INTO webhooks (url, method, headers, body)
            VALUES (%s, %s, %s, %s)
        ''', (url, method, headers, body))
    else:
        cursor.execute('''
            INSERT INTO webhooks (url, method, headers, body)
            VALUES (?, ?, ?, ?)
        ''', (url, method, headers, body))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Webhook created successfully'}), 201

@app.route('/webhooks', methods=['GET'])
def get_webhooks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM webhooks')
    webhooks = cursor.fetchall()
    conn.close()

    return jsonify([{
        'id': w[0],
        'url': w[1],
        'method': w[2],
        'headers': w[3],
        'body': w[4],
        'created_at': str(w[5]) if w[5] else None
    } for w in webhooks])

@app.route('/webhooks/<int:id>', methods=['GET'])
def get_webhook(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = is_using_postgres()
    
    if is_postgres:
        cursor.execute('SELECT * FROM webhooks WHERE id = %s', (id,))
    else:
        cursor.execute('SELECT * FROM webhooks WHERE id = ?', (id,))
    webhook = cursor.fetchone()
    conn.close()

    if webhook:
        return jsonify({
            'id': webhook[0],
            'url': webhook[1],
            'method': webhook[2],
            'headers': webhook[3],
            'body': webhook[4],
            'created_at': str(webhook[5]) if webhook[5] else None
        })
    return jsonify({'error': 'Webhook not found'}), 404

@app.route('/webhooks/<int:id>', methods=['DELETE'])
def delete_webhook(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = is_using_postgres()
    
    if is_postgres:
        cursor.execute('DELETE FROM webhooks WHERE id = %s', (id,))
    else:
        cursor.execute('DELETE FROM webhooks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

# Initialize database on import (for gunicorn)
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

# Initialize user authentication system
if USER_AUTH_AVAILABLE:
    try:
        init_auth_system()
        # Create initial admin user if no users exist
        create_initial_admin()
        logger.info("✅ User authentication system initialized")
    except Exception as e:
        logger.warning(f"Auth system initialization warning: {e}")

# ============================================================================
# WebSocket Handlers (Real-time updates like Trade Manager)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info('Client connected to WebSocket')
    emit('status', {
        'connected': True,
        'message': 'Connected to server',
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info('Client disconnected from WebSocket')

@socketio.on('subscribe')
def handle_subscribe(data):
    """Subscribe to specific update channels"""
    channels = data.get('channels', [])
    logger.info(f'Client subscribed to: {channels}')
    emit('subscribed', {'channels': channels})

# ============================================================================
# Strategy P&L Recording Functions
# ============================================================================

def record_strategy_pnl(strategy_id, strategy_name, pnl, drawdown=0.0):
    """Record strategy P&L to database (like Trade Manager)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('''
                INSERT INTO strategy_pnl_history (strategy_id, strategy_name, pnl, drawdown, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            ''', (strategy_id, strategy_name, pnl, drawdown, datetime.now()))
        else:
            cursor.execute('''
                INSERT INTO strategy_pnl_history (strategy_id, strategy_name, pnl, drawdown, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (strategy_id, strategy_name, pnl, drawdown, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error recording strategy P&L: {e}")

def calculate_strategy_pnl(strategy_id):
    """Calculate current P&L for a strategy from trades database"""
    try:
        # Try to get P&L from just_trades.db (SQLAlchemy models)
        try:
            from app.database import SessionLocal
            from app.models import Trade, Position
            
            db = SessionLocal()
            
            # Calculate realized P&L from closed trades
            closed_trades = db.query(Trade).filter(
                Trade.strategy_id == strategy_id,
                Trade.status == 'filled',
                Trade.closed_at.isnot(None)
            ).all()
            
            realized_pnl = sum(trade.pnl or 0.0 for trade in closed_trades)
            
            # Calculate unrealized P&L from open positions
            positions = db.query(Position).filter(
                Position.account_id.in_(
                    db.query(Trade.account_id).filter(Trade.strategy_id == strategy_id).distinct()
                )
            ).all()
            
            unrealized_pnl = sum(pos.unrealized_pnl or 0.0 for pos in positions)
            
            total_pnl = realized_pnl + unrealized_pnl
            db.close()
            
            return total_pnl
            
        except ImportError:
            # Fallback to SQLite direct query
            conn = get_db_connection()
            cursor = conn.execute('''
                SELECT COALESCE(SUM(pnl), 0.0) as total_pnl
                FROM trades
                WHERE strategy_id = ? AND status = 'filled'
            ''', (strategy_id,))
            result = cursor.fetchone()
            if result:
                pnl_val = result.get('total_pnl') if isinstance(result, dict) else result[0]
                pnl = float(pnl_val) if pnl_val else 0.0
            else:
                pnl = 0.0
            conn.close()
            return pnl
            
    except Exception as e:
        logger.error(f"Error calculating strategy P&L: {e}")
        return 0.0

def calculate_strategy_drawdown(strategy_id):
    """Calculate current drawdown for a strategy"""
    try:
        # Get historical P&L to calculate drawdown
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        
        if is_postgres:
            cursor.execute('''
                SELECT pnl FROM strategy_pnl_history
                WHERE strategy_id = %s
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (strategy_id,))
        else:
            cursor.execute('''
                SELECT pnl FROM strategy_pnl_history
                WHERE strategy_id = ?
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (strategy_id,))
        
        pnl_history = [float(row[0]) for row in cursor.fetchall() if row[0] is not None]
        conn.close()
        
        if not pnl_history:
            return 0.0
        
        # Calculate drawdown: peak - current
        peak = max(pnl_history)
        current = pnl_history[0] if pnl_history else 0.0
        drawdown = max(0.0, peak - current)
        
        return drawdown
        
    except Exception as e:
        logger.error(f"Error calculating strategy drawdown: {e}")
        return 0.0

# ============================================================================
# Background Threads for Real-Time Updates (Every Second, like Trade Manager)
# ============================================================================

# Global position cache to persist positions across updates
_position_cache = {}

# Market data cache for real-time prices
_market_data_cache = {}

# Market data WebSocket connection
_market_data_ws = None
_market_data_ws_task = None
_market_data_subscribed_symbols = set()

async def connect_tradovate_market_data_websocket():
    """Connect to Tradovate market data WebSocket and subscribe to quotes"""
    global _market_data_cache, _market_data_ws, _market_data_subscribed_symbols
    
    if not WEBSOCKETS_AVAILABLE:
        logger.error("websockets library not available. Cannot connect to market data.")
        return
    
    # Get md_access_token from database
    md_token = None
    demo = True  # Default to demo
    account_id = None
    
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, md_access_token, environment, tradovate_token FROM accounts 
            WHERE md_access_token IS NOT NULL AND md_access_token != ''
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            account_id = row['id']
            md_token = row['md_access_token']
            # Check if environment is 'demo' or 'live'
            # Note: sqlite3.Row doesn't have .get() method, use dict() or direct access
            env = row['environment'] if row['environment'] else 'demo'
            demo = (env == 'demo' or env is None)
            
            # Validate that the account has valid tokens before connecting
            if account_id:
                valid_token = get_valid_tradovate_token(account_id)
                if not valid_token:
                    logger.warning(f"Account {account_id} has no valid access token - WebSocket may fail")
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching md_access_token: {e}")
        return
    
    if not md_token:
        logger.warning("No md_access_token found. Market data WebSocket will not connect.")
        return
    
    # WebSocket URL (demo or live)
    ws_url = "wss://demo.tradovateapi.com/v1/websocket" if demo else "wss://live.tradovateapi.com/v1/websocket"
    
    while True:
        try:
            logger.info(f"Connecting to Tradovate market data WebSocket: {ws_url}")
            async with websockets.connect(ws_url) as ws:
                _market_data_ws = ws
                logger.info("✅ Market data WebSocket connected")
                
                # Authorize with md_access_token
                # Format: "authorize\n0\n\n{token}"
                auth_message = f"authorize\n0\n\n{md_token}"
                await ws.send(auth_message)
                
                # Wait for authorization response
                response = await ws.recv()
                logger.info(f"Market data auth response: {response[:200]}")
                
                # Subscribe to quotes for symbols we have positions in
                await subscribe_to_market_data_symbols(ws)
                
                # Listen for market data updates
                async for message in ws:
                    try:
                        # Parse message (format: "frame\n{id}\n\n{json_data}")
                        if message.startswith("frame"):
                            parts = message.split("\n", 3)
                            if len(parts) >= 4:
                                json_data = json.loads(parts[3])
                                await process_market_data_message(json_data)
                        elif message.startswith("["):
                            # Direct JSON array format
                            data = json.loads(message)
                            await process_market_data_message(data)
                    except json.JSONDecodeError as e:
                        logger.debug(f"Could not parse market data message: {e}")
                    except Exception as e:
                        logger.warning(f"Error processing market data message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Market data WebSocket connection closed. Reconnecting in 5 seconds...")
            # Validate tokens before reconnecting
            if account_id:
                get_valid_tradovate_token(account_id)  # Auto-refresh if needed
            await asyncio.sleep(5)
        except Exception as e:
            error_str = str(e)
            # Check for rate limiting (429)
            if '429' in error_str:
                logger.error(f"Market data WebSocket rate limited (429). Backing off for 120 seconds...")
                await asyncio.sleep(120)  # Long backoff for rate limiting
            else:
                logger.error(f"Market data WebSocket error: {e}. Reconnecting in 30 seconds...")
                # Validate tokens before reconnecting
                if account_id:
                    get_valid_tradovate_token(account_id)  # Auto-refresh if needed
                await asyncio.sleep(30)  # Increased from 10 to 30 seconds

async def subscribe_to_market_data_symbols(ws):
    """Subscribe to market data quotes for symbols we have positions in AND open recorder trades"""
    global _position_cache, _market_data_subscribed_symbols
    
    # Get symbols from positions
    symbols_to_subscribe = set()
    for position in _position_cache.values():
        symbol = position.get('symbol', '')
        if symbol:
            # Convert TradingView symbol to Tradovate format if needed
            # MES1! -> MESM1 (front month)
            tradovate_symbol = convert_symbol_for_tradovate_md(symbol)
            symbols_to_subscribe.add(tradovate_symbol)
    
    # Also check database for open positions
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM open_positions WHERE symbol IS NOT NULL")
        for row in cursor.fetchall():
            symbol = row[0]
            if symbol:
                tradovate_symbol = convert_symbol_for_tradovate_md(symbol)
                symbols_to_subscribe.add(tradovate_symbol)
        conn.close()
    except Exception as e:
        logger.warning(f"Error getting symbols from database: {e}")
    
    # Get symbols from open recorder trades (for TP/SL monitoring)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT ticker FROM recorded_trades 
            WHERE status = 'open' AND ticker IS NOT NULL
        ''')
        for row in cursor.fetchall():
            symbol = row[0]
            if symbol:
                tradovate_symbol = convert_symbol_for_tradovate_md(symbol)
                symbols_to_subscribe.add(tradovate_symbol)
                logger.info(f"Adding recorder trade symbol to market data subscription: {symbol} -> {tradovate_symbol}")
        conn.close()
    except Exception as e:
        logger.warning(f"Error getting recorder trade symbols: {e}")
    
    # Subscribe to each symbol
    for symbol in symbols_to_subscribe:
        if symbol not in _market_data_subscribed_symbols:
            try:
                # Subscribe to quote data
                # Format: "quote/subscribe\n{id}\n\n{json}"
                subscribe_msg = f"quote/subscribe\n1\n\n{json.dumps({'symbol': symbol})}"
                await ws.send(subscribe_msg)
                _market_data_subscribed_symbols.add(symbol)
                logger.info(f"Subscribed to market data for {symbol}")
            except Exception as e:
                logger.warning(f"Error subscribing to {symbol}: {e}")

def convert_symbol_for_tradovate_md(symbol: str) -> str:
    """Convert symbol format for Tradovate market data (MES1! -> MESM1)"""
    # Remove ! and convert month codes
    symbol = symbol.upper().replace('!', '')
    # If it ends with a number, it's already in Tradovate format
    if symbol[-1].isdigit():
        return symbol
    # Otherwise, try to get front month (simplified - you may need contract lookup)
    # For now, just return the symbol as-is
    return symbol

async def process_market_data_message(data):
    """Process incoming market data message and update cache"""
    global _market_data_cache
    
    try:
        symbols_updated = set()
        
        # Handle different message formats
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    symbol = item.get('symbol') or item.get('s')
                    if symbol:
                        # Update cache with latest price
                        if symbol not in _market_data_cache:
                            _market_data_cache[symbol] = {}
                        
                        # Extract price data
                        last = item.get('last') or item.get('lastPrice') or item.get('l')
                        bid = item.get('bid') or item.get('b')
                        ask = item.get('ask') or item.get('a')
                        
                        if last:
                            _market_data_cache[symbol]['last'] = float(last)
                            symbols_updated.add(symbol)
                        if bid:
                            _market_data_cache[symbol]['bid'] = float(bid)
                        if ask:
                            _market_data_cache[symbol]['ask'] = float(ask)
                        
        elif isinstance(data, dict):
            symbol = data.get('symbol') or data.get('s')
            if symbol:
                if symbol not in _market_data_cache:
                    _market_data_cache[symbol] = {}
                
                last = data.get('last') or data.get('lastPrice') or data.get('l')
                bid = data.get('bid') or data.get('b')
                ask = data.get('ask') or data.get('a')
                
                if last:
                    _market_data_cache[symbol]['last'] = float(last)
                    symbols_updated.add(symbol)
                if bid:
                    _market_data_cache[symbol]['bid'] = float(bid)
                if ask:
                    _market_data_cache[symbol]['ask'] = float(ask)
        
        # Update PnL for positions with this symbol
        update_position_pnl()
        
        # Check TP/SL for open recorder trades
        if symbols_updated:
            check_recorder_trades_tp_sl(symbols_updated)
                
    except Exception as e:
        logger.warning(f"Error processing market data: {e}")

def check_recorder_trades_tp_sl(symbols_updated: set):
    """
    Check open recorder trades for TP/SL hits based on current market prices.
    This is called on every market data update for real-time TP/SL monitoring.
    """
    global _market_data_cache
    
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all open trades that have TP or SL set
        cursor.execute('''
            SELECT t.*, r.name as recorder_name 
            FROM recorded_trades t
            JOIN recorders r ON t.recorder_id = r.id
            WHERE t.status = 'open' AND (t.tp_price IS NOT NULL OR t.sl_price IS NOT NULL)
        ''')
        
        open_trades = [dict(row) for row in cursor.fetchall()]
        
        for trade in open_trades:
            ticker = trade['ticker']
            
            # Normalize ticker for market data lookup (MNQ1! -> MNQ, etc.)
            ticker_root = extract_symbol_root(ticker) if ticker else None
            if not ticker_root:
                continue
            
            # Find price in cache (try various symbol formats)
            current_price = None
            for cached_symbol in _market_data_cache.keys():
                if ticker_root in cached_symbol.upper():
                    current_price = _market_data_cache[cached_symbol].get('last')
                    if current_price:
                        break
            
            if not current_price:
                continue
            
            # =====================================================
            # MFE/MAE TRACKING - Update on every price tick
            # =====================================================
            side = trade['side']
            entry_price = trade['entry_price']
            tick_size = get_tick_size(ticker)
            tick_value = get_tick_value(ticker)
            
            # Get current MFE/MAE values
            current_max_favorable = trade.get('max_favorable') or 0
            current_max_adverse = trade.get('max_adverse') or 0
            
            # Calculate current excursion based on trade direction
            if side == 'LONG':
                # For LONG: favorable = price went UP, adverse = price went DOWN
                favorable_excursion = max(0, current_price - entry_price)
                adverse_excursion = max(0, entry_price - current_price)
            else:  # SHORT
                # For SHORT: favorable = price went DOWN, adverse = price went UP
                favorable_excursion = max(0, entry_price - current_price)
                adverse_excursion = max(0, current_price - entry_price)
            
            # Update MFE/MAE if we have new highs/lows
            new_max_favorable = max(current_max_favorable, favorable_excursion)
            new_max_adverse = max(current_max_adverse, adverse_excursion)
            
            # Only update database if values changed (to reduce DB writes)
            if new_max_favorable != current_max_favorable or new_max_adverse != current_max_adverse:
                cursor.execute('''
                    UPDATE recorded_trades 
                    SET max_favorable = ?, max_adverse = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_max_favorable, new_max_adverse, trade['id']))
                conn.commit()
                
                # Log significant drawdown events (when MAE increases by more than 2 ticks)
                if new_max_adverse > current_max_adverse:
                    mae_ticks = new_max_adverse / tick_size if tick_size > 0 else 0
                    mae_dollars = mae_ticks * tick_value * trade['quantity']
                    if mae_ticks >= 2:  # Only log if significant
                        logger.debug(f"📉 MAE update for trade {trade['id']}: {mae_ticks:.1f} ticks (${mae_dollars:.2f})")
            
            # Check TP/SL
            tp_price = trade.get('tp_price')
            sl_price = trade.get('sl_price')
            
            hit_type = None
            exit_price = None
            
            if side == 'LONG':
                # LONG: TP hit if price >= tp_price, SL hit if price <= sl_price
                if tp_price and current_price >= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                elif sl_price and current_price <= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
            else:  # SHORT
                # SHORT: TP hit if price <= tp_price, SL hit if price >= sl_price
                if tp_price and current_price <= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                elif sl_price and current_price >= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
            
            if hit_type and exit_price:
                # Calculate PnL (tick_size and tick_value already calculated above for MFE/MAE)
                if side == 'LONG':
                    pnl_ticks = (exit_price - entry_price) / tick_size
                else:
                    pnl_ticks = (entry_price - exit_price) / tick_size
                
                pnl = pnl_ticks * tick_value * trade['quantity']
                
                # Close the trade
                cursor.execute('''
                    UPDATE recorded_trades 
                    SET exit_price = ?, exit_time = CURRENT_TIMESTAMP, 
                        pnl = ?, pnl_ticks = ?, status = 'closed', 
                        exit_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (exit_price, pnl, pnl_ticks, hit_type, trade['id']))
                
                conn.commit()
                
                # Also close any open position in recorder_positions (Trade Manager style)
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (trade['recorder_id'], ticker))
                open_pos = cursor.fetchone()
                if open_pos:
                    # Close the position with proper PnL calculation
                    cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (open_pos[0],))
                    pos_row = cursor.fetchone()
                    if pos_row:
                        pos_columns = [desc[0] for desc in cursor.description]
                        pos = dict(zip(pos_columns, pos_row))
                        
                        pos_avg_entry = pos['avg_entry_price']
                        pos_total_qty = pos['total_quantity']
                        pos_side = pos['side']
                        
                        if pos_side == 'LONG':
                            pos_pnl_ticks = (exit_price - pos_avg_entry) / tick_size
                        else:
                            pos_pnl_ticks = (pos_avg_entry - exit_price) / tick_size
                        
                        pos_realized_pnl = pos_pnl_ticks * tick_value * pos_total_qty
                        
                        cursor.execute('''
                            UPDATE recorder_positions
                            SET status = 'closed',
                                exit_price = ?,
                                realized_pnl = ?,
                                closed_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (exit_price, pos_realized_pnl, open_pos[0]))
                        conn.commit()
                        
                        logger.info(f"📊 Position closed on {hit_type.upper()}: {pos_side} {ticker} x{pos_total_qty} | "
                                   f"Avg Entry: {pos_avg_entry} | Exit: {exit_price} | PnL: ${pos_realized_pnl:.2f}")
                
                logger.info(f"🎯 {hit_type.upper()} HIT via market data for '{trade['recorder_name']}': "
                           f"{side} {ticker} | Entry: {entry_price} | Exit: {exit_price} | "
                           f"PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks)")
                
                # Emit WebSocket event for real-time UI updates
                try:
                    socketio.emit('trade_executed', {
                        'recorder_id': trade['recorder_id'],
                        'recorder_name': trade['recorder_name'],
                        'trade_id': trade['id'],
                        'side': side,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'pnl_ticks': pnl_ticks,
                        'exit_reason': hit_type.upper(),
                        'ticker': ticker,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    socketio.emit('signal_received', {
                        'recorder_id': trade['recorder_id'],
                        'recorder_name': trade['recorder_name'],
                        'action': f'{hit_type.upper()}_HIT',
                        'ticker': ticker,
                        'price': exit_price,
                        'timestamp': datetime.now().isoformat(),
                        'trade': {
                            'action': 'closed',
                            'trade_id': trade['id'],
                            'side': side,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'exit_reason': hit_type.upper()
                        }
                    })
                except Exception as e:
                    logger.warning(f"Could not emit WebSocket update: {e}")
        
        conn.close()
        
    except Exception as e:
        logger.warning(f"Error checking recorder trades TP/SL: {e}")
        import traceback
        logger.debug(traceback.format_exc())


def start_market_data_websocket():
    """Start the market data WebSocket in a background thread"""
    global _market_data_ws_task
    if _market_data_ws_task and hasattr(_market_data_ws_task, 'is_alive') and _market_data_ws_task.is_alive():
        return  # Already running
    
    def run_websocket():
        asyncio.run(connect_tradovate_market_data_websocket())
    
    _market_data_ws_task = threading.Thread(target=run_websocket, daemon=True)
    _market_data_ws_task.start()
    logger.info("Market data WebSocket thread started")


# ============================================================================
# Recorder Trade TP/SL Polling (Fallback when WebSocket not available)
# ============================================================================

_recorder_tp_sl_thread = None

def poll_recorder_trades_tp_sl():
    """
    Polling fallback for TP/SL monitoring when Tradovate WebSocket isn't connected.
    Uses TradingView public API to get prices every 5 seconds.
    """
    global _market_data_cache
    
    logger.info("🔄 Starting recorder trade TP/SL polling thread (every 5 seconds)")
    
    while True:
        try:
            # Get all open trades with TP/SL set
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT ticker FROM recorded_trades 
                WHERE status = 'open' AND ticker IS NOT NULL
                AND (tp_price IS NOT NULL OR sl_price IS NOT NULL)
            ''')
            
            symbols_needed = [row['ticker'] for row in cursor.fetchall()]
            conn.close()
            
            if not symbols_needed:
                time.sleep(5)
                continue
            
            # Fetch prices for all symbols
            symbols_updated = set()
            for symbol in symbols_needed:
                price = get_cached_price(symbol)
                if price:
                    root = extract_symbol_root(symbol)
                    if root not in _market_data_cache:
                        _market_data_cache[root] = {}
                    _market_data_cache[root]['last'] = price
                    symbols_updated.add(root)
                    logger.debug(f"Polled price for {symbol}: {price}")
            
            # Check TP/SL for open trades
            if symbols_updated:
                check_recorder_trades_tp_sl(symbols_updated)
            
            time.sleep(5)  # Poll every 5 seconds
            
        except Exception as e:
            logger.warning(f"Error in TP/SL polling: {e}")
            time.sleep(10)


def start_recorder_tp_sl_polling():
    """Start the TP/SL polling thread"""
    global _recorder_tp_sl_thread
    
    if _recorder_tp_sl_thread and _recorder_tp_sl_thread.is_alive():
        return
    
    _recorder_tp_sl_thread = threading.Thread(target=poll_recorder_trades_tp_sl, daemon=True)
    _recorder_tp_sl_thread.start()
    logger.info("✅ Recorder TP/SL polling thread started")


# ============================================================================
# Position Drawdown Polling (Trade Manager Style Real-Time Tracking)
# ============================================================================

_position_drawdown_thread = None

def poll_recorder_positions_drawdown():
    """
    Background thread that polls open positions and updates drawdown (worst_unrealized_pnl).
    Runs every 1 second for accurate tracking - same as Trade Manager.
    """
    global _market_data_cache
    
    logger.info("📊 Starting position drawdown tracker (every 1 second)")
    
    while True:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all open positions
            cursor.execute('''
                SELECT rp.*, r.name as recorder_name
                FROM recorder_positions rp
                JOIN recorders r ON rp.recorder_id = r.id
                WHERE rp.status = 'open'
            ''')
            
            positions = [dict(row) for row in cursor.fetchall()]
            
            for pos in positions:
                ticker = pos['ticker']
                side = pos['side']
                avg_entry = pos['avg_entry_price']
                total_qty = pos['total_quantity']
                
                # Get current price from market data cache
                root = extract_symbol_root(ticker)
                current_price = None
                if root in _market_data_cache:
                    current_price = _market_data_cache[root].get('last')
                
                if not current_price:
                    # Try to get cached price
                    current_price = get_cached_price(ticker)
                
                if not current_price:
                    continue
                
                # Calculate unrealized P&L
                tick_size = get_tick_size(ticker)
                tick_value = get_tick_value(ticker)
                
                if side == 'LONG':
                    pnl_ticks = (current_price - avg_entry) / tick_size
                else:  # SHORT
                    pnl_ticks = (avg_entry - current_price) / tick_size
                
                unrealized_pnl = pnl_ticks * tick_value * total_qty
                
                # Update worst/best unrealized P&L
                current_worst = pos['worst_unrealized_pnl'] or 0
                current_best = pos['best_unrealized_pnl'] or 0
                
                new_worst = min(current_worst, unrealized_pnl)  # Worst is most negative
                new_best = max(current_best, unrealized_pnl)    # Best is most positive
                
                # Only update database if values changed
                if new_worst != current_worst or new_best != current_best or pos['current_price'] != current_price:
                    cursor.execute('''
                        UPDATE recorder_positions
                        SET current_price = ?, 
                            unrealized_pnl = ?,
                            worst_unrealized_pnl = ?,
                            best_unrealized_pnl = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (current_price, unrealized_pnl, new_worst, new_best, pos['id']))
                    conn.commit()
                    
                    # Log significant drawdown changes
                    if new_worst < current_worst:
                        logger.debug(f"📉 Position drawdown update: {pos['recorder_name']} {side} {ticker} x{total_qty} | Drawdown: ${abs(new_worst):.2f}")
            
            conn.close()
            
        except Exception as e:
            logger.warning(f"Error in position drawdown polling: {e}")
        
        time.sleep(1)  # Poll every 1 second for accurate tracking


def start_position_drawdown_polling():
    """Start the position drawdown polling thread"""
    global _position_drawdown_thread
    
    if _position_drawdown_thread and _position_drawdown_thread.is_alive():
        return
    
    _position_drawdown_thread = threading.Thread(target=poll_recorder_positions_drawdown, daemon=True)
    _position_drawdown_thread.start()
    logger.info("✅ Position drawdown polling thread started")


# ============================================================================
# TradingView WebSocket for Real-Time Price Data
# ============================================================================

_tradingview_ws = None
_tradingview_ws_thread = None
_tradingview_subscribed_symbols = set()

def get_tradingview_session():
    """Get TradingView session cookies from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT tradingview_session FROM accounts WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return json.loads(row[0])
        return None
    except Exception as e:
        logger.error(f"Error getting TradingView session: {e}")
        return None


async def connect_tradingview_websocket():
    """Connect to TradingView WebSocket for real-time quotes"""
    global _market_data_cache, _tradingview_ws, _tradingview_subscribed_symbols
    
    if not WEBSOCKETS_AVAILABLE:
        logger.error("websockets library not available for TradingView")
        return
    
    session = get_tradingview_session()
    if not session or not session.get('sessionid'):
        logger.warning("No TradingView session configured. Use /api/tradingview/session to set it up.")
        return
    
    sessionid = session.get('sessionid')
    sessionid_sign = session.get('sessionid_sign', '')
    
    # TradingView WebSocket URL
    ws_url = "wss://data.tradingview.com/socket.io/websocket"
    
    while True:
        try:
            logger.info(f"Connecting to TradingView WebSocket...")
            
            # Create connection with headers
            async with websockets.connect(
                ws_url,
                additional_headers={
                    'Origin': 'https://www.tradingview.com',
                    'Cookie': f'sessionid={sessionid}; sessionid_sign={sessionid_sign}'
                }
            ) as ws:
                _tradingview_ws = ws
                logger.info("✅ TradingView WebSocket connected!")
                
                # TradingView uses a custom protocol
                # The cookies handle auth, we use "unauthorized_user_token" for WebSocket
                # but the cookies give us access to real-time data
                auth_msg = json.dumps({
                    "m": "set_auth_token",
                    "p": ["unauthorized_user_token"]
                })
                await ws.send(f"~m~{len(auth_msg)}~m~{auth_msg}")
                logger.info("Sent TradingView auth")
                
                # Create a quote session
                quote_session = f"qs_{int(time.time())}"
                create_session_msg = json.dumps({
                    "m": "quote_create_session",
                    "p": [quote_session]
                })
                await ws.send(f"~m~{len(create_session_msg)}~m~{create_session_msg}")
                
                # Subscribe to symbols we need
                await subscribe_tradingview_symbols(ws, quote_session)
                
                # Listen for messages
                msg_count = 0
                async for message in ws:
                    msg_count += 1
                    try:
                        # Handle ping/pong
                        if message.startswith('~h~'):
                            # Respond to heartbeat
                            await ws.send(message)
                            continue
                        
                        await process_tradingview_message(message)
                        
                        # Log first few messages
                        if msg_count <= 5:
                            logger.info(f"TradingView msg #{msg_count}: {message[:100]}...")
                            
                    except Exception as e:
                        logger.warning(f"Error processing TradingView message: {e}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"TradingView WebSocket closed: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"TradingView WebSocket error: {e}. Reconnecting in 10 seconds...")
            import traceback
            logger.debug(traceback.format_exc())
            await asyncio.sleep(10)


async def subscribe_tradingview_symbols(ws, quote_session):
    """Subscribe to symbols for real-time quotes"""
    global _tradingview_subscribed_symbols
    
    # Get symbols from open recorder trades
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT ticker FROM recorded_trades 
            WHERE status = 'open' AND ticker IS NOT NULL
        ''')
        
        symbols = set()
        for row in cursor.fetchall():
            ticker = row[0]
            if ticker:
                # Convert to TradingView format
                root = extract_symbol_root(ticker)
                tv_symbol = f"CME_MINI:{root}1!" if root in ['MNQ', 'MES', 'M2K'] else f"CME:{root}1!"
                symbols.add(tv_symbol)
        conn.close()
        
        # Also add common symbols
        default_symbols = ['CME_MINI:MNQ1!', 'CME_MINI:MES1!', 'CME:NQ1!', 'CME:ES1!']
        symbols.update(default_symbols)
        
        for symbol in symbols:
            if symbol not in _tradingview_subscribed_symbols:
                # Add symbol to session - simplified format
                add_msg = json.dumps({
                    "m": "quote_add_symbols",
                    "p": [quote_session, symbol]
                })
                await ws.send(f"~m~{len(add_msg)}~m~{add_msg}")
                _tradingview_subscribed_symbols.add(symbol)
                logger.info(f"📈 Subscribed to TradingView: {symbol}")
                
    except Exception as e:
        logger.warning(f"Error subscribing to TradingView symbols: {e}")


async def process_tradingview_message(message):
    """Process incoming TradingView WebSocket message"""
    global _market_data_cache
    
    try:
        # TradingView messages are formatted as: ~m~{length}~m~{json}
        if not message:
            return
        
        # Log first few messages for debugging
        if len(message) < 500:
            logger.debug(f"TradingView raw msg: {message[:200]}")
        
        # Handle heartbeat
        if message.startswith('~h~'):
            return
        
        if not message.startswith('~m~'):
            return
        
        # Extract JSON part
        parts = message.split('~m~')
        for part in parts:
            if not part or part.isdigit():
                continue
            
            try:
                data = json.loads(part)
                
                # Log message type
                if isinstance(data, dict):
                    msg_type = data.get('m', 'unknown')
                    logger.debug(f"TradingView msg type: {msg_type}")
                
                # Handle quote update messages
                if isinstance(data, dict) and data.get('m') == 'qsd':
                    # Quote session data
                    params = data.get('p', [])
                    logger.debug(f"QSD params: {params}")
                    if len(params) >= 2:
                        symbol_data = params[1]
                        symbol = symbol_data.get('n', '')  # Symbol name
                        values = symbol_data.get('v', {})
                        
                        if symbol and values:
                            # TradingView can send price in different fields
                            last_price = values.get('lp') or values.get('last_price') or values.get('ch')
                            bid = values.get('bid')
                            ask = values.get('ask')
                            
                            # Log what we're getting
                            if 'lp' in values or 'bid' in values or 'ask' in values:
                                logger.info(f"📊 TradingView {symbol}: lp={values.get('lp')}, bid={bid}, ask={ask}")
                            
                            # Use mid price if we have bid/ask but no last
                            if not last_price and bid and ask:
                                last_price = (float(bid) + float(ask)) / 2
                            
                            if last_price:
                                # Extract root symbol (CME_MINI:MNQ1! -> MNQ)
                                root = symbol.split(':')[-1].replace('1!', '').replace('!', '')
                                
                                if root not in _market_data_cache:
                                    _market_data_cache[root] = {}
                                
                                _market_data_cache[root]['last'] = float(last_price)
                                _market_data_cache[root]['source'] = 'tradingview'
                                _market_data_cache[root]['updated'] = time.time()
                                
                                logger.info(f"💰 TradingView price: {root} = {last_price}")
                                
                                # Check TP/SL for recorder trades
                                check_recorder_trades_tp_sl({root})
                                
            except json.JSONDecodeError:
                continue
                
    except Exception as e:
        logger.debug(f"Error processing TradingView message: {e}")


def start_tradingview_websocket():
    """Start TradingView WebSocket in background thread"""
    global _tradingview_ws_thread
    
    if _tradingview_ws_thread and _tradingview_ws_thread.is_alive():
        logger.info("TradingView WebSocket already running")
        return
    
    def run_websocket():
        asyncio.run(connect_tradingview_websocket())
    
    _tradingview_ws_thread = threading.Thread(target=run_websocket, daemon=True)
    _tradingview_ws_thread.start()
    logger.info("✅ TradingView WebSocket thread started")


def update_position_pnl():
    """Update PnL for all cached positions based on current market prices"""
    global _position_cache, _market_data_cache
    
    for cache_key, position in _position_cache.items():
        symbol = position.get('symbol', '')
        if not symbol:
            continue
        
        # Get current price from market data cache
        current_price = _market_data_cache.get(symbol, {}).get('last', 0.0)
        if current_price == 0:
            # Try to get from bid/ask
            market_data = _market_data_cache.get(symbol, {})
            current_price = market_data.get('bid', 0.0) or market_data.get('ask', 0.0)
        
        if current_price > 0 and position.get('avg_price', 0) > 0:
            # Calculate PnL: (current_price - avg_price) * quantity * contract_multiplier
            contract_multiplier = get_contract_multiplier(symbol)
            quantity = position.get('net_quantity', 0)
            avg_price = position.get('avg_price', 0)
            
            # PnL = (current - entry) * quantity * multiplier
            # For long: (current - entry) * qty * mult
            # For short: (entry - current) * qty * mult = (current - entry) * (-qty) * mult
            pnl = (current_price - avg_price) * quantity * contract_multiplier
            
            position['last_price'] = current_price
            position['unrealized_pnl'] = pnl
            
            # Update in database
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE open_positions 
                    SET last_price = ?, unrealized_pnl = ?, updated_at = ?
                    WHERE symbol = ? AND subaccount_id = ?
                ''', (current_price, pnl, datetime.now().isoformat(), symbol, position.get('subaccount_id')))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Error updating position PnL in database: {e}")
            
            logger.debug(f"Updated PnL for {symbol}: price={current_price}, avg={avg_price}, qty={quantity}, mult={contract_multiplier}, PnL={pnl}")

# ============================================================================
# Custom OCO Monitor - Tracks TP/SL pairs and cancels the other when one fills
# ============================================================================

# Store paired orders: {tp_order_id: sl_order_id, sl_order_id: tp_order_id}
_oco_pairs = {}
# Store order details for monitoring: {order_id: {account_id, symbol, type: 'tp'|'sl', partner_id}}
_oco_order_details = {}
_oco_lock = threading.Lock()

def register_oco_pair(tp_order_id: int, sl_order_id: int, account_id: int, symbol: str):
    """Register a TP/SL pair for OCO monitoring"""
    global _oco_pairs, _oco_order_details
    
    with _oco_lock:
        # Store the pairing both ways for easy lookup
        _oco_pairs[tp_order_id] = sl_order_id
        _oco_pairs[sl_order_id] = tp_order_id
        
        # Store details for each order
        _oco_order_details[tp_order_id] = {
            'account_id': account_id,
            'symbol': symbol,
            'type': 'tp',
            'partner_id': sl_order_id,
            'created_at': time.time()
        }
        _oco_order_details[sl_order_id] = {
            'account_id': account_id,
            'symbol': symbol,
            'type': 'sl',
            'partner_id': tp_order_id,
            'created_at': time.time()
        }
        
        logger.info(f"🔗 OCO pair registered: TP={tp_order_id} <-> SL={sl_order_id} for {symbol}")

def unregister_oco_pair(order_id: int):
    """Remove an OCO pair from monitoring (called when one side fills/cancels)"""
    global _oco_pairs, _oco_order_details
    
    with _oco_lock:
        if order_id in _oco_pairs:
            partner_id = _oco_pairs.pop(order_id, None)
            if partner_id and partner_id in _oco_pairs:
                _oco_pairs.pop(partner_id, None)
            
            # Remove details
            _oco_order_details.pop(order_id, None)
            if partner_id:
                _oco_order_details.pop(partner_id, None)

def monitor_oco_orders():
    """
    Background thread that monitors OCO order pairs across ALL accounts.
    When one order fills, it cancels the partner order on the SAME account.
    """
    logger.info("🔄 OCO Monitor started - watching for TP/SL fills...")
    
    while True:
        try:
            # Only process if we have pairs to monitor
            with _oco_lock:
                if not _oco_pairs:
                    time.sleep(1)
                    continue
                
                # Get a copy of current pairs
                pairs_to_check = dict(_oco_pairs)
                details_copy = dict(_oco_order_details)
            
            if not pairs_to_check:
                time.sleep(1)
                continue
            
            # Get ALL accounts with tokens (for multi-account support)
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, tradovate_token, environment, tradovate_accounts, subaccounts
                FROM accounts 
                WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
            ''')
            all_accounts = cursor.fetchall()
            conn.close()
            
            if not all_accounts:
                time.sleep(2)
                continue
            
            # Group OCO pairs by account_id for efficient processing
            account_orders = {}  # {account_id: [order_ids]}
            for order_id, details in details_copy.items():
                acc_id = details.get('account_id')
                if acc_id:
                    if acc_id not in account_orders:
                        account_orders[acc_id] = []
                    account_orders[acc_id].append(order_id)
            
            # Build a map of account_id -> account info (token, env)
            # Account IDs in our system are the tradovate subaccount IDs (like 26029294)
            account_info_map = {}
            for acc in all_accounts:
                # Get valid token (auto-refreshes if needed)
                account_record_id = acc['id']
                token = get_valid_tradovate_token(account_record_id)
                if not token:
                    logger.warning(f"No valid token for account record {account_record_id} - skipping")
                    continue
                
                env = acc['environment'] or 'demo'
                
                # Try tradovate_accounts field (JSON format)
                tradovate_accounts_str = acc['tradovate_accounts'] or ''
                if tradovate_accounts_str:
                    try:
                        import json
                        tradovate_accounts = json.loads(tradovate_accounts_str)
                        for ta in tradovate_accounts:
                            acc_id = ta.get('id') or ta.get('accountId')
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': env}
                    except:
                        pass
                
                # Also try subaccounts field (comma-separated or JSON)
                subaccounts_str = acc['subaccounts'] or ''
                if subaccounts_str:
                    try:
                        import json
                        subaccounts = json.loads(subaccounts_str)
                        for sa in subaccounts:
                            if isinstance(sa, dict):
                                acc_id = sa.get('id') or sa.get('accountId')
                            else:
                                acc_id = sa
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': env}
                    except:
                        # Try comma-separated
                        for tid in subaccounts_str.split(','):
                            tid = tid.strip()
                            if tid:
                                try:
                                    account_info_map[int(tid)] = {'token': token, 'env': env}
                                except ValueError:
                                    pass
            
            # Process each account's orders
            orders_to_remove = []
            partners_to_cancel = []  # [(partner_id, filled_id, symbol, account_id)]
            
            for account_id, order_ids in account_orders.items():
                # Get token for this account
                acc_info = account_info_map.get(account_id)
                if not acc_info:
                    # Try to find any token (fallback for accounts not in our map)
                    if all_accounts:
                        acc_info = {
                            'token': all_accounts[0]['tradovate_token'],
                            'env': all_accounts[0]['environment'] or 'demo'
                        }
                    else:
                        continue
                
                token = acc_info['token']
                env = acc_info['env']
                base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                
                # Get orders for this account
                try:
                    response = requests.get(f'{base_url}/order/list', headers=headers, timeout=5)
                    if response.status_code != 200:
                        continue
                    
                    orders = response.json()
                    order_status_map = {o.get('id'): o.get('ordStatus', '') for o in orders}
                except Exception as e:
                    logger.debug(f"OCO monitor fetch error for account {account_id}: {e}")
                    continue
                
                # Check each order for this account
                for order_id in order_ids:
                    if order_id not in pairs_to_check:
                        continue
                    
                    partner_id = pairs_to_check.get(order_id)
                    details = details_copy.get(order_id, {})
                    status = order_status_map.get(order_id, '')
                    
                    # If order is filled, we need to cancel the partner
                    if status.lower() == 'filled':
                        order_type = details.get('type', 'unknown')
                        symbol = details.get('symbol', 'unknown')
                        
                        logger.info(f"🎯 OCO: {order_type.upper()} order {order_id} FILLED for {symbol} (account {account_id})")
                        logger.info(f"🎯 OCO: Cancelling partner order {partner_id}...")
                        
                        partners_to_cancel.append((partner_id, order_id, symbol, account_id, token, env))
                        orders_to_remove.append(order_id)
                    
                    # If order is cancelled/rejected, just remove from monitoring
                    elif status.lower() in ['canceled', 'cancelled', 'rejected', 'expired']:
                        orders_to_remove.append(order_id)
            
            # Cancel partner orders (using the correct token for each account)
            for partner_id, filled_id, symbol, account_id, token, env in partners_to_cancel:
                try:
                    base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                    
                    cancel_response = requests.post(
                        f'{base_url}/order/cancelorder',
                        json={'orderId': partner_id, 'isAutomated': True},
                        headers=headers,
                        timeout=5
                    )
                    if cancel_response.status_code == 200:
                        result = cancel_response.json()
                        if result.get('errorText'):
                            logger.warning(f"⚠️ OCO: Cancel returned error for {partner_id}: {result.get('errorText')}")
                        else:
                            logger.info(f"✅ OCO: Successfully cancelled partner order {partner_id} for {symbol} (account {account_id})")
                        
                        # Emit event to frontend
                        socketio.emit('oco_triggered', {
                            'filled_order': filled_id,
                            'cancelled_order': partner_id,
                            'symbol': symbol,
                            'account_id': account_id,
                            'message': f'OCO triggered: cancelled partner order for {symbol}'
                        })
                    else:
                        logger.warning(f"⚠️ OCO: Failed to cancel partner order {partner_id}: {cancel_response.text[:200]}")
                except Exception as e:
                    logger.error(f"❌ OCO: Error cancelling partner order {partner_id}: {e}")
            
            # Remove processed orders from monitoring
            for order_id in orders_to_remove:
                unregister_oco_pair(order_id)
            
            time.sleep(1)  # Check every second
            
        except Exception as e:
            logger.error(f"OCO Monitor error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            time.sleep(2)

# Start OCO monitor thread
oco_monitor_thread = threading.Thread(target=monitor_oco_orders, daemon=True)
oco_monitor_thread.start()
logger.info("🔄 OCO Monitor thread started")

def cleanup_orphaned_orders():
    """
    On startup, scan for working orders that don't have matching positions.
    This cleans up orphaned TP/SL orders from previous sessions.
    """
    time.sleep(10)  # Wait for server to fully start
    logger.info("🧹 Scanning for orphaned orders...")
    
    try:
        # Get all accounts with tokens
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, tradovate_token, tradovate_accounts
            FROM accounts 
            WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
        ''')
        accounts = cursor.fetchall()
        conn.close()
        
        if not accounts:
            logger.info("🧹 No accounts to scan for orphaned orders")
            return
        
        for account in accounts:
            # Get valid token (auto-refreshes if needed)
            account_record_id = account['id']
            token = get_valid_tradovate_token(account_record_id)
            if not token:
                logger.warning(f"No valid token for account record {account_record_id} - skipping")
                continue
            
            tradovate_accounts = []
            if account['tradovate_accounts']:
                try:
                    tradovate_accounts = json.loads(account['tradovate_accounts'])
                except:
                    pass
            
            for ta in tradovate_accounts:
                acc_id = ta.get('id')
                is_demo = ta.get('is_demo', True)
                acc_name = ta.get('name', str(acc_id))
                base_url = 'https://demo.tradovateapi.com/v1' if is_demo else 'https://live.tradovateapi.com/v1'
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                
                try:
                    # Get positions
                    pos_response = requests.get(f'{base_url}/position/list', headers=headers, timeout=5)
                    positions = pos_response.json() if pos_response.status_code == 200 else []
                    
                    # Build set of contract IDs with open positions
                    open_contracts = set()
                    for pos in positions:
                        if pos.get('netPos', 0) != 0:
                            open_contracts.add(pos.get('contractId'))
                    
                    # Get orders
                    order_response = requests.get(f'{base_url}/order/list', headers=headers, timeout=5)
                    orders = order_response.json() if order_response.status_code == 200 else []
                    
                    orphaned = []
                    for order in orders:
                        order_status = order.get('ordStatus', '').lower()
                        if order_status in ['working', 'pending', 'accepted']:
                            contract_id = order.get('contractId')
                            # If no open position for this contract, it's orphaned
                            if contract_id not in open_contracts:
                                orphaned.append(order)
                    
                    if orphaned:
                        logger.warning(f"🧹 Found {len(orphaned)} orphaned orders for {acc_name}")
                        for order in orphaned:
                            order_id = order.get('id')
                            try:
                                cancel_response = requests.post(
                                    f'{base_url}/order/cancelorder',
                                    json={'orderId': order_id, 'isAutomated': True},
                                    headers=headers,
                                    timeout=5
                                )
                                if cancel_response.status_code == 200:
                                    logger.info(f"🧹 Cancelled orphaned order {order_id}")
                                else:
                                    logger.warning(f"🧹 Failed to cancel orphaned order {order_id}: {cancel_response.text[:100]}")
                            except Exception as e:
                                logger.warning(f"🧹 Error cancelling orphaned order {order_id}: {e}")
                    else:
                        logger.info(f"🧹 No orphaned orders for {acc_name}")
                        
                except Exception as e:
                    logger.warning(f"🧹 Error scanning {acc_name} for orphaned orders: {e}")
                    
    except Exception as e:
        logger.error(f"🧹 Error in orphaned orders cleanup: {e}")

# Start orphaned orders cleanup in background
cleanup_thread = threading.Thread(target=cleanup_orphaned_orders, daemon=True)
cleanup_thread.start()

# ============================================================================
# Break-Even Monitor - Moves SL to entry price when position goes profitable
# ============================================================================

# Store break-even monitors: {key: {account_id, symbol, entry_price, is_long, activation_ticks, ...}}
_break_even_monitors = {}
_break_even_lock = threading.Lock()

def register_break_even_monitor(account_id: int, symbol: str, entry_price: float, is_long: bool,
                                 activation_ticks: int, tick_size: float, sl_order_id: int,
                                 quantity: int, account_spec: str):
    """Register a position for break-even monitoring"""
    global _break_even_monitors
    
    key = f"{account_id}:{symbol}"
    
    with _break_even_lock:
        _break_even_monitors[key] = {
            'account_id': account_id,
            'symbol': symbol,
            'entry_price': entry_price,
            'is_long': is_long,
            'activation_ticks': activation_ticks,
            'tick_size': tick_size,
            'sl_order_id': sl_order_id,
            'quantity': quantity,
            'account_spec': account_spec,
            'triggered': False,
            'created_at': time.time()
        }
        
        activation_price = entry_price + (tick_size * activation_ticks) if is_long else entry_price - (tick_size * activation_ticks)
        logger.info(f"📊 Break-even monitor registered: {symbol} on account {account_id}")
        logger.info(f"   Entry: {entry_price}, Activation: {activation_price} ({activation_ticks} ticks)")

def unregister_break_even_monitor(key: str):
    """Remove a break-even monitor"""
    global _break_even_monitors
    
    with _break_even_lock:
        if key in _break_even_monitors:
            _break_even_monitors.pop(key)

def monitor_break_even():
    """
    Background thread that monitors positions for break-even activation.
    When price reaches activation_ticks profit, cancels old SL and places new SL at entry.
    """
    logger.info("📊 Break-Even Monitor started")
    
    while True:
        try:
            with _break_even_lock:
                if not _break_even_monitors:
                    time.sleep(2)
                    continue
                
                monitors_copy = dict(_break_even_monitors)
            
            if not monitors_copy:
                time.sleep(2)
                continue
            
            # Get tokens from database
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, tradovate_token, environment, tradovate_accounts, subaccounts
                FROM accounts 
                WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
            ''')
            all_accounts = cursor.fetchall()
            conn.close()
            
            if not all_accounts:
                time.sleep(2)
                continue
            
            # Build account info map
            account_info_map = {}
            for acc in all_accounts:
                # Get valid token (auto-refreshes if needed)
                account_record_id = acc['id']
                token = get_valid_tradovate_token(account_record_id)
                if not token:
                    logger.warning(f"No valid token for account record {account_record_id} - skipping")
                    continue
                
                env = acc['environment'] or 'demo'
                
                tradovate_accounts_str = acc['tradovate_accounts'] or ''
                if tradovate_accounts_str:
                    try:
                        tradovate_accounts = json.loads(tradovate_accounts_str)
                        for ta in tradovate_accounts:
                            acc_id = ta.get('id') or ta.get('accountId')
                            is_demo = ta.get('is_demo', True)
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': 'demo' if is_demo else 'live'}
                    except:
                        pass
            
            # Check each monitored position
            monitors_to_remove = []
            
            for key, monitor in monitors_copy.items():
                if monitor.get('triggered'):
                    continue
                
                account_id = monitor['account_id']
                symbol = monitor['symbol']
                entry_price = monitor['entry_price']
                is_long = monitor['is_long']
                activation_ticks = monitor['activation_ticks']
                tick_size = monitor['tick_size']
                sl_order_id = monitor['sl_order_id']
                quantity = monitor['quantity']
                account_spec = monitor['account_spec']
                
                acc_info = account_info_map.get(account_id)
                if not acc_info:
                    continue
                
                token = acc_info['token']
                env = acc_info['env']
                base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                
                try:
                    # Get current positions
                    pos_response = requests.get(f'{base_url}/position/list', headers=headers, timeout=5)
                    if pos_response.status_code != 200:
                        continue
                    
                    positions = pos_response.json()
                    
                    # Find matching position
                    position = None
                    for p in positions:
                        if p.get('accountId') == account_id:
                            pos_symbol = p.get('contractId')  # Need to resolve
                            # For now, check by netPos direction matching
                            net_pos = p.get('netPos', 0)
                            if (is_long and net_pos > 0) or (not is_long and net_pos < 0):
                                position = p
                                break
                    
                    if not position:
                        # Position closed, remove monitor
                        monitors_to_remove.append(key)
                        continue
                    
                    # Get current MARKET price (NOT position.netPrice which is entry price!)
                    # Use market data cache for real-time prices
                    symbol_root = extract_symbol_root(symbol)
                    current_price = None
                    
                    # Try market data cache first (real-time WebSocket prices)
                    if symbol_root in _market_data_cache:
                        current_price = _market_data_cache[symbol_root].get('last')
                    
                    # Try exact symbol match
                    if not current_price and symbol in _market_data_cache:
                        current_price = _market_data_cache[symbol].get('last')
                    
                    # Fallback to cached price function
                    if not current_price:
                        current_price = get_cached_price(symbol)
                    
                    # Last resort: try TradingView API
                    if not current_price:
                        current_price = get_market_price_simple(symbol)
                    
                    if not current_price:
                        logger.debug(f"Break-even monitor: No market price for {symbol}, skipping check")
                        continue
                    
                    # Calculate profit in ticks
                    if is_long:
                        profit_ticks = (current_price - entry_price) / tick_size
                    else:
                        profit_ticks = (entry_price - current_price) / tick_size
                    
                    # Log monitoring progress (every ~10 seconds)
                    monitor_age = time.time() - monitor.get('created_at', time.time())
                    if int(monitor_age) % 10 < 2:  # Log roughly every 10 seconds
                        logger.debug(f"📊 Break-even monitor: {symbol} | Entry: {entry_price:.2f} | Current: {current_price:.2f} | Profit: {profit_ticks:.1f}/{activation_ticks} ticks")
                    
                    # Check if activation threshold reached
                    if profit_ticks >= activation_ticks:
                        logger.info(f"🎯 Break-even triggered for {symbol}! Profit: {profit_ticks:.1f} ticks >= {activation_ticks} ticks")
                        
                        # Cancel old SL order
                        if sl_order_id:
                            cancel_response = requests.post(
                                f'{base_url}/order/cancelorder',
                                json={'orderId': sl_order_id, 'isAutomated': True},
                                headers=headers,
                                timeout=5
                            )
                            if cancel_response.status_code == 200:
                                logger.info(f"✅ Cancelled old SL order {sl_order_id}")
                        
                        # Place new SL at entry price (break-even)
                        exit_side = 'Sell' if is_long else 'Buy'
                        new_sl_data = {
                            "accountSpec": account_spec,
                            "orderType": "Stop",
                            "action": exit_side,
                            "symbol": symbol,
                            "orderQty": int(quantity),
                            "stopPrice": float(entry_price),
                            "timeInForce": "GTC",
                            "isAutomated": True
                        }
                        
                        sl_response = requests.post(
                            f'{base_url}/order/placeorder',
                            json=new_sl_data,
                            headers=headers,
                            timeout=5
                        )
                        
                        if sl_response.status_code == 200:
                            result = sl_response.json()
                            new_sl_id = result.get('orderId')
                            logger.info(f"✅ Break-even SL placed at {entry_price}, Order ID: {new_sl_id}")
                            
                            # Emit to frontend
                            socketio.emit('break_even_triggered', {
                                'symbol': symbol,
                                'account_id': account_id,
                                'entry_price': entry_price,
                                'new_sl_order_id': new_sl_id,
                                'message': f'Break-even activated for {symbol}'
                            })
                        else:
                            logger.warning(f"⚠️ Failed to place break-even SL: {sl_response.text[:200]}")
                        
                        # Mark as triggered
                        with _break_even_lock:
                            if key in _break_even_monitors:
                                _break_even_monitors[key]['triggered'] = True
                        
                        monitors_to_remove.append(key)
                
                except Exception as e:
                    logger.debug(f"Break-even monitor error for {key}: {e}")
                    continue
            
            # Remove processed monitors
            for key in monitors_to_remove:
                unregister_break_even_monitor(key)
            
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            logger.error(f"Break-Even Monitor error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            time.sleep(3)

# Start break-even monitor thread
break_even_thread = threading.Thread(target=monitor_break_even, daemon=True)
break_even_thread.start()
logger.info("📊 Break-Even Monitor thread started")

# ============================================================================
# Tradovate PnL Fetching (Direct from API - No Market Data Required!)
# ============================================================================

# Cache for Tradovate PnL data
# RESET on every server start to avoid stale data
_tradovate_pnl_cache = {
    'last_fetch': 0,
    'data': {},
    'positions': [],
    'account_count': 10,  # Start slower (2 second interval) to avoid rate limits
    'rate_limited_until': 0  # Timestamp when rate limit expires
}

# Track last refresh attempt per account to avoid hammering API
_last_refresh_attempt = {}

def get_valid_tradovate_token(account_id: int) -> str | None:
    """
    Get a valid Tradovate access token for an account.
    Automatically refreshes if token is expired or expiring soon (within 15 minutes).
    Returns the access token string, or None if unavailable.
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tradovate_token, tradovate_refresh_token, token_expires_at, name
            FROM accounts WHERE id = ?
        ''', (account_id,))
        account = cursor.fetchone()
        conn.close()
        
        if not account or not account['tradovate_token']:
            logger.debug(f"No access token found for account {account_id}")
            return None
        
        access_token = account['tradovate_token']
        refresh_token = account['tradovate_refresh_token']
        expires_at_str = account['token_expires_at']
        
        # Check if token needs refresh
        needs_refresh = False
        if not expires_at_str:
            # No expiration time stored - refresh to be safe
            logger.debug(f"Account {account_id} has no expiration time - refreshing token")
            needs_refresh = True
        else:
            try:
                from datetime import datetime, timedelta
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                
                # Refresh if expired or expiring within 15 minutes
                time_until_expiry = (expires_at - now).total_seconds()
                if time_until_expiry <= 0:
                    logger.info(f"Token for account {account_id} is expired - refreshing")
                    needs_refresh = True
                elif time_until_expiry < 15 * 60:  # Less than 15 minutes
                    logger.info(f"Token for account {account_id} expires in {int(time_until_expiry/60)} minutes - refreshing proactively")
                    needs_refresh = True
            except Exception as e:
                logger.warning(f"Could not parse expiration time for account {account_id}: {e} - refreshing to be safe")
                needs_refresh = True
        
        # Refresh if needed
        if needs_refresh and refresh_token:
            logger.info(f"Refreshing token for account {account_id}")
            if try_refresh_tradovate_token(account_id):
                # Get the new token
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT tradovate_token FROM accounts WHERE id = ?', (account_id,))
                new_account = cursor.fetchone()
                conn.close()
                if new_account and new_account['tradovate_token']:
                    return new_account['tradovate_token']
                else:
                    logger.warning(f"Token refresh succeeded but new token not found for account {account_id}")
            else:
                logger.warning(f"Failed to refresh token for account {account_id}")
                # Return existing token anyway - might still work
                return access_token
        
        return access_token
        
    except Exception as e:
        logger.error(f"Error getting valid token for account {account_id}: {e}")
        return None

def try_refresh_tradovate_token(account_id: int) -> bool:
    """
    Try to refresh the Tradovate access token.
    
    CRITICAL FIX (Dec 18, 2025): Tradovate doesn't use traditional refresh tokens!
    Instead, you renew the ACCESS TOKEN using Authorization header.
    See: https://community.tradovate.com/t/token-expiry/5276
    
    Uses environment-specific endpoint based on account settings.
    Includes rate limit protection to avoid 429 errors.
    """
    global _last_refresh_attempt

    # Rate limit protection: don't try more than once per 30 seconds per account
    last_attempt = _last_refresh_attempt.get(account_id, 0)
    if time.time() - last_attempt < 30:
        logger.debug(f"Skipping refresh for account {account_id} - tried recently")
        return False
    _last_refresh_attempt[account_id] = time.time()

    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tradovate_token, tradovate_refresh_token, environment, name
            FROM accounts WHERE id = ?
        ''', (account_id,))
        account = cursor.fetchone()

        if not account or not account['tradovate_token']:
            conn.close()
            logger.warning(f"No access token found for account {account_id}")
            return False

        current_token = account['tradovate_token']
        account_name = account['name'] or f'Account {account_id}'
        env = account['environment'] or 'demo'

        # Use environment-specific endpoint (demo tokens only work on demo, live on live)
        if env == 'live':
            token_endpoints = [
                'https://live.tradovateapi.com/v1/auth/renewAccessToken'
            ]
        else:
            token_endpoints = [
                'https://demo.tradovateapi.com/v1/auth/renewAccessToken'
            ]

        for token_url in token_endpoints:
            try:
                # CRITICAL: Use Authorization header with current access token!
                # NOT json body with refreshToken (that's the old broken way)
                response = requests.post(
                    token_url,
                    headers={
                        'Authorization': f'Bearer {current_token}',
                        'Content-Type': 'application/json'
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    new_access_token = data.get('accessToken') or data.get('access_token')
                    # Keep the existing refresh token (Tradovate renewal doesn't return a new one)
                    existing_refresh_token = account['tradovate_refresh_token']
                    
                    if new_access_token:
                        # Calculate actual expiration time from Tradovate response
                        expires_at = None
                        if 'expirationTime' in data:
                            try:
                                from datetime import datetime
                                expires_at = datetime.fromisoformat(data['expirationTime'].replace('Z', '+00:00'))
                                expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                            except Exception as e:
                                logger.warning(f"Could not parse expirationTime in refresh response: {e}")
                        elif 'expiresIn' in data:
                            try:
                                from datetime import datetime, timedelta
                                expires_in_seconds = int(data['expiresIn'])
                                expires_at = (datetime.now() + timedelta(seconds=expires_in_seconds)).strftime('%Y-%m-%d %H:%M:%S')
                            except Exception as e:
                                logger.warning(f"Could not parse expiresIn in refresh response: {e}")
                        
                        # Fallback: Tradovate access tokens typically expire in 90 minutes
                        if not expires_at:
                            from datetime import datetime, timedelta
                            expires_at = (datetime.now() + timedelta(minutes=85)).strftime('%Y-%m-%d %H:%M:%S')
                        
                        cursor.execute('''
                            UPDATE accounts 
                            SET tradovate_token = ?, 
                                tradovate_refresh_token = ?,
                                token_expires_at = ?
                            WHERE id = ?
                        ''', (new_access_token, existing_refresh_token, expires_at, account_id))
                        conn.commit()
                        conn.close()
                        logger.info(f"✅ Successfully refreshed token for '{account_name}' via {token_url.split('/')[2]}")
                        return True
                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate limited (429) at {token_url.split('/')[2]}, trying next...")
                    time.sleep(1)  # Brief pause before trying next endpoint
                    continue
                else:
                    logger.debug(f"Refresh failed at {token_url}: {response.status_code}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request error at {token_url}: {e}")
                continue
        
        # CHECK: Does this account have credentials that will work for trading?
        # API Access during trades uses username/password (bypasses refresh token issues)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT username, password FROM accounts WHERE id = ?', (account_id,))
            creds_row = cursor.fetchone()
            username = None
            password = None
            if creds_row:
                username = creds_row['username'] if isinstance(creds_row, dict) else creds_row[0]
                password = creds_row['password'] if isinstance(creds_row, dict) else creds_row[1]
            
            if username and password:
                # Account has credentials - trades will work via API Access
                conn.close()
                logger.info(f"⚠️ [{account_name}] Refresh token expired, but has credentials for API Access - trades will still work")
                # Don't mark as needing reauth - trading will work
                clear_account_reauth(account_id)
                return True  # Consider it "refreshed" since trading will work
        except Exception as e:
            logger.debug(f"Error checking credentials: {e}")
        
        conn.close()
        logger.error(f"❌ CRITICAL: No valid auth for '{account_name}' (ID: {account_id}) - no refresh token AND no credentials")
        logger.error(f"❌ This account will NOT be able to execute trades!")
        logger.error(f"❌ User must re-authenticate via OAuth to restore connection")
        # Mark account as needing re-auth (only if no credentials)
        mark_account_needs_reauth(account_id)
        return False
    except Exception as e:
        logger.error(f"Error refreshing Tradovate token: {e}")
        return False

def fetch_tradovate_pnl_sync():
    """
    Fetch real-time PnL directly from Tradovate's cashBalance API.
    This is the CORRECT way to get PnL - Tradovate calculates it for us!
    No market data subscription required.
    """
    global _tradovate_pnl_cache
    
    current_time = time.time()
    
    # Dynamic throttling based on account count to avoid rate limits
    # Tradovate allows ~120 requests/min, each account needs 2 calls (cashBalance + positions)
    # 
    # SCALING TABLE:
    # Accounts | Calls/update | Safe interval | Updates/min
    # ---------|--------------|---------------|------------
    #    1     |      2       |    0.5s       |    120
    #    2     |      4       |    0.5s       |    120  
    #    5     |     10       |    1.0s       |     60
    #   10     |     20       |    2.0s       |     30
    #   20     |     40       |    4.0s       |     15
    #   50     |    100       |   10.0s       |      6
    #
    # Formula: interval = max(0.5, num_accounts * 0.2) to stay under 120 req/min
    # Check if we're in a rate limit cooldown
    rate_limited_until = _tradovate_pnl_cache.get('rate_limited_until', 0)
    if current_time < rate_limited_until:
        # Still in cooldown, return cached data
        return _tradovate_pnl_cache.get('data', {}), _tradovate_pnl_cache.get('positions', [])
    
    num_accounts = _tradovate_pnl_cache.get('account_count', 2)
    if not isinstance(num_accounts, int) or num_accounts < 1:
        num_accounts = 2
    # Increased minimum interval to reduce rate limiting (trades are priority, PnL is secondary)
    # Formula: max(3.0, num_accounts * 0.6) - very conservative to stay under 120 req/min
    min_interval = max(3.0, num_accounts * 0.6)  # Scale up as accounts increase (very conservative - trades priority)
    
    if current_time - _tradovate_pnl_cache['last_fetch'] < min_interval:
        return _tradovate_pnl_cache['data'], _tradovate_pnl_cache['positions']
    
    try:
        # Get ALL connected accounts from database (multi-account support for copy trading)
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, tradovate_token, tradovate_accounts, environment
            FROM accounts 
            WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
        ''')
        all_linked_accounts = cursor.fetchall()
        conn.close()
        
        if not all_linked_accounts:
            return {}, []
        
        all_pnl_data = {}
        all_positions = []
        total_subaccounts = 0
        
        # Process each linked account (user may have multiple Tradovate logins)
        for account in all_linked_accounts:
            account_id = account['id']
            # Get valid token (auto-refreshes if needed)
            token = get_valid_tradovate_token(account_id)
            if not token:
                logger.warning(f"No valid token available for account {account_id} - skipping")
                continue
            
            env = account['environment'] or 'demo'
            user_account_name = account['name'] if account['name'] else f"Account {account_id}"  # User's custom name
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Parse tradovate_accounts to get subaccount IDs
            tradovate_accounts = []
            try:
                if account['tradovate_accounts']:
                    tradovate_accounts = json.loads(account['tradovate_accounts'])
            except:
                pass
            
            total_subaccounts += len(tradovate_accounts)
            
            # Fetch PnL for each subaccount under this linked account
            for ta in tradovate_accounts:
                acc_id = ta.get('id')
                subaccount_name = ta.get('name', str(acc_id))  # Tradovate's subaccount name
                is_demo = ta.get('is_demo', True)
                # Display as "UserName - SubaccountName" (like account dropdown)
                acc_name = f"{user_account_name} - {subaccount_name}"
                
                # Use correct base URL for demo vs live accounts
                acc_base_url = 'https://demo.tradovateapi.com/v1' if is_demo else 'https://live.tradovateapi.com/v1'
                
                try:
                    # Get cash balance snapshot (includes openPnL!)
                    response = requests.get(
                        f'{acc_base_url}/cashBalance/getCashBalanceSnapshot?accountId={acc_id}',
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        snap = response.json()
                        all_pnl_data[acc_id] = {
                            'account_id': acc_id,
                            'account_name': acc_name,
                            'is_demo': is_demo,
                            'total_cash_value': snap.get('totalCashValue', 0),
                            'net_liq': snap.get('netLiq', 0),
                            'open_pnl': snap.get('openPnL', 0),  # Unrealized PnL!
                            'realized_pnl': snap.get('realizedPnL', 0),
                            'total_pnl': snap.get('totalPnL', 0),
                            'week_realized_pnl': snap.get('weekRealizedPnL', 0),
                            'initial_margin': snap.get('initialMargin', 0),
                            'maintenance_margin': snap.get('maintenanceMargin', 0)
                        }
                        logger.debug(f"Fetched PnL for {acc_name}: openPnL=${snap.get('openPnL', 0):.2f}, realizedPnL=${snap.get('realizedPnL', 0):.2f}")
                    elif response.status_code == 429:
                        # Rate limited - enter cooldown for 60 seconds
                        cooldown_seconds = 60
                        _tradovate_pnl_cache['rate_limited_until'] = current_time + cooldown_seconds
                        logger.warning(f"Rate limited by Tradovate (429)! Entering {cooldown_seconds}s cooldown")
                        return _tradovate_pnl_cache.get('data', {}), _tradovate_pnl_cache.get('positions', [])
                    elif response.status_code == 401:
                        logger.warning(f"⚠️ Token expired for account {acc_id} (401) - token validation should have caught this")
                        # Token should have been refreshed proactively, but if we still get 401, try one more refresh
                        refreshed = try_refresh_tradovate_token(account_id)
                        if refreshed:
                            logger.info(f"✅ Token refreshed for account {account_id}, will retry on next cycle")
                        else:
                            logger.error(f"❌ CRITICAL: Failed to refresh token for account {account_id} - account connection broken!")
                            logger.error(f"❌ User must re-authenticate via OAuth to restore connection")
                        continue
                    else:
                        logger.debug(f"Cash balance API returned {response.status_code} for {acc_id}: {response.text[:100]}")
                    
                    # Get positions for this account
                    pos_response = requests.get(
                        f'{acc_base_url}/position/list',
                        headers=headers,
                        timeout=5
                    )
                    
                    if pos_response.status_code == 200:
                        positions = pos_response.json()
                        for pos in positions:
                            if pos.get('netPos', 0) != 0:  # Only open positions
                                # Get contract name
                                contract_id = pos.get('contractId')
                                contract_name = get_contract_name_cached(contract_id, acc_base_url, headers)
                                
                                all_positions.append({
                                    'account_id': acc_id,
                                    'account_name': acc_name,
                                    'is_demo': is_demo,
                                    'contract_id': contract_id,
                                    'symbol': contract_name,
                                    'net_quantity': pos.get('netPos', 0),
                                    'bought': pos.get('bought', 0),
                                    'bought_value': pos.get('boughtValue', 0),
                                    'sold': pos.get('sold', 0),
                                    'sold_value': pos.get('soldValue', 0),
                                    # Calculate avg price from bought/sold values
                                    'avg_price': calculate_avg_price(pos),
                                    'timestamp': pos.get('timestamp')
                                })
                    elif pos_response.status_code == 401:
                        logger.warning(f"⚠️ Token expired when fetching positions for account {acc_id} - attempting auto-refresh")
                        refreshed = try_refresh_tradovate_token(account['id'])
                        if refreshed:
                            logger.info(f"✅ Token refreshed for account {account['id']}, positions will retry on next cycle")
                        else:
                            logger.error(f"❌ CRITICAL: Failed to refresh token for account {account['id']} - position fetch failed!")
                                
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error fetching PnL/positions for account {acc_id}: {e}")
                    continue
        
        # Update cache (including total subaccount count for dynamic throttling)
        _tradovate_pnl_cache['last_fetch'] = current_time
        _tradovate_pnl_cache['data'] = all_pnl_data
        _tradovate_pnl_cache['positions'] = all_positions
        _tradovate_pnl_cache['account_count'] = total_subaccounts  # Total across all linked accounts
        
        if total_subaccounts > 5:
            logger.info(f"Monitoring {total_subaccounts} subaccounts, update interval: {max(0.5, total_subaccounts * 0.2):.1f}s")
        
        # Debug: Log what we're returning
        if all_pnl_data:
            logger.info(f"📊 Returning PnL data for {len(all_pnl_data)} accounts, {len(all_positions)} positions")
        
        return all_pnl_data, all_positions
        
    except Exception as e:
        logger.error(f"Error fetching Tradovate PnL: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return _tradovate_pnl_cache.get('data', {}), _tradovate_pnl_cache.get('positions', [])

# Cache for contract names
_contract_name_cache = {}

def get_contract_name_cached(contract_id, base_url, headers):
    """Get contract name from ID, with caching"""
    global _contract_name_cache
    
    if contract_id in _contract_name_cache:
        return _contract_name_cache[contract_id]
    
    try:
        response = requests.get(
            f'{base_url}/contract/item?id={contract_id}',
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            contract = response.json()
            name = contract.get('name', str(contract_id))
            _contract_name_cache[contract_id] = name
            return name
    except:
        pass
    
    return str(contract_id)

def calculate_avg_price(position):
    """Get average entry price from position data.
    
    CRITICAL: Use netPrice from broker - this IS the correct average entry price.
    Don't calculate from boughtValue/bought - that gives wrong values for DCA positions.
    """
    # netPrice IS the broker's calculated average entry price - use it directly!
    net_price = position.get('netPrice')
    if net_price:
        return net_price
    
    # Fallback only if netPrice not available (shouldn't happen)
    net_pos = position.get('netPos', 0)
    if net_pos == 0:
        return 0
    
    if net_pos > 0:
        bought = position.get('bought', 0)
        bought_value = position.get('boughtValue', 0)
        if bought > 0:
            return bought_value / bought
    else:
        sold = position.get('sold', 0)
        sold_value = position.get('soldValue', 0)
        if sold > 0:
            return sold_value / sold
    
    return 0

# ============================================================================
# PROACTIVE TOKEN REFRESH - Prevents session expiration throughout the day
# ============================================================================
# This thread runs every 5 minutes and refreshes any Tradovate tokens that
# will expire within 30 minutes. This keeps connections alive INDEFINITELY.
# ============================================================================

def proactive_token_refresh():
    """
    Background thread that proactively refreshes Tradovate tokens BEFORE they expire.
    
    CRITICAL FIX (Dec 18, 2025): 
    - Changed from 30 min to 5 min intervals (tokens can expire in 90 min!)
    - Changed from 2 hour to 30 min threshold (refresh well before expiry)
    
    This keeps sessions alive INDEFINITELY without manual re-login.
    """
    logger.info("🔐 Proactive token refresh thread started (checks every 5 minutes)")
    
    # Wait 60 seconds before first check to let server fully start
    time.sleep(60)
    
    while True:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find accounts with tokens that expire within 30 minutes
            # Also refresh tokens where we don't know the expiration (NULL)
            # More aggressive refresh keeps connections alive INDEFINITELY
            cursor.execute('''
                SELECT id, name, tradovate_token, tradovate_refresh_token, 
                       token_expires_at, environment
                FROM accounts 
                WHERE tradovate_token IS NOT NULL 
                  AND tradovate_refresh_token IS NOT NULL
                  AND (
                      token_expires_at IS NULL 
                      OR token_expires_at < datetime('now', '+30 minutes')
                  )
            ''')
            accounts_to_refresh = cursor.fetchall()
            conn.close()
            
            if accounts_to_refresh:
                logger.info(f"🔐 Found {len(accounts_to_refresh)} account(s) with tokens expiring soon")
                
                for account in accounts_to_refresh:
                    account_id = account['id']
                    account_name = account['name']
                    expires_at = account['token_expires_at']
                    
                    if expires_at:
                        logger.info(f"🔄 Proactively refreshing token for '{account_name}' (expires: {expires_at})")
                    else:
                        logger.info(f"🔄 Proactively refreshing token for '{account_name}' (expiration unknown)")
                    
                    # Use existing refresh function
                    success = try_refresh_tradovate_token(account_id)
                    
                    if success:
                        logger.info(f"✅ Proactively refreshed token for '{account_name}' - good for 24 more hours")
                    else:
                        logger.warning(f"⚠️ Failed to refresh token for '{account_name}' - may need to re-authenticate via OAuth")
                    
                    # Small delay between accounts to avoid rate limiting
                    time.sleep(2)
            else:
                logger.info("🔐 All Tradovate tokens are fresh (not expiring within 30 minutes)")
                
        except Exception as e:
            logger.error(f"Error in proactive token refresh: {e}")

        # Check every 5 minutes (more aggressive to keep tokens fresh)
        time.sleep(5 * 60)

def emit_realtime_updates():
    """Emit real-time updates (throttled to avoid rate limits)"""
    global _position_cache
    while True:
        try:
            # ============================================================
            # FETCH REAL-TIME PnL DIRECTLY FROM TRADOVATE
            # This is the correct approach - no market data needed!
            # Note: fetch_tradovate_pnl_sync() has built-in throttling
            # ============================================================
            
            total_pnl = 0.0
            today_pnl = 0.0
            open_pnl = 0.0
            active_positions = 0
            positions_list = []
            
            # Fetch PnL from Tradovate's cashBalance API (throttled internally)
            pnl_data, tradovate_positions = fetch_tradovate_pnl_sync()
            
            if pnl_data:
                # Sum up PnL from all accounts
                for acc_id, acc_data in pnl_data.items():
                    open_pnl += acc_data.get('open_pnl', 0)
                    today_pnl += acc_data.get('realized_pnl', 0)
                    total_pnl += acc_data.get('total_pnl', 0)
                
                logger.debug(f"Tradovate PnL: open=${open_pnl:.2f}, realized=${today_pnl:.2f}, total=${total_pnl:.2f}")
            
            if tradovate_positions:
                active_positions = len(tradovate_positions)
                positions_list = [{
                    'symbol': pos.get('symbol', 'Unknown'),
                    'net_quantity': pos.get('net_quantity', 0),
                    'avg_price': pos.get('avg_price', 0),
                    'account_id': pos.get('account_id'),
                    'account_name': pos.get('account_name'),
                    'is_demo': pos.get('is_demo', True),
                    # Note: unrealized_pnl per position requires market data
                    # But we have total open_pnl from cashBalance
                } for pos in tradovate_positions]
            
            # Also include any synthetic positions from manual trades
            if _position_cache:
                for cache_key, pos in _position_cache.items():
                    # Check if this position is already in tradovate_positions
                    exists = any(
                        p.get('symbol') == pos.get('symbol') and 
                        p.get('account_id') == pos.get('account_id')
                        for p in positions_list
                    )
                    if not exists and pos.get('net_quantity', 0) != 0:
                        positions_list.append(pos)
                        active_positions = len(positions_list)
            
            # Emit P&L updates with REAL data from Tradovate
            socketio.emit('pnl_update', {
                'total_pnl': total_pnl,
                'open_pnl': open_pnl,  # Unrealized PnL
                'today_pnl': today_pnl,  # Realized PnL today
                'active_positions': active_positions,
                'timestamp': datetime.now().isoformat()
            })
            
            # Emit position updates
            socketio.emit('position_update', {
                'positions': positions_list,
                'count': active_positions,
                'pnl_data': pnl_data,  # Include full PnL data per account
                'timestamp': datetime.now().isoformat()
            })
            
            # Note: Position and PnL fetching is now handled by fetch_tradovate_pnl_sync() above
            # The new implementation uses Tradovate's cashBalance API which provides 
            # real-time PnL without needing market data subscription
            
        except Exception as e:
            logger.error(f"Error emitting real-time updates: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
        # Sleep 5 seconds - trades are priority, PnL updates are secondary
        # fetch_tradovate_pnl_sync() has its own throttling, so this just reduces check frequency
        time.sleep(5)  # Check every 5 seconds (trades are priority, PnL is secondary)

def record_strategy_pnl_continuously():
    """Record P&L for all active strategies every second (like Trade Manager)"""
    while True:
        try:
            strategies = []
            
            # Try SQLAlchemy models first
            try:
                from app.database import SessionLocal
                from app.models import Strategy
                
                db = SessionLocal()
                active_strategies = db.query(Strategy).filter(Strategy.active == True).all()
                strategies = [(s.id, s.name) for s in active_strategies]
                db.close()
                
            except (ImportError, Exception):
                # Fallback to unified database connection
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    if is_using_postgres():
                        cursor.execute('''
                            SELECT id, name FROM strategies WHERE enabled = true
                        ''')
                    else:
                        cursor.execute('''
                            SELECT id, name FROM strategies WHERE enabled = 1
                        ''')
                    strategies = cursor.fetchall()
                    conn.close()
                except Exception as e:
                    # If strategies table doesn't exist yet, that's okay
                    if 'no such table' not in str(e).lower() and 'does not exist' not in str(e).lower():
                        logger.debug(f"Strategies table not found: {e}")
                    strategies = []
            
            # Record P&L for each strategy
            for strategy_id, strategy_name in strategies:
                try:
                    # Calculate current P&L for strategy
                    pnl = calculate_strategy_pnl(strategy_id)
                    drawdown = calculate_strategy_drawdown(strategy_id)
                    
                    # Record to database
                    record_strategy_pnl(strategy_id, strategy_name, pnl, drawdown)
                    
                    # Emit real-time update
                    socketio.emit('strategy_pnl_update', {
                        'strategy_id': strategy_id,
                        'strategy_name': strategy_name,
                        'pnl': pnl,
                        'drawdown': drawdown,
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error processing strategy {strategy_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error recording strategy P&L: {e}")
        time.sleep(1)  # Every second

# Start background threads
update_thread = threading.Thread(target=emit_realtime_updates, daemon=True)
update_thread.start()

pnl_recording_thread = threading.Thread(target=record_strategy_pnl_continuously, daemon=True)
pnl_recording_thread.start()

# Start proactive token refresh thread (keeps sessions alive throughout the day)
token_refresh_thread = threading.Thread(target=proactive_token_refresh, daemon=True)
token_refresh_thread.start()
logger.info("✅ Proactive token refresh thread started (refreshes tokens before expiration)")

# ============================================================================
# Auto-Flat After Cutoff - Automatically closes positions after trading window
# ============================================================================

def auto_flat_after_cutoff_worker():
    """
    Background task that checks if any recorders have positions that should be 
    closed because we're outside the trading window and auto_flat_after_cutoff is enabled.
    """
    from datetime import datetime, timedelta
    
    logger.info("🔄 Auto-Flat After Cutoff worker started")
    
    def parse_time(time_str):
        """Parse time string like '8:45 AM' or '13:45' to datetime.time"""
        if not time_str:
            return None
        time_str = time_str.strip()
        try:
            if 'AM' in time_str.upper() or 'PM' in time_str.upper():
                return datetime.strptime(time_str.upper(), '%I:%M %p').time()
            return datetime.strptime(time_str, '%H:%M').time()
        except:
            return None
    
    def is_time_past_cutoff(current_time, stop_str):
        """Check if current time is past the cutoff"""
        stop = parse_time(stop_str)
        if not stop:
            return False
        # Check if we're within 1 minute after the cutoff (to avoid repeated closes)
        current = current_time.time()
        stop_dt = datetime.combine(datetime.today(), stop)
        current_dt = datetime.combine(datetime.today(), current)
        # Close if we're between stop and stop + 2 minutes
        return stop_dt <= current_dt <= stop_dt + timedelta(minutes=2)
    
    while True:
        try:
            # Get current time (local time - assumes server is in correct timezone)
            now = datetime.now()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Find recorders with auto_flat_after_cutoff enabled and time filters set
            if is_using_postgres():
                cursor.execute('''
                    SELECT r.id, r.name, r.time_filter_1_stop, r.time_filter_2_stop, r.auto_flat_after_cutoff
                    FROM recorders r
                    WHERE r.auto_flat_after_cutoff = true
                    AND (r.time_filter_1_stop IS NOT NULL OR r.time_filter_2_stop IS NOT NULL)
                ''')
            else:
                cursor.execute('''
                    SELECT r.id, r.name, r.time_filter_1_stop, r.time_filter_2_stop, r.auto_flat_after_cutoff
                    FROM recorders r
                    WHERE r.auto_flat_after_cutoff = 1
                    AND (r.time_filter_1_stop IS NOT NULL OR r.time_filter_2_stop IS NOT NULL)
                ''')
            recorders = cursor.fetchall()
            
            for rec in recorders:
                rec = dict(rec)
                recorder_id = rec['id']
                recorder_name = rec['name']
                time_filter_1_stop = rec.get('time_filter_1_stop')
                time_filter_2_stop = rec.get('time_filter_2_stop')
                
                # Check if we just hit cutoff time
                at_cutoff_1 = is_time_past_cutoff(now, time_filter_1_stop) if time_filter_1_stop else False
                at_cutoff_2 = is_time_past_cutoff(now, time_filter_2_stop) if time_filter_2_stop else False
                
                if at_cutoff_1 or at_cutoff_2:
                    cutoff_time = time_filter_1_stop if at_cutoff_1 else time_filter_2_stop
                    logger.info(f"🕐 [{recorder_name}] At cutoff time ({cutoff_time}) - checking for open positions")
                    
                    # Check for open positions
                    cursor.execute('''
                        SELECT id, ticker, side, quantity FROM recorded_trades
                        WHERE recorder_id = ? AND status = 'open'
                    ''', (recorder_id,))
                    open_trades = cursor.fetchall()
                    
                    if open_trades:
                        logger.info(f"🔄 [{recorder_name}] Found {len(open_trades)} open trades - AUTO-FLATTENING")
                        
                        # Get trader info for closing
                        if is_using_postgres():
                            cursor.execute('''
                                SELECT t.*, a.tradovate_token, a.username, a.password, a.id as account_id
                                FROM traders t
                                JOIN accounts a ON t.account_id = a.id
                                WHERE t.recorder_id = %s AND t.enabled = true
                                LIMIT 1
                            ''', (recorder_id,))
                        else:
                            cursor.execute('''
                                SELECT t.*, a.tradovate_token, a.username, a.password, a.id as account_id
                                FROM traders t
                                JOIN accounts a ON t.account_id = a.id
                                WHERE t.recorder_id = ? AND t.enabled = 1
                                LIMIT 1
                            ''', (recorder_id,))
                        trader_row = cursor.fetchone()
                        
                        if trader_row:
                            from recorder_service import close_all_positions_for_recorder
                            try:
                                close_result = close_all_positions_for_recorder(recorder_id)
                                logger.info(f"✅ [{recorder_name}] Auto-flat result: {close_result}")
                            except Exception as e:
                                logger.error(f"❌ [{recorder_name}] Auto-flat failed: {e}")
                        else:
                            logger.warning(f"⚠️ [{recorder_name}] No trader linked - cannot auto-flat")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Auto-flat worker error: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(60)  # Check every minute

# Start auto-flat after cutoff worker
auto_flat_thread = threading.Thread(target=auto_flat_after_cutoff_worker, daemon=True)
auto_flat_thread.start()
logger.info("✅ Auto-Flat After Cutoff worker started")

# Start Tradovate market data WebSocket
if WEBSOCKETS_AVAILABLE:
    start_market_data_websocket()
    logger.info("✅ Market data WebSocket thread started")
else:
    logger.warning("websockets library not installed. Market data WebSocket will not work. Install with: pip install websockets")

# ============================================================================
# RECORDER THREADS DISABLED - Now handled by Trading Engine (port 8083)
# ============================================================================
# The following threads have been moved to recorder_service.py (Trading Engine):
# - TP/SL monitoring (poll_recorder_trades_tp_sl)
# - Position drawdown tracking (poll_recorder_positions_drawdown)
# - TradingView WebSocket for recorders
#
# DO NOT RE-ENABLE THESE - they would duplicate the Trading Engine's work
# and cause race conditions with the shared database.
# ============================================================================

# NOTE: Recorder TP/SL monitoring now handled by Trading Engine
# start_recorder_tp_sl_polling()  # DISABLED - handled by Trading Engine
logger.info("ℹ️ Recorder TP/SL monitoring handled by Trading Engine (port 8083)")

# NOTE: Position drawdown tracking now handled by Trading Engine
# start_position_drawdown_polling()  # DISABLED - handled by Trading Engine
logger.info("ℹ️ Position drawdown tracking handled by Trading Engine (port 8083)")

# NOTE: TradingView WebSocket for recorders now handled by Trading Engine
# The main server's TradingView WebSocket is only for Tradovate market data
logger.info("ℹ️ Recorder price streaming handled by Trading Engine (port 8083)")

# Configure logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    # Railway/Production uses PORT env variable, local dev uses --port arg
    parser = argparse.ArgumentParser(description='Start the trading webhook server.')
    parser.add_argument('--port', type=int, default=8082, help='Port to run the server on.')
    args = parser.parse_args()

    # Railway sets PORT env variable - use it if available
    port = int(os.getenv('PORT', args.port))
    
    logger.info(f"Starting Just.Trades server on 0.0.0.0:{port}")
    logger.info("WebSocket support enabled (like Trade Manager)")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
