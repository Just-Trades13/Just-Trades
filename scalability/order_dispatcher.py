"""
Order Dispatcher for Just.Trades Scalability
=============================================

Centralized dispatcher for all broker order actions with:
- Per-account queues (prevents one account from starving others)
- Priority lanes (risk-reducing actions always win)
- Rate limiting with token bucket
- Penalty-aware retry (p-time / p-ticket from Tradovate)
- Coalescing of rapid modifications

Architecture:
    Signal/UI → OrderDispatcher.submit() → Queue → Worker → Broker API
    
Priority Lanes (highest to lowest):
    1. CRITICAL: Flatten, emergency exits, stop losses triggered
    2. HIGH: Close positions, take profits, cancel orders  
    3. NORMAL: New entries, bracket orders
    4. LOW: Modifications, non-critical updates
    5. BACKGROUND: Analytics fetches, reconciliation
    
Usage:
    from scalability.order_dispatcher import get_dispatcher
    
    dispatcher = get_dispatcher()
    
    # Submit an order intent
    task_id = dispatcher.submit(
        account_id=12345,
        action='place_order',
        priority=Priority.NORMAL,
        payload={
            'symbol': 'MESZ4',
            'action': 'Buy',
            'quantity': 1,
            'order_type': 'Market'
        }
    )
    
    # Check status
    status = dispatcher.get_task_status(task_id)
"""

import threading
import time
import logging
import uuid
import heapq
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """
    Order priority levels.
    Lower number = higher priority (for heap ordering).
    """
    CRITICAL = 1   # Flatten, emergency exits, stop loss triggered
    HIGH = 2       # Close positions, take profits, cancels
    NORMAL = 3     # New entries, brackets
    LOW = 4        # Modifications, updates
    BACKGROUND = 5 # Analytics, reconciliation


@dataclass(order=True)
class OrderTask:
    """
    A single order task to be processed.
    Comparable by priority for heap ordering.
    """
    priority: int
    submitted_at: float = field(compare=False)
    task_id: str = field(compare=False)
    account_id: int = field(compare=False)
    action: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)
    
    # Retry tracking
    attempts: int = field(compare=False, default=0)
    max_attempts: int = field(compare=False, default=1)  # NO RETRIES by default (safety)
    
    # Penalty handling (Tradovate p-time/p-ticket)
    p_ticket: Optional[str] = field(compare=False, default=None)
    retry_after: float = field(compare=False, default=0)  # Timestamp when retry is allowed
    
    # Status tracking
    status: str = field(compare=False, default='pending')  # pending, processing, completed, failed
    result: Optional[dict] = field(compare=False, default=None)
    error: Optional[str] = field(compare=False, default=None)
    completed_at: Optional[float] = field(compare=False, default=None)


class TokenBucket:
    """
    Token bucket rate limiter.
    Tokens refill at a steady rate; each request consumes one token.
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, timeout: float = None) -> bool:
        """
        Try to acquire a token.
        
        Args:
            timeout: Max seconds to wait for a token (None = don't wait)
            
        Returns:
            True if token acquired, False if not available
        """
        deadline = time.time() + (timeout or 0)
        
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
            
            if timeout is None or time.time() >= deadline:
                return False
            
            # Wait a bit and try again
            time.sleep(min(0.1, deadline - time.time()))
        
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now
    
    def get_tokens(self) -> float:
        """Get current token count"""
        with self._lock:
            self._refill()
            return self._tokens


class AccountQueue:
    """
    Priority queue for a single account.
    Uses a min-heap ordered by priority.
    """
    
    def __init__(self, account_id: int):
        self.account_id = account_id
        self._heap: List[OrderTask] = []
        self._lock = threading.Lock()
        self._task_map: Dict[str, OrderTask] = {}  # For quick lookup by task_id
        
        # Penalty tracking
        self.penalty_until: float = 0  # Timestamp when penalty expires
        self.penalty_ticket: Optional[str] = None
        
        # Stats
        self.tasks_submitted = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
    
    def push(self, task: OrderTask):
        """Add a task to the queue"""
        with self._lock:
            heapq.heappush(self._heap, task)
            self._task_map[task.task_id] = task
            self.tasks_submitted += 1
    
    def pop(self) -> Optional[OrderTask]:
        """Get highest priority task (None if empty or penalized)"""
        with self._lock:
            # Check if we're in penalty period
            if time.time() < self.penalty_until:
                return None
            
            if not self._heap:
                return None
            
            task = heapq.heappop(self._heap)
            return task
    
    def peek(self) -> Optional[OrderTask]:
        """Look at highest priority task without removing"""
        with self._lock:
            return self._heap[0] if self._heap else None
    
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        with self._lock:
            return len(self._heap) == 0
    
    def size(self) -> int:
        """Get queue size"""
        with self._lock:
            return len(self._heap)
    
    def is_penalized(self) -> bool:
        """Check if account is in penalty period"""
        return time.time() < self.penalty_until
    
    def set_penalty(self, p_time: float, p_ticket: str = None):
        """Set penalty period for this account"""
        self.penalty_until = time.time() + p_time
        self.penalty_ticket = p_ticket
        logger.warning(f"Account {self.account_id} penalized for {p_time}s (ticket: {p_ticket})")
    
    def get_task(self, task_id: str) -> Optional[OrderTask]:
        """Get task by ID"""
        with self._lock:
            return self._task_map.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        with self._lock:
            if task_id in self._task_map:
                task = self._task_map[task_id]
                if task.status == 'pending':
                    task.status = 'cancelled'
                    task.completed_at = time.time()
                    return True
            return False


class OrderDispatcher:
    """
    Central dispatcher for all broker order actions.
    
    Features:
    - Per-account queues (fair scheduling)
    - Priority lanes (risk actions first)
    - Global + per-account rate limiting
    - Penalty-aware retry
    - Task coalescing
    """
    
    def __init__(
        self,
        execute_func: Callable[[OrderTask], dict] = None,
        global_rate_limit: int = 50,  # Requests per second platform-wide
        per_account_rate_limit: int = 5,  # Requests per second per account
        enable_coalescing: bool = True,
        coalesce_window_ms: int = 500,  # Coalesce modifications within this window
    ):
        """
        Initialize the Order Dispatcher.
        
        Args:
            execute_func: Function to execute orders (receives OrderTask, returns dict)
            global_rate_limit: Platform-wide requests per second
            per_account_rate_limit: Per-account requests per second
            enable_coalescing: Whether to coalesce rapid modifications
            coalesce_window_ms: Milliseconds to wait before coalescing
        """
        # Execution function (injected for testability)
        self._execute_func = execute_func
        
        # Per-account queues
        self._account_queues: Dict[int, AccountQueue] = {}
        self._queues_lock = threading.Lock()
        
        # Rate limiters
        self._global_limiter = TokenBucket(
            capacity=global_rate_limit,
            refill_rate=global_rate_limit
        )
        self._account_limiters: Dict[int, TokenBucket] = {}
        self._per_account_rate = per_account_rate_limit
        
        # Coalescing
        self._enable_coalescing = enable_coalescing
        self._coalesce_window = coalesce_window_ms / 1000.0
        self._pending_modifications: Dict[str, OrderTask] = {}  # Key: account_id:order_id
        
        # Worker thread control
        self._running = False
        self._worker_threads: List[threading.Thread] = []
        self._num_workers = 4  # Number of parallel workers
        
        # Task tracking (for status queries)
        self._task_history: Dict[str, OrderTask] = {}
        self._history_lock = threading.Lock()
        self._history_max_size = 10000
        
        # Stats
        self._stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
            'coalesced': 0,
            'rate_limited': 0,
            'penalties': 0,
        }
        
        logger.info(f"📦 OrderDispatcher initialized (global_rate={global_rate_limit}/s, per_account={per_account_rate_limit}/s)")
    
    # ========================================================================
    # QUEUE MANAGEMENT
    # ========================================================================
    
    def _get_account_queue(self, account_id: int) -> AccountQueue:
        """Get or create queue for an account"""
        with self._queues_lock:
            if account_id not in self._account_queues:
                self._account_queues[account_id] = AccountQueue(account_id)
                self._account_limiters[account_id] = TokenBucket(
                    capacity=self._per_account_rate,
                    refill_rate=self._per_account_rate
                )
            return self._account_queues[account_id]
    
    def _get_account_limiter(self, account_id: int) -> TokenBucket:
        """Get rate limiter for an account"""
        self._get_account_queue(account_id)  # Ensure it exists
        return self._account_limiters[account_id]
    
    # ========================================================================
    # TASK SUBMISSION
    # ========================================================================
    
    def submit(
        self,
        account_id: int,
        action: str,
        payload: dict,
        priority: Priority = Priority.NORMAL,
        allow_retry_on_penalty: bool = True,
    ) -> str:
        """
        Submit an order task for execution.
        
        Args:
            account_id: Tradovate account ID
            action: Action type ('place_order', 'cancel_order', 'modify_order', etc.)
            payload: Action-specific data
            priority: Priority level
            allow_retry_on_penalty: Whether to retry if penalized (with p-ticket)
            
        Returns:
            task_id: Unique identifier for tracking
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = OrderTask(
            priority=priority.value,
            submitted_at=time.time(),
            task_id=task_id,
            account_id=account_id,
            action=action,
            payload=payload,
            max_attempts=2 if allow_retry_on_penalty else 1,
        )
        
        # Check for coalescing opportunity (only for modifications)
        if self._enable_coalescing and action == 'modify_order':
            coalesce_key = f"{account_id}:{payload.get('order_id')}"
            if coalesce_key in self._pending_modifications:
                # Replace pending modification with this one
                old_task = self._pending_modifications[coalesce_key]
                old_task.status = 'coalesced'
                self._stats['coalesced'] += 1
                logger.debug(f"Coalesced modification for {coalesce_key}")
            self._pending_modifications[coalesce_key] = task
        
        # Add to account queue
        queue = self._get_account_queue(account_id)
        queue.push(task)
        
        # Track in history
        with self._history_lock:
            self._task_history[task_id] = task
            # Trim history if too large
            if len(self._task_history) > self._history_max_size:
                oldest = sorted(self._task_history.values(), key=lambda t: t.submitted_at)[:1000]
                for t in oldest:
                    del self._task_history[t.task_id]
        
        self._stats['submitted'] += 1
        logger.debug(f"Task submitted: {task_id} - {action} (priority={priority.name}, account={account_id})")
        
        return task_id
    
    def submit_critical(self, account_id: int, action: str, payload: dict) -> str:
        """Submit a critical priority task (flatten, emergency exit)"""
        return self.submit(account_id, action, payload, Priority.CRITICAL)
    
    def submit_high(self, account_id: int, action: str, payload: dict) -> str:
        """Submit a high priority task (close, TP, cancel)"""
        return self.submit(account_id, action, payload, Priority.HIGH)
    
    # ========================================================================
    # TASK STATUS
    # ========================================================================
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get status of a task"""
        with self._history_lock:
            task = self._task_history.get(task_id)
            if not task:
                return None
            return {
                'task_id': task.task_id,
                'account_id': task.account_id,
                'action': task.action,
                'status': task.status,
                'priority': Priority(task.priority).name,
                'submitted_at': task.submitted_at,
                'completed_at': task.completed_at,
                'attempts': task.attempts,
                'result': task.result,
                'error': task.error,
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        with self._history_lock:
            task = self._task_history.get(task_id)
            if task and task.status == 'pending':
                queue = self._get_account_queue(task.account_id)
                return queue.cancel_task(task_id)
        return False
    
    # ========================================================================
    # WORKER LOOP
    # ========================================================================
    
    def start(self, num_workers: int = None):
        """Start the dispatcher worker threads"""
        if self._running:
            logger.warning("OrderDispatcher already running")
            return
        
        self._running = True
        self._num_workers = num_workers or self._num_workers
        
        for i in range(self._num_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"OrderDispatcher-Worker-{i}"
            )
            self._worker_threads.append(thread)
            thread.start()
        
        logger.info(f"✅ OrderDispatcher started with {self._num_workers} workers")
    
    def stop(self):
        """Stop the dispatcher"""
        self._running = False
        for thread in self._worker_threads:
            thread.join(timeout=2.0)
        self._worker_threads.clear()
        logger.info("🛑 OrderDispatcher stopped")
    
    def is_running(self) -> bool:
        """Check if dispatcher is running"""
        return self._running
    
    def _worker_loop(self):
        """Main worker loop - processes tasks from queues"""
        thread_name = threading.current_thread().name
        logger.info(f"🔧 {thread_name} started")
        
        while self._running:
            try:
                task = self._get_next_task()
                
                if task is None:
                    # No tasks available, sleep briefly
                    time.sleep(0.05)
                    continue
                
                self._process_task(task)
                
            except Exception as e:
                logger.error(f"{thread_name} error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                time.sleep(0.1)
        
        logger.info(f"🔧 {thread_name} stopped")
    
    def _get_next_task(self) -> Optional[OrderTask]:
        """
        Get next task to process using round-robin across accounts.
        Respects rate limits and penalties.
        """
        with self._queues_lock:
            accounts = list(self._account_queues.keys())
        
        if not accounts:
            return None
        
        # Round-robin: try each account once
        for account_id in accounts:
            queue = self._account_queues.get(account_id)
            if not queue or queue.is_empty():
                continue
            
            # Check if account is penalized
            if queue.is_penalized():
                continue
            
            # Check rate limits
            if not self._global_limiter.acquire(timeout=0):
                self._stats['rate_limited'] += 1
                continue
            
            account_limiter = self._get_account_limiter(account_id)
            if not account_limiter.acquire(timeout=0):
                self._stats['rate_limited'] += 1
                continue
            
            # Get task from queue
            task = queue.pop()
            if task and task.status == 'pending':
                return task
        
        return None
    
    def _process_task(self, task: OrderTask):
        """Process a single task"""
        task.status = 'processing'
        task.attempts += 1
        
        logger.info(f"⚡ Processing: {task.task_id} - {task.action} (attempt {task.attempts}/{task.max_attempts})")
        
        try:
            if self._execute_func is None:
                raise ValueError("No execute function configured")
            
            # Execute the task
            result = self._execute_func(task)
            
            # Check for penalty response
            if result.get('penalized'):
                p_time = result.get('p_time', 10)
                p_ticket = result.get('p_ticket')
                
                self._stats['penalties'] += 1
                
                # Set account penalty
                queue = self._get_account_queue(task.account_id)
                queue.set_penalty(p_time, p_ticket)
                
                # Retry if allowed
                if task.attempts < task.max_attempts:
                    task.status = 'pending'
                    task.p_ticket = p_ticket
                    task.retry_after = time.time() + p_time
                    queue.push(task)
                    logger.info(f"🔄 Task {task.task_id} will retry after {p_time}s penalty")
                    return
                else:
                    task.status = 'failed'
                    task.error = f"Penalized: {p_time}s (max attempts reached)"
                    task.completed_at = time.time()
                    self._stats['failed'] += 1
                    queue.tasks_failed += 1
                    return
            
            # Check for rate limit (429)
            if result.get('rate_limited'):
                self._stats['rate_limited'] += 1
                
                if task.attempts < task.max_attempts:
                    task.status = 'pending'
                    task.retry_after = time.time() + 5  # Wait 5 seconds
                    queue = self._get_account_queue(task.account_id)
                    queue.push(task)
                    logger.warning(f"🔄 Task {task.task_id} rate limited, will retry")
                    return
                else:
                    task.status = 'failed'
                    task.error = "Rate limited (max attempts reached)"
                    task.completed_at = time.time()
                    self._stats['failed'] += 1
                    return
            
            # Success
            if result.get('success'):
                task.status = 'completed'
                task.result = result
                task.completed_at = time.time()
                self._stats['completed'] += 1
                
                queue = self._get_account_queue(task.account_id)
                queue.tasks_completed += 1
                
                logger.info(f"✅ Task completed: {task.task_id}")
            else:
                # Failed (but not penalty/rate limit)
                task.status = 'failed'
                task.error = result.get('error', 'Unknown error')
                task.completed_at = time.time()
                self._stats['failed'] += 1
                
                queue = self._get_account_queue(task.account_id)
                queue.tasks_failed += 1
                
                logger.error(f"❌ Task failed: {task.task_id} - {task.error}")
                
        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            task.completed_at = time.time()
            self._stats['failed'] += 1
            logger.error(f"❌ Task exception: {task.task_id} - {e}")
    
    # ========================================================================
    # STATS & HEALTH
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get dispatcher statistics"""
        with self._queues_lock:
            queue_stats = {
                acc_id: {
                    'size': q.size(),
                    'penalized': q.is_penalized(),
                    'penalty_until': q.penalty_until,
                    'submitted': q.tasks_submitted,
                    'completed': q.tasks_completed,
                    'failed': q.tasks_failed,
                }
                for acc_id, q in self._account_queues.items()
            }
        
        return {
            **self._stats,
            'running': self._running,
            'workers': len(self._worker_threads),
            'workers_alive': sum(1 for t in self._worker_threads if t.is_alive()),
            'global_tokens': self._global_limiter.get_tokens(),
            'accounts': len(self._account_queues),
            'queue_stats': queue_stats,
        }
    
    def get_queue_depth(self) -> int:
        """Get total tasks across all queues"""
        with self._queues_lock:
            return sum(q.size() for q in self._account_queues.values())
    
    def health_check(self) -> dict:
        """Check dispatcher health"""
        workers_alive = sum(1 for t in self._worker_threads if t.is_alive())
        
        return {
            'healthy': self._running and workers_alive == len(self._worker_threads),
            'running': self._running,
            'workers_alive': workers_alive,
            'workers_expected': len(self._worker_threads),
            'queue_depth': self.get_queue_depth(),
            'error_rate': self._stats['failed'] / max(1, self._stats['submitted']),
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_dispatcher: Optional[OrderDispatcher] = None


def init_dispatcher(execute_func: Callable[[OrderTask], dict], **kwargs) -> OrderDispatcher:
    """
    Initialize the global order dispatcher.
    
    Args:
        execute_func: Function to execute orders
        **kwargs: Additional args passed to OrderDispatcher
    """
    global _global_dispatcher
    
    if _global_dispatcher and _global_dispatcher.is_running():
        logger.warning("Dispatcher already running, returning existing instance")
        return _global_dispatcher
    
    _global_dispatcher = OrderDispatcher(execute_func=execute_func, **kwargs)
    return _global_dispatcher


def get_dispatcher() -> Optional[OrderDispatcher]:
    """Get the global dispatcher instance"""
    return _global_dispatcher


def start_dispatcher():
    """Start the global dispatcher"""
    if _global_dispatcher:
        _global_dispatcher.start()


def stop_dispatcher():
    """Stop the global dispatcher"""
    global _global_dispatcher
    if _global_dispatcher:
        _global_dispatcher.stop()
        _global_dispatcher = None
