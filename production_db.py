"""
Production Database Module
==========================
Supports SQLite (development) and PostgreSQL (production)
with connection pooling, Redis caching, and proper transactions.

Usage:
    from production_db import db
    
    # Get connection (automatically uses pool)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts")
        
    # Cache position data
    db.cache_position(recorder_id, position_data)
    position = db.get_cached_position(recorder_id)
"""

import os
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger('production_db')

# Check if we're in production mode
PRODUCTION_MODE = os.getenv('DATABASE_URL') is not None
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DATABASE_URL = os.getenv('DATABASE_URL', 'just_trades.db')

# Import production libraries if available
try:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    logger.info("psycopg2 not installed - using SQLite mode")

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.info("redis not installed - caching disabled")


class DatabaseManager:
    """
    Production-ready database manager with:
    - Connection pooling (PostgreSQL)
    - Redis caching for positions
    - Automatic failover to SQLite
    - Thread-safe operations
    """
    
    def __init__(self):
        self.pool = None
        self.redis_client = None
        self.sqlite_path = 'just_trades.db'
        self.is_postgres = False
        
        self._init_database()
        self._init_redis()
    
    def _init_database(self):
        """Initialize database connection pool."""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and HAS_POSTGRES and database_url.startswith('postgres'):
            try:
                # PostgreSQL with connection pool
                # Handle Heroku-style postgres:// URLs
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
                self.pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    dsn=database_url
                )
                self.is_postgres = True
                logger.info("✅ PostgreSQL connection pool initialized (2-20 connections)")
            except Exception as e:
                logger.error(f"❌ PostgreSQL init failed: {e} - falling back to SQLite")
                self.is_postgres = False
        else:
            logger.info("📁 Using SQLite database (set DATABASE_URL for PostgreSQL)")
            self.is_postgres = False
    
    def _init_redis(self):
        """Initialize Redis connection for caching."""
        if not HAS_REDIS:
            return
            
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                self.redis_client.ping()
                logger.info("✅ Redis connected for position caching")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e} - caching disabled")
                self.redis_client = None
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection from the pool.
        Automatically returns connection to pool when done.
        
        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn = None
        try:
            if self.is_postgres and self.pool:
                conn = self.pool.getconn()
                conn.autocommit = False
                yield conn
                conn.commit()
            else:
                # SQLite fallback
                conn = sqlite3.connect(self.sqlite_path, timeout=30)
                conn.row_factory = sqlite3.Row
                yield conn
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                if self.is_postgres and self.pool:
                    self.pool.putconn(conn)
                else:
                    conn.close()
    
    def execute(self, query: str, params: tuple = None, fetch: str = None) -> Any:
        """
        Execute a query with automatic connection handling.
        
        Args:
            query: SQL query (use %s for PostgreSQL, ? for SQLite)
            params: Query parameters
            fetch: 'one', 'all', or None for no fetch
            
        Returns:
            Query results or None
        """
        # Convert SQLite ? placeholders to PostgreSQL %s if needed
        if self.is_postgres:
            query = query.replace('?', '%s')
        
        with self.get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()
            
            cursor.execute(query, params or ())
            
            if fetch == 'one':
                row = cursor.fetchone()
                return dict(row) if row else None
            elif fetch == 'all':
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                return cursor.lastrowid if not self.is_postgres else None
    
    # ==========================================
    # REDIS POSITION CACHE
    # ==========================================
    
    def cache_position(self, recorder_id: int, position_data: Dict[str, Any], ttl: int = 300):
        """
        Cache position data in Redis.
        
        Args:
            recorder_id: The recorder ID
            position_data: Position data dict (qty, avg_price, side, etc.)
            ttl: Time to live in seconds (default 5 minutes)
        """
        if not self.redis_client:
            return False
            
        try:
            key = f"position:{recorder_id}"
            position_data['cached_at'] = datetime.utcnow().isoformat()
            self.redis_client.setex(key, ttl, json.dumps(position_data))
            return True
        except Exception as e:
            logger.warning(f"Redis cache_position failed: {e}")
            return False
    
    def get_cached_position(self, recorder_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached position data from Redis.
        
        Returns:
            Position dict or None if not cached/expired
        """
        if not self.redis_client:
            return None
            
        try:
            key = f"position:{recorder_id}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Redis get_cached_position failed: {e}")
            return None
    
    def invalidate_position_cache(self, recorder_id: int):
        """Invalidate cached position (call after trade execution)."""
        if not self.redis_client:
            return
            
        try:
            key = f"position:{recorder_id}"
            self.redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis invalidate failed: {e}")
    
    # ==========================================
    # BROKER POSITION CACHE (Real-time from WebSocket)
    # ==========================================
    
    def set_broker_position(self, account_id: int, symbol: str, qty: int, avg_price: float):
        """
        Set broker position from WebSocket update.
        This is the source of truth for position data.
        """
        if not self.redis_client:
            return False
            
        try:
            key = f"broker_position:{account_id}:{symbol}"
            data = {
                'qty': qty,
                'avg_price': avg_price,
                'updated_at': datetime.utcnow().isoformat()
            }
            # Broker positions don't expire - they're updated by WebSocket
            self.redis_client.set(key, json.dumps(data))
            return True
        except Exception as e:
            logger.warning(f"Redis set_broker_position failed: {e}")
            return False
    
    def get_broker_position(self, account_id: int, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get broker position (source of truth).
        
        Returns:
            {'qty': int, 'avg_price': float, 'updated_at': str} or None
        """
        if not self.redis_client:
            return None
            
        try:
            key = f"broker_position:{account_id}:{symbol}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Redis get_broker_position failed: {e}")
            return None
    
    # ==========================================
    # WEBHOOK QUEUE (Redis List)
    # ==========================================
    
    def queue_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Add webhook to processing queue.
        Webhooks are processed in order by worker.
        """
        if not self.redis_client:
            return False
            
        try:
            webhook_data['queued_at'] = datetime.utcnow().isoformat()
            self.redis_client.rpush('webhook_queue', json.dumps(webhook_data))
            return True
        except Exception as e:
            logger.error(f"Failed to queue webhook: {e}")
            return False
    
    def dequeue_webhook(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get next webhook from queue (blocking).
        
        Args:
            timeout: How long to wait for a webhook (seconds)
            
        Returns:
            Webhook data dict or None if timeout
        """
        if not self.redis_client:
            return None
            
        try:
            result = self.redis_client.blpop('webhook_queue', timeout=timeout)
            if result:
                _, data = result
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue webhook: {e}")
            return None
    
    def get_queue_length(self) -> int:
        """Get number of webhooks waiting in queue."""
        if not self.redis_client:
            return 0
            
        try:
            return self.redis_client.llen('webhook_queue')
        except:
            return 0
    
    # ==========================================
    # HEALTH CHECK
    # ==========================================
    
    def health_check(self) -> Dict[str, Any]:
        """Check database and cache health."""
        status = {
            'database': 'unknown',
            'database_type': 'postgresql' if self.is_postgres else 'sqlite',
            'redis': 'unknown',
            'webhook_queue_length': 0
        }
        
        # Check database
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                status['database'] = 'healthy'
        except Exception as e:
            status['database'] = f'error: {e}'
        
        # Check Redis
        if self.redis_client:
            try:
                self.redis_client.ping()
                status['redis'] = 'healthy'
                status['webhook_queue_length'] = self.get_queue_length()
            except Exception as e:
                status['redis'] = f'error: {e}'
        else:
            status['redis'] = 'not configured'
        
        return status
    
    def close(self):
        """Close all connections."""
        if self.pool:
            self.pool.closeall()
        if self.redis_client:
            self.redis_client.close()


# Global database instance
db = DatabaseManager()


# ==========================================
# MIGRATION HELPERS
# ==========================================

def migrate_sqlite_to_postgres(sqlite_path: str, postgres_url: str):
    """
    Migrate data from SQLite to PostgreSQL.
    
    Usage:
        migrate_sqlite_to_postgres('just_trades.db', 'postgresql://user:pass@host/db')
    """
    import psycopg2
    from psycopg2.extras import execute_values
    
    logger.info("Starting SQLite → PostgreSQL migration...")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    pg_conn = psycopg2.connect(postgres_url)
    pg_cursor = pg_conn.cursor()
    
    # Tables to migrate
    tables = ['accounts', 'traders', 'recorders', 'recorded_trades', 'recorder_positions', 'signals']
    
    for table in tables:
        try:
            # Get data from SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                logger.info(f"  {table}: 0 rows (skipping)")
                continue
            
            # Get column names
            columns = [desc[0] for desc in sqlite_cursor.description]
            
            # Insert into PostgreSQL
            placeholders = ','.join(['%s'] * len(columns))
            cols_str = ','.join(columns)
            
            for row in rows:
                try:
                    pg_cursor.execute(
                        f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                        tuple(row)
                    )
                except Exception as e:
                    logger.warning(f"  Row insert error in {table}: {e}")
            
            pg_conn.commit()
            logger.info(f"  {table}: {len(rows)} rows migrated")
            
        except Exception as e:
            logger.error(f"  {table}: Error - {e}")
            pg_conn.rollback()
    
    sqlite_conn.close()
    pg_conn.close()
    logger.info("Migration complete!")


if __name__ == '__main__':
    # Test the database manager
    logging.basicConfig(level=logging.INFO)
    
    print("Database Health Check:")
    print(json.dumps(db.health_check(), indent=2))
