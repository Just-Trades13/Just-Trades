"""
Database initialization and session management for Just.Trades.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from app.models import Base

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///just_trades.db')

# Create engine
# For SQLite, use StaticPool to handle multiple threads
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL query logging
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def get_db():
    """
    Get database session (for use in routes).
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    This should be called once when setting up the application.
    """
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def drop_all_tables():
    """
    Drop all tables (use with caution - for development only).
    """
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped!")


def reset_db():
    """
    Reset database - drop all tables and recreate them.
    WARNING: This will delete all data!
    """
    drop_all_tables()
    init_db()
    print("Database reset complete!")


if __name__ == '__main__':
    # Initialize database when run directly
    print(f"Initializing database at: {DATABASE_URL}")
    init_db()
    print("Done!")

