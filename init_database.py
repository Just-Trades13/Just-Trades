#!/usr/bin/env python3
"""
Simple database initialization script for Just.Trades.
Creates all tables defined in app/models.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import init_db, engine
    from app.models import Base
    
    print("=" * 60)
    print("Just.Trades. Database Initialization")
    print("=" * 60)
    print()
    
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    print()
    print("✅ Database initialized successfully!")
    print()
    print("Created tables:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
    print()
    
except ImportError as e:
    print(f"❌ Error: Missing required packages")
    print(f"   {e}")
    print()
    print("Please install required packages:")
    print("  pip3 install sqlalchemy --user")
    print("  # or use a virtual environment")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error initializing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

