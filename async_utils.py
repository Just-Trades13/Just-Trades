"""
Async Utilities Module
======================
Provides safe async execution in sync contexts (like Flask).

The Problem:
- Flask is synchronous, but Tradovate API uses asyncio
- Calling asyncio.run() multiple times causes "Event loop is closed" errors
- Mixing sync/async code leads to deadlocks and crashes

The Solution:
- Dedicated background thread with persistent event loop
- Safe wrappers that never close the loop
- Thread-safe execution from sync code

Usage:
    from async_utils import run_async, async_executor
    
    # Run any async function from sync code
    result = run_async(some_async_function(args))
    
    # Or use decorator
    @async_executor
    async def my_async_func():
        await something()
    
    # Call decorated function from sync code
    result = my_async_func()  # Runs in background loop
"""

import asyncio
import threading
import logging
import functools
from typing import Any, Callable, Coroutine, TypeVar
from concurrent.futures import Future, ThreadPoolExecutor
import atexit

logger = logging.getLogger('async_utils')

T = TypeVar('T')

# Global event loop thread
_loop: asyncio.AbstractEventLoop = None
_loop_thread: threading.Thread = None
_loop_lock = threading.Lock()
_shutdown = False


def _start_background_loop():
    """Start the background event loop thread."""
    global _loop, _loop_thread
    
    if _loop is not None and _loop.is_running():
        return
    
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return
        
        _loop = asyncio.new_event_loop()
        
        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        
        _loop_thread = threading.Thread(target=run_loop, daemon=True, name="AsyncEventLoop")
        _loop_thread.start()
        logger.info("✅ Background async event loop started")


def _ensure_loop():
    """Ensure background loop is running."""
    global _loop
    if _loop is None or not _loop.is_running():
        _start_background_loop()
    return _loop


def run_async(coro: Coroutine[Any, Any, T], timeout: float = 60.0) -> T:
    """
    Run an async coroutine from sync code safely.
    
    This is the SAFE alternative to asyncio.run() in Flask/sync contexts.
    
    Args:
        coro: The coroutine to run
        timeout: Max seconds to wait (default 60)
        
    Returns:
        The result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If timeout exceeded
        Exception: Any exception from the coroutine
        
    Example:
        async def fetch_data():
            return await api.get_positions()
        
        # In Flask route:
        positions = run_async(fetch_data())
    """
    if _shutdown:
        raise RuntimeError("Async executor is shutting down")

    loop = _ensure_loop()

    # Wrap with asyncio.wait_for so timeout CANCELS the task on the event loop
    # (concurrent.futures.Future.cancel() does NOT cancel running asyncio tasks,
    #  leaving zombie coroutines that accumulate and block the event loop)
    async def _with_timeout():
        return await asyncio.wait_for(coro, timeout=timeout)

    future = asyncio.run_coroutine_threadsafe(_with_timeout(), loop)

    try:
        # Sync timeout slightly longer so asyncio.wait_for fires first and cancels cleanly
        return future.result(timeout=timeout + 5)
    except (asyncio.TimeoutError, TimeoutError):
        future.cancel()
        raise asyncio.TimeoutError(f"Async operation timed out after {timeout}s")


def run_async_nowait(coro: Coroutine) -> asyncio.Future:
    """
    Schedule an async coroutine without waiting for result.
    
    Useful for fire-and-forget operations.
    
    Returns:
        Future that can be checked later
    """
    if _shutdown:
        raise RuntimeError("Async executor is shutting down")
    
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop)


def async_executor(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """
    Decorator that makes an async function callable from sync code.
    
    Example:
        @async_executor
        async def get_positions(account_id: int):
            async with TradovateIntegration() as api:
                return await api.get_positions(account_id)
        
        # Now callable from sync Flask route:
        positions = get_positions(123)  # No await needed!
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        return run_async(coro)
    
    return wrapper


class AsyncBatchExecutor:
    """
    Execute multiple async operations concurrently.
    
    Example:
        executor = AsyncBatchExecutor()
        
        async def fetch_account(account_id):
            return await api.get_account(account_id)
        
        # Add multiple tasks
        executor.add(fetch_account(1))
        executor.add(fetch_account(2))
        executor.add(fetch_account(3))
        
        # Execute all concurrently and get results
        results = executor.run()  # Returns list of results
    """
    
    def __init__(self, timeout: float = 60.0):
        self.tasks = []
        self.timeout = timeout
    
    def add(self, coro: Coroutine):
        """Add a coroutine to the batch."""
        self.tasks.append(coro)
        return self
    
    def run(self) -> list:
        """Execute all tasks concurrently and return results."""
        if not self.tasks:
            return []
        
        async def run_all():
            return await asyncio.gather(*self.tasks, return_exceptions=True)
        
        results = run_async(run_all(), timeout=self.timeout)
        self.tasks = []  # Clear for reuse
        return results


def shutdown_async():
    """Shutdown the background event loop gracefully."""
    global _loop, _loop_thread, _shutdown
    
    _shutdown = True
    
    if _loop is not None:
        _loop.call_soon_threadsafe(_loop.stop)
        if _loop_thread is not None:
            _loop_thread.join(timeout=5)
        logger.info("✅ Background async event loop stopped")


# Register shutdown handler
atexit.register(shutdown_async)

# Start loop on import for immediate availability
_start_background_loop()


# ============================================================================
# SAFE ASYNC CONTEXT MANAGER FOR TRADOVATE
# ============================================================================

class SafeTradovateClient:
    """
    Thread-safe wrapper for TradovateIntegration.
    
    Example:
        client = SafeTradovateClient(demo=True)
        client.set_token(access_token)
        
        # These are all sync calls that internally run async:
        positions = client.get_positions(account_id)
        order = client.place_order(account_id, "Buy", "MNQH6", 1)
    """
    
    def __init__(self, demo: bool = True):
        self.demo = demo
        self._integration = None
        self._token = None
        self._lock = threading.Lock()
    
    def set_token(self, access_token: str):
        """Set the access token."""
        self._token = access_token
    
    def _get_integration(self):
        """Get or create integration instance."""
        if self._integration is None:
            from phantom_scraper.tradovate_integration import TradovateIntegration
            self._integration = TradovateIntegration(demo=self.demo)
            self._integration.access_token = self._token
        return self._integration
    
    def get_positions(self, account_id: int) -> list:
        """Get positions for account."""
        async def _fetch():
            integration = self._get_integration()
            async with integration:
                return await integration.get_positions(account_id=account_id)
        
        with self._lock:
            return run_async(_fetch())
    
    def place_order(self, account_id: int, action: str, symbol: str, quantity: int, **kwargs) -> dict:
        """Place an order."""
        async def _place():
            integration = self._get_integration()
            async with integration:
                return await integration.place_order(
                    account_id=account_id,
                    action=action,
                    symbol=symbol,
                    qty=quantity,
                    **kwargs
                )
        
        with self._lock:
            return run_async(_place())
    
    def get_orders(self, account_id: int) -> list:
        """Get orders for account."""
        async def _fetch():
            integration = self._get_integration()
            async with integration:
                return await integration.get_orders(account_id=account_id)
        
        with self._lock:
            return run_async(_fetch())


# Log startup
logger.info("✅ Async utilities loaded - background event loop ready")

