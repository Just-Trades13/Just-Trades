"""
Neon Database Utility - Read Replica / Backup Connection

This provides a secondary PostgreSQL connection to Neon for:
- Read-heavy queries (dashboards, reports, analytics)
- Fallback if Railway PostgreSQL has issues
- Reducing load on primary database

Usage:
    from neon_db import get_neon_connection, query_neon

    # Simple query
    results = query_neon("SELECT * FROM users WHERE id = %s", (user_id,))

    # Or get a connection directly
    conn = get_neon_connection()
    cursor = conn.cursor()
    ...
    conn.close()
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Neon connection string (pooler endpoint for better connection handling)
NEON_DATABASE_URL = os.getenv(
    'NEON_DATABASE_URL',
    'postgresql://neondb_owner:npg_D5j0fBQevGZd@ep-small-hall-ae3vmr2h-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require'
)

_neon_pool = None


def get_neon_connection(use_dict_cursor: bool = True):
    """
    Get a connection to the Neon database.

    Args:
        use_dict_cursor: If True, returns rows as dictionaries instead of tuples

    Returns:
        psycopg2 connection object
    """
    try:
        conn = psycopg2.connect(NEON_DATABASE_URL)
        if use_dict_cursor:
            conn.cursor_factory = RealDictCursor
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Neon: {e}")
        raise


def query_neon(sql: str, params: tuple = None, fetch_one: bool = False):
    """
    Execute a read query on Neon database.

    Args:
        sql: SQL query string with %s placeholders
        params: Tuple of parameters
        fetch_one: If True, returns single row; otherwise returns all rows

    Returns:
        Query results as list of dicts (or single dict if fetch_one=True)
        Returns None on error
    """
    conn = None
    try:
        conn = get_neon_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)

        if fetch_one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()

        return result

    except Exception as e:
        logger.error(f"Neon query failed: {e}")
        return None

    finally:
        if conn:
            conn.close()


def check_neon_connection():
    """
    Test the Neon connection and return status.

    Returns:
        dict with 'connected', 'version', 'latency_ms', 'error'
    """
    import time

    result = {
        'connected': False,
        'version': None,
        'latency_ms': None,
        'error': None
    }

    try:
        start = time.time()
        conn = get_neon_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        latency = (time.time() - start) * 1000

        result['connected'] = True
        result['version'] = version['version'] if isinstance(version, dict) else version[0]
        result['latency_ms'] = round(latency, 2)

        conn.close()

    except Exception as e:
        result['error'] = str(e)

    return result


def get_table_counts():
    """
    Get row counts for main tables (useful for sync verification).

    Returns:
        dict of table_name -> row_count
    """
    tables = ['users', 'accounts', 'traders', 'recorders', 'recorded_trades',
              'recorder_positions', 'open_positions', 'webhooks']

    counts = {}
    conn = None

    try:
        conn = get_neon_connection()
        cursor = conn.cursor()

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                row = cursor.fetchone()
                counts[table] = row['count'] if isinstance(row, dict) else row[0]
            except:
                counts[table] = -1  # Table doesn't exist or error

    except Exception as e:
        logger.error(f"Failed to get table counts: {e}")

    finally:
        if conn:
            conn.close()

    return counts


# Quick test when run directly
if __name__ == "__main__":
    print("Testing Neon connection...")
    status = check_neon_connection()

    if status['connected']:
        print(f"✅ Connected to Neon ({status['latency_ms']}ms)")
        print(f"   Version: {status['version'][:50]}...")
        print("\nTable counts:")
        for table, count in get_table_counts().items():
            print(f"   {table}: {count}")
    else:
        print(f"❌ Connection failed: {status['error']}")
