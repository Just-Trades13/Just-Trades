"""
Database Models for Just.Trades.
Complete schema with all required tables and relationships.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()


class User(Base):
    """User accounts for authentication and Discord integration"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Discord integration
    discord_user_id = Column(String(50), unique=True, nullable=True)
    discord_access_token = Column(Text, nullable=True)  # Encrypted
    discord_dms_enabled = Column(Boolean, default=True)
    
    # Session management
    session_id = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    strategies = relationship("Strategy", back_populates="user")
    traders = relationship("Trader", back_populates="user")


class Account(Base):
    """Trading accounts (Tradovate live/demo)"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Link to user
    name = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False, default='Tradovate')
    auth_type = Column(String(20), nullable=False)  # 'credentials' or 'api'
    
    # Credentials authentication
    username = Column(String(100), nullable=True)
    password = Column(Text, nullable=True)  # Encrypted
    account_id = Column(String(50), nullable=True)  # Tradovate account ID
    
    # API authentication
    api_key = Column(String(255), nullable=True)
    api_secret = Column(Text, nullable=True)  # Encrypted
    api_endpoint = Column(String(255), nullable=True)
    environment = Column(String(20), nullable=True)  # 'live' or 'demo'
    
    # OAuth credentials (NEW - for Tradovate OAuth)
    client_id = Column(String(255), nullable=True)
    client_secret = Column(Text, nullable=True)  # Encrypted
    
    # Tradovate specific tokens
    tradovate_token = Column(Text, nullable=True)
    tradovate_refresh_token = Column(Text, nullable=True)  # Encrypted
    token_expires_at = Column(DateTime, nullable=True)
    
    # Account settings
    max_contracts = Column(Integer, default=1)
    multiplier = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    strategies = relationship("Strategy", foreign_keys="Strategy.account_id", back_populates="account")
    demo_strategies = relationship("Strategy", foreign_keys="Strategy.demo_account_id", back_populates="demo_account")
    traders = relationship("Trader", back_populates="account")
    trades = relationship("Trade", back_populates="account")
    recorded_positions = relationship("RecordedPosition", back_populates="account")


class Strategy(Base):
    """Trading strategies/recorders"""
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # NEW - Link to user
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
    demo_account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)  # NEW - Demo account for recording
    
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=True)  # NEW - Symbol (ES, NQ, etc.)
    
    # Strategy settings
    strat_type = Column(String(50), nullable=True)
    days_to_expiry = Column(Integer, nullable=True)
    strike_offset = Column(Float, nullable=True)
    position_size = Column(Integer, default=1)
    position_add = Column(Integer, default=1)
    take_profit = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    trim = Column(Float, nullable=True)
    tpsl_units = Column(String(20), nullable=True)  # 'Ticks', 'Percent', 'Dollars'
    directional_strategy = Column(String(50), nullable=True)
    
    # Recording settings (NEW)
    recording_enabled = Column(Boolean, default=True)
    
    # Positional settings (from UI)
    positional_settings = Column(JSON, nullable=True)  # Store complex positional config
    
    # Filter settings
    delay_seconds = Column(Integer, default=0)
    max_contracts = Column(Integer, nullable=True)
    premium_filter = Column(Boolean, default=False)
    direction_filter = Column(String(20), nullable=True)  # 'long', 'short', 'both'
    
    # Time filters
    time_filter_enabled = Column(Boolean, default=False)
    time_filter_start = Column(String(10), nullable=True)  # 'HH:MM' format
    time_filter_end = Column(String(10), nullable=True)
    
    # Execution controls
    entry_delay = Column(Integer, default=0)
    signal_cooldown = Column(Integer, default=0)
    max_signals_per_session = Column(Integer, nullable=True)
    max_daily_loss = Column(Float, nullable=True)
    auto_flat = Column(Boolean, default=False)
    
    # Strategy status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="strategies")
    account = relationship("Account", foreign_keys=[account_id], back_populates="strategies")
    demo_account = relationship("Account", foreign_keys=[demo_account_id], back_populates="demo_strategies")
    trades = relationship("Trade", back_populates="strategy")
    recorded_positions = relationship("RecordedPosition", back_populates="strategy")
    strategy_logs = relationship("StrategyLog", back_populates="strategy")
    traders = relationship("Trader", back_populates="strategy")


class Trader(Base):
    """Strategy-account assignments (My Traders)"""
    __tablename__ = 'traders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # NEW - Link to user
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    
    # Trader name (can be different from strategy name)
    name = Column(String(100), nullable=False)
    
    # Account routing settings
    enabled = Column(Boolean, default=True)
    max_contracts = Column(Integer, nullable=True)
    custom_ticker = Column(String(20), nullable=True)
    multiplier = Column(Float, default=1.0)
    
    # Positional/SLTP/Filter settings (can override strategy defaults)
    positional_settings = Column(JSON, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    filter_settings = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="traders")
    strategy = relationship("Strategy", back_populates="traders")
    account = relationship("Account", back_populates="traders")


class Trade(Base):
    """Executed trades (from webhooks)"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=True)
    trader_id = Column(Integer, ForeignKey('traders.id'), nullable=True)  # NEW - Link to trader
    
    # Trade details
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)
    order_type = Column(String(20), nullable=True)  # 'market', 'limit', 'stop'
    
    # Trade status
    status = Column(String(20), default='pending')  # 'pending', 'filled', 'cancelled', 'rejected'
    tradovate_order_id = Column(String(50), nullable=True)
    
    # Webhook tracking (NEW)
    webhook_id = Column(Integer, ForeignKey('webhook_logs.id'), nullable=True)
    webhook_payload = Column(JSON, nullable=True)  # Store original webhook data
    
    # PnL tracking
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")
    webhook_log = relationship("WebhookLog", foreign_keys=[webhook_id])


class RecordedPosition(Base):
    """Recorded positions from demo account (for Recorder system)"""
    __tablename__ = 'recorded_positions'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    
    # Position details
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'Buy' or 'Sell'
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_timestamp = Column(DateTime, nullable=False)
    
    # Exit details
    exit_price = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime, nullable=True)
    exit_reason = Column(String(50), nullable=True)  # 'Take Profit', 'Stop Loss', 'Manual', 'Signal'
    
    # P&L
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    commission = Column(Float, default=0.0)
    net_pnl = Column(Float, nullable=True)
    
    # Stop Loss / Take Profit
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    
    # Tradovate IDs
    tradovate_order_id = Column(String(50), nullable=True)
    tradovate_position_id = Column(String(50), nullable=True)
    
    # Status
    status = Column(String(20), default='open')  # 'open', 'closed', 'stopped_out', 'target_hit'
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="recorded_positions")
    account = relationship("Account", back_populates="recorded_positions")


class StrategyLog(Base):
    """Strategy-specific event logs"""
    __tablename__ = 'strategy_logs'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    
    log_type = Column(String(50), nullable=False)  # 'entry', 'exit', 'signal', 'error', 'info'
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)  # Additional data as JSON
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="strategy_logs")


class WebhookLog(Base):
    """Webhook logs from TradingView"""
    __tablename__ = 'webhook_logs'
    
    id = Column(Integer, primary_key=True)
    webhook_data = Column(Text, nullable=False)  # JSON string of webhook payload
    processed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=True)  # NEW - Link to strategy
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    strategy = relationship("Strategy", foreign_keys=[strategy_id])
    trades = relationship("Trade", back_populates="webhook_log")

