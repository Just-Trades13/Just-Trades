from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    auth_type = Column(String(20), nullable=False)  # 'credentials' or 'api'
    
    # Credentials authentication
    username = Column(String(100))
    password = Column(String(255))  # Will be encrypted
    account_id = Column(String(50))
    
    # API authentication
    api_key = Column(String(255))
    api_secret = Column(String(255))  # Will be encrypted
    api_endpoint = Column(String(255))
    environment = Column(String(20))  # 'live' or 'demo'
    
    # Account settings
    max_contracts = Column(Integer, default=1)
    multiplier = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    
    # Tradovate specific
    tradovate_token = Column(Text)
    tradovate_refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    strategies = relationship("Strategy", back_populates="account")
    trades = relationship("Trade", back_populates="account")

class Strategy(Base):
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    
    # Strategy settings
    strat_type = Column(String(50))
    days_to_expiry = Column(Integer)
    strike_offset = Column(Float)
    position_size = Column(Integer)
    position_add = Column(Integer)
    take_profit = Column(Float)
    stop_loss = Column(Float)
    trim = Column(Float)
    tpsl_units = Column(String(20))
    directional_strategy = Column(String(50))
    
    # Strategy status
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("Account", back_populates="strategies")
    trades = relationship("Trade", back_populates="strategy")

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    
    # Trade details
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    quantity = Column(Integer, nullable=False)
    price = Column(Float)
    order_type = Column(String(20))  # 'market', 'limit', 'stop'
    
    # Trade status
    status = Column(String(20), default='pending')  # 'pending', 'filled', 'cancelled', 'rejected'
    tradovate_order_id = Column(String(50))
    
    # PnL tracking
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime)
    closed_at = Column(DateTime)
    
    # Relationships
    account = relationship("Account", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")

class WebhookLog(Base):
    __tablename__ = 'webhook_logs'
    
    id = Column(Integer, primary_key=True)
    webhook_data = Column(Text)  # JSON string of webhook payload
    processed = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database setup
def create_database():
    engine = create_engine('sqlite:///trading_platform.db')
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
