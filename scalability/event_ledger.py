"""
Event Ledger for Just.Trades Scalability
=========================================

Append-only event store for broker events. Provides:
- Auditability (every broker event is recorded)
- Replay capability (rebuild state from events)
- Debugging (see exact sequence of events)

Storage options:
- SQLite/PostgreSQL (default)
- In-memory (for testing)
- File-based (for export)

Usage:
    from scalability.event_ledger import EventLedger, get_ledger
    
    ledger = get_ledger()
    
    # Record a broker event
    ledger.append(
        account_id=12345,
        entity_type='position',
        event_type='Updated',
        entity_id=67890,
        raw_data={'netPos': 2, 'netPrice': 21500.00}
    )
    
    # Query events
    events = ledger.get_events(account_id=12345, entity_type='position')
    
    # Replay to rebuild state
    state = ledger.replay(account_id=12345)
"""

import threading
import time
import json
import logging
from typing import Dict, List, Optional, Any, Iterator
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class BrokerEvent:
    """A single broker event"""
    id: int
    account_id: int
    timestamp: float  # Unix timestamp
    entity_type: str  # position, order, fill, etc.
    event_type: str   # Created, Updated, Deleted, etc.
    entity_id: Optional[int]
    raw_data: dict
    sequence: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BrokerEvent':
        return cls(**data)


class EventLedger:
    """
    Append-only event store for broker events.
    
    This implementation uses an in-memory store by default.
    For production, override with database-backed storage.
    """
    
    def __init__(
        self,
        db_connection=None,
        max_memory_events: int = 100000,
        retention_hours: int = 24
    ):
        """
        Initialize the event ledger.
        
        Args:
            db_connection: Optional database connection for persistence
            max_memory_events: Maximum events to keep in memory
            retention_hours: How long to keep events
        """
        self._db = db_connection
        self._max_events = max_memory_events
        self._retention_hours = retention_hours
        
        # In-memory storage (append-only)
        self._events: List[BrokerEvent] = []
        self._events_lock = threading.Lock()
        
        # Indexes for fast lookup
        self._by_account: Dict[int, List[int]] = defaultdict(list)  # account_id -> event indices
        self._by_entity: Dict[str, List[int]] = defaultdict(list)   # "type:id" -> event indices
        
        # Sequence counter
        self._sequence = 0
        self._event_id = 0
        
        # Stats
        self._stats = {
            'events_appended': 0,
            'events_trimmed': 0,
            'replays': 0,
        }
        
        # Initialize database table if using persistence
        if self._db:
            self._init_db()
        
        logger.info(f"📜 EventLedger initialized (max_events={max_memory_events}, retention={retention_hours}h)")
    
    def _init_db(self):
        """Initialize database table for event storage"""
        try:
            cursor = self._db.cursor()

            # Try PostgreSQL syntax first
            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS broker_events (
                        id SERIAL PRIMARY KEY,
                        account_id BIGINT NOT NULL,
                        timestamp DOUBLE PRECISION NOT NULL,
                        entity_type VARCHAR(50) NOT NULL,
                        event_type VARCHAR(50) NOT NULL,
                        entity_id BIGINT,
                        raw_data JSONB,
                        sequence BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_events_account ON broker_events(account_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_events_entity ON broker_events(entity_type, entity_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_events_timestamp ON broker_events(timestamp)')

                # MIGRATION: Alter existing columns from INTEGER to BIGINT if table already exists
                # This fixes "integer out of range" errors for large Tradovate IDs
                try:
                    cursor.execute('ALTER TABLE broker_events ALTER COLUMN account_id TYPE BIGINT')
                    cursor.execute('ALTER TABLE broker_events ALTER COLUMN entity_id TYPE BIGINT')
                    self._db.commit()
                    logger.info("📜 Migrated broker_events columns to BIGINT")
                except Exception as migrate_err:
                    # Column might already be BIGINT or migration failed - that's ok
                    self._db.rollback()
                    logger.debug(f"BIGINT migration skipped (may already be done): {migrate_err}")
            except:
                # Fall back to SQLite syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS broker_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_id INTEGER NOT NULL,
                        timestamp REAL NOT NULL,
                        entity_type TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        entity_id INTEGER,
                        raw_data TEXT,
                        sequence INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_events_account ON broker_events(account_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_events_entity ON broker_events(entity_type, entity_id)')
            
            self._db.commit()
            logger.info("📜 EventLedger database table initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize event ledger table: {e}")
    
    # ========================================================================
    # APPEND EVENTS
    # ========================================================================
    
    def append(
        self,
        account_id: int,
        entity_type: str,
        event_type: str,
        entity_id: int = None,
        raw_data: dict = None,
        timestamp: float = None
    ) -> BrokerEvent:
        """
        Append an event to the ledger.
        
        Args:
            account_id: Tradovate account ID
            entity_type: Type of entity (position, order, fill, etc.)
            event_type: Type of event (Created, Updated, Deleted, etc.)
            entity_id: ID of the entity (if applicable)
            raw_data: Raw event data from broker
            timestamp: Event timestamp (default: now)
            
        Returns:
            The created BrokerEvent
        """
        with self._events_lock:
            self._event_id += 1
            self._sequence += 1
            
            event = BrokerEvent(
                id=self._event_id,
                account_id=account_id,
                timestamp=timestamp or time.time(),
                entity_type=entity_type,
                event_type=event_type,
                entity_id=entity_id,
                raw_data=raw_data or {},
                sequence=self._sequence
            )
            
            # Store in memory
            idx = len(self._events)
            self._events.append(event)
            
            # Update indexes
            self._by_account[account_id].append(idx)
            if entity_id:
                self._by_entity[f"{entity_type}:{entity_id}"].append(idx)
            
            self._stats['events_appended'] += 1
            
            # Persist to database if available
            if self._db:
                self._persist_event(event)
            
            # Trim if over limit
            if len(self._events) > self._max_events:
                self._trim_old_events()
            
            logger.debug(f"Event appended: {entity_type}.{event_type} (account={account_id}, entity={entity_id})")
            
            return event
    
    def append_raw(self, account_id: int, raw_event: dict) -> Optional[BrokerEvent]:
        """
        Append a raw event from broker WebSocket.
        Parses the Tradovate props event format.
        
        Expected format:
            {"e": "props", "d": {"entityType": "position", "event": "Created", "entity": {...}}}
        """
        try:
            if raw_event.get('e') != 'props':
                return None
            
            data = raw_event.get('d', {})
            entity_type = data.get('entityType')
            event_type = data.get('event')
            entity = data.get('entity', {})
            entity_id = entity.get('id')
            
            if not entity_type:
                logger.debug(f"Unknown entity type in raw event: {raw_event}")
                return None
            
            return self.append(
                account_id=account_id,
                entity_type=entity_type,
                event_type=event_type,
                entity_id=entity_id,
                raw_data=entity,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Failed to append raw event: {e}")
            return None
    
    def _persist_event(self, event: BrokerEvent):
        """Persist event to database"""
        try:
            cursor = self._db.cursor()
            
            raw_json = json.dumps(event.raw_data) if event.raw_data else None
            
            # Detect database type and use appropriate placeholder
            # PostgreSQL uses %s, SQLite uses ?
            db_type = type(self._db).__module__
            if 'psycopg' in db_type or 'pg8000' in db_type:
                # PostgreSQL
                cursor.execute('''
                    INSERT INTO broker_events (account_id, timestamp, entity_type, event_type, entity_id, raw_data, sequence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (event.account_id, event.timestamp, event.entity_type, event.event_type, 
                      event.entity_id, raw_json, event.sequence))
            else:
                # SQLite or other
                cursor.execute('''
                    INSERT INTO broker_events (account_id, timestamp, entity_type, event_type, entity_id, raw_data, sequence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (event.account_id, event.timestamp, event.entity_type, event.event_type, 
                      event.entity_id, raw_json, event.sequence))
            
            self._db.commit()
            
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")
            # CRITICAL: Rollback failed transaction to prevent cascading failures
            # Without this, all subsequent DB commands fail with "transaction aborted"
            try:
                self._db.rollback()
            except:
                pass
    
    def _trim_old_events(self):
        """Remove oldest events to stay under limit"""
        trim_count = len(self._events) - self._max_events + 1000  # Trim 1000 extra
        if trim_count <= 0:
            return
        
        # Remove from memory
        self._events = self._events[trim_count:]
        
        # Rebuild indexes (expensive but rare)
        self._by_account.clear()
        self._by_entity.clear()
        
        for idx, event in enumerate(self._events):
            self._by_account[event.account_id].append(idx)
            if event.entity_id:
                self._by_entity[f"{event.entity_type}:{event.entity_id}"].append(idx)
        
        self._stats['events_trimmed'] += trim_count
        logger.debug(f"Trimmed {trim_count} old events from memory")
    
    # ========================================================================
    # QUERY EVENTS
    # ========================================================================
    
    def get_events(
        self,
        account_id: int = None,
        entity_type: str = None,
        entity_id: int = None,
        since_sequence: int = None,
        since_timestamp: float = None,
        limit: int = 1000
    ) -> List[BrokerEvent]:
        """
        Query events with filters.
        
        Args:
            account_id: Filter by account
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            since_sequence: Only events after this sequence
            since_timestamp: Only events after this timestamp
            limit: Maximum events to return
            
        Returns:
            List of matching events (newest first)
        """
        with self._events_lock:
            results = []
            
            # Determine which events to scan
            if entity_id and entity_type:
                indices = self._by_entity.get(f"{entity_type}:{entity_id}", [])
                candidates = [self._events[i] for i in indices if i < len(self._events)]
            elif account_id:
                indices = self._by_account.get(account_id, [])
                candidates = [self._events[i] for i in indices if i < len(self._events)]
            else:
                candidates = self._events
            
            # Apply filters
            for event in reversed(candidates):  # Newest first
                if since_sequence and event.sequence <= since_sequence:
                    continue
                if since_timestamp and event.timestamp <= since_timestamp:
                    continue
                if account_id and event.account_id != account_id:
                    continue
                if entity_type and event.entity_type != entity_type:
                    continue
                
                results.append(event)
                
                if len(results) >= limit:
                    break
            
            return results
    
    def get_latest_event(
        self,
        account_id: int,
        entity_type: str,
        entity_id: int = None
    ) -> Optional[BrokerEvent]:
        """Get the most recent event for an entity"""
        events = self.get_events(
            account_id=account_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=1
        )
        return events[0] if events else None
    
    # ========================================================================
    # REPLAY / STATE RECONSTRUCTION
    # ========================================================================
    
    def replay(
        self,
        account_id: int,
        entity_type: str = None,
        up_to_sequence: int = None
    ) -> dict:
        """
        Replay events to reconstruct current state.
        
        Args:
            account_id: Account to replay
            entity_type: Optional filter by entity type
            up_to_sequence: Stop at this sequence (for point-in-time)
            
        Returns:
            Reconstructed state: {
                'positions': {entity_id: data},
                'orders': {entity_id: data},
                'fills': {entity_id: data},
                ...
            }
        """
        self._stats['replays'] += 1
        
        state = defaultdict(dict)
        
        with self._events_lock:
            indices = self._by_account.get(account_id, [])
            
            for idx in indices:
                if idx >= len(self._events):
                    continue
                    
                event = self._events[idx]
                
                if up_to_sequence and event.sequence > up_to_sequence:
                    continue
                
                if entity_type and event.entity_type != entity_type:
                    continue
                
                # Apply event to state
                if event.event_type in ('Created', 'Updated', 'Changed'):
                    if event.entity_id:
                        state[event.entity_type][event.entity_id] = event.raw_data
                    else:
                        # For entities without ID (like cash balance)
                        state[event.entity_type]['current'] = event.raw_data
                        
                elif event.event_type == 'Deleted':
                    if event.entity_id and event.entity_id in state[event.entity_type]:
                        del state[event.entity_type][event.entity_id]
        
        logger.debug(f"Replayed {len(indices)} events for account {account_id}")
        
        return dict(state)
    
    # ========================================================================
    # STATS & MAINTENANCE
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get ledger statistics"""
        with self._events_lock:
            return {
                **self._stats,
                'events_in_memory': len(self._events),
                'accounts_tracked': len(self._by_account),
                'current_sequence': self._sequence,
                'oldest_event': self._events[0].timestamp if self._events else None,
                'newest_event': self._events[-1].timestamp if self._events else None,
            }
    
    def cleanup_old_events(self, older_than_hours: int = None) -> int:
        """Remove events older than specified hours"""
        hours = older_than_hours or self._retention_hours
        cutoff = time.time() - (hours * 3600)
        
        with self._events_lock:
            original_count = len(self._events)
            
            # Find cutoff index
            cutoff_idx = 0
            for i, event in enumerate(self._events):
                if event.timestamp >= cutoff:
                    cutoff_idx = i
                    break
            else:
                cutoff_idx = len(self._events)
            
            if cutoff_idx > 0:
                self._events = self._events[cutoff_idx:]
                
                # Rebuild indexes
                self._by_account.clear()
                self._by_entity.clear()
                
                for idx, event in enumerate(self._events):
                    self._by_account[event.account_id].append(idx)
                    if event.entity_id:
                        self._by_entity[f"{event.entity_type}:{event.entity_id}"].append(idx)
            
            removed = original_count - len(self._events)
            if removed:
                self._stats['events_trimmed'] += removed
                logger.info(f"Cleaned up {removed} events older than {hours} hours")
            
            return removed
    
    def clear(self):
        """Clear all events (for testing)"""
        with self._events_lock:
            self._events.clear()
            self._by_account.clear()
            self._by_entity.clear()
            logger.info("EventLedger cleared")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_global_ledger: Optional[EventLedger] = None


def get_ledger() -> EventLedger:
    """Get or create the global event ledger"""
    global _global_ledger
    if _global_ledger is None:
        _global_ledger = EventLedger()
    return _global_ledger


def init_ledger(db_connection=None, **kwargs) -> EventLedger:
    """Initialize the global ledger with options"""
    global _global_ledger
    _global_ledger = EventLedger(db_connection=db_connection, **kwargs)
    return _global_ledger
