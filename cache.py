"""
Caching Module (Redis + Memory Fallback)
========================================
Provides token caching and general caching functionality.

Features:
- Redis for production (distributed, persistent)
- In-memory fallback for development
- Automatic TTL management
- Thread-safe operations

Configuration:
    Set REDIS_URL environment variable to enable Redis:
    export REDIS_URL=redis://localhost:6379/0
    
    Or for Redis Cloud/production:
    export REDIS_URL=redis://user:password@host:port/0

Usage:
    from cache import token_cache, cache
    
    # Token caching (with automatic expiry)
    token_cache.set_token(account_id, access_token, expires_in=3600)
    token = token_cache.get_token(account_id)
    
    # General caching
    cache.set("my_key", {"data": "value"}, ttl=300)
    data = cache.get("my_key")
"""

import os
import json
import time
import threading
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger('cache')

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL')

# Redis client (lazy loaded)
_redis_client = None
_redis_available = None


def _get_redis():
    """Get Redis client, return None if not available."""
    global _redis_client, _redis_available
    
    if _redis_available is False:
        return None
    
    if _redis_client is not None:
        return _redis_client
    
    if not REDIS_URL:
        _redis_available = False
        logger.info("📦 Cache: Using in-memory (set REDIS_URL for Redis)")
        return None
    
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()  # Test connection
        _redis_available = True
        logger.info(f"✅ Cache: Connected to Redis")
        return _redis_client
    except ImportError:
        logger.warning("redis package not installed - using in-memory cache")
        _redis_available = False
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - using in-memory cache")
        _redis_available = False
        return None


class MemoryCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if expired or missing."""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expires_at'] and time.time() > entry['expires_at']:
                del self._cache[key]
                return None
            
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with optional TTL (seconds)."""
        with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
    
    def delete(self, key: str):
        """Delete key from cache."""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
    
    def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern (simple * wildcard only)."""
        with self._lock:
            if pattern == "*":
                return list(self._cache.keys())
            
            prefix = pattern.rstrip("*")
            return [k for k in self._cache.keys() if k.startswith(prefix)]
    
    def cleanup_expired(self):
        """Remove expired entries."""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._cache.items() 
                      if v['expires_at'] and now > v['expires_at']]
            for k in expired:
                del self._cache[k]
        return len(expired)


class Cache:
    """
    Unified cache interface - uses Redis if available, memory otherwise.
    """
    
    def __init__(self, prefix: str = "jt"):
        self.prefix = prefix
        self._memory = MemoryCache()
    
    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        full_key = self._key(key)
        
        redis_client = _get_redis()
        if redis_client:
            try:
                value = redis_client.get(full_key)
                if value:
                    return json.loads(value)
                return None
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        return self._memory.get(full_key)
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with optional TTL (seconds)."""
        full_key = self._key(key)
        
        redis_client = _get_redis()
        if redis_client:
            try:
                serialized = json.dumps(value)
                if ttl:
                    redis_client.setex(full_key, ttl, serialized)
                else:
                    redis_client.set(full_key, serialized)
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
        
        self._memory.set(full_key, value, ttl)
    
    def delete(self, key: str):
        """Delete key from cache."""
        full_key = self._key(key)
        
        redis_client = _get_redis()
        if redis_client:
            try:
                redis_client.delete(full_key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")
        
        self._memory.delete(full_key)
    
    def clear_prefix(self, prefix: str):
        """Clear all keys with given prefix."""
        full_prefix = self._key(prefix)
        
        redis_client = _get_redis()
        if redis_client:
            try:
                keys = redis_client.keys(f"{full_prefix}*")
                if keys:
                    redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        for key in self._memory.keys(f"{full_prefix}*"):
            self._memory.delete(key)


class TokenCache:
    """
    Specialized cache for OAuth tokens.
    
    Features:
    - Automatic expiry tracking
    - Token refresh detection
    - Multi-account support
    """
    
    def __init__(self):
        self._cache = Cache(prefix="jt:token")
    
    def set_token(self, account_id: int, token_data: dict, expires_in: int = 3600):
        """
        Cache token for an account.
        
        Args:
            account_id: The account ID
            token_data: Dict with 'access_token', optionally 'refresh_token'
            expires_in: Seconds until expiry (default 1 hour)
        """
        key = f"account:{account_id}"
        
        data = {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'expires_at': time.time() + expires_in,
            'cached_at': time.time()
        }
        
        # Cache with slightly shorter TTL to refresh before expiry
        cache_ttl = max(expires_in - 300, 60)  # Expire 5 min early, minimum 1 min
        self._cache.set(key, data, ttl=cache_ttl)
        
        logger.debug(f"Cached token for account {account_id}, expires in {expires_in}s")
    
    def get_token(self, account_id: int) -> Optional[str]:
        """Get cached access token for account, or None if expired/missing."""
        key = f"account:{account_id}"
        data = self._cache.get(key)
        
        if not data:
            return None
        
        # Check if expired (with 60s buffer)
        if time.time() > data.get('expires_at', 0) - 60:
            logger.debug(f"Token for account {account_id} is expired")
            return None
        
        return data.get('access_token')
    
    def get_token_data(self, account_id: int) -> Optional[dict]:
        """Get full token data including refresh token."""
        key = f"account:{account_id}"
        return self._cache.get(key)
    
    def is_expiring_soon(self, account_id: int, threshold_seconds: int = 300) -> bool:
        """Check if token is expiring within threshold."""
        key = f"account:{account_id}"
        data = self._cache.get(key)
        
        if not data:
            return True  # No token = needs refresh
        
        return time.time() > data.get('expires_at', 0) - threshold_seconds
    
    def invalidate(self, account_id: int):
        """Remove token from cache (force re-auth)."""
        key = f"account:{account_id}"
        self._cache.delete(key)
        logger.debug(f"Invalidated token cache for account {account_id}")
    
    def clear_all(self):
        """Clear all cached tokens."""
        self._cache.clear_prefix("account:")
        logger.info("Cleared all cached tokens")
    
    def get_accounts_expiring_soon(self, threshold_seconds: int = 300) -> list:
        """Get list of account IDs with tokens expiring soon."""
        # This is a bit inefficient without Redis SCAN, but works
        expiring = []
        
        redis_client = _get_redis()
        if redis_client:
            try:
                keys = redis_client.keys("jt:token:account:*")
                for key in keys:
                    account_id = int(key.split(":")[-1])
                    if self.is_expiring_soon(account_id, threshold_seconds):
                        expiring.append(account_id)
            except Exception as e:
                logger.warning(f"Error scanning Redis keys: {e}")
        
        return expiring


class PositionCache:
    """
    Cache for broker positions to reduce API calls.
    Short TTL since positions change frequently.
    """
    
    def __init__(self):
        self._cache = Cache(prefix="jt:pos")
    
    def set_positions(self, account_id: int, positions: list, ttl: int = 5):
        """Cache positions for an account (default 5s TTL)."""
        key = f"account:{account_id}"
        self._cache.set(key, {
            'positions': positions,
            'cached_at': time.time()
        }, ttl=ttl)
    
    def get_positions(self, account_id: int) -> Optional[list]:
        """Get cached positions, or None if stale/missing."""
        key = f"account:{account_id}"
        data = self._cache.get(key)
        return data.get('positions') if data else None
    
    def invalidate(self, account_id: int):
        """Invalidate position cache (after trade)."""
        key = f"account:{account_id}"
        self._cache.delete(key)


# Global instances
cache = Cache()
token_cache = TokenCache()
position_cache = PositionCache()


def get_cache_status() -> dict:
    """Get cache status for health checks."""
    redis_client = _get_redis()
    
    return {
        'backend': 'redis' if redis_client else 'memory',
        'redis_url': REDIS_URL[:20] + '...' if REDIS_URL and len(REDIS_URL) > 20 else REDIS_URL,
        'connected': redis_client is not None
    }


# Log configuration
logger.info(f"✅ Cache module loaded")

