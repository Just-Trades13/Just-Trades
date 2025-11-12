#!/usr/bin/env python3
"""
Create a test user for Just.Trades
Run this script to create a test account for login
"""

from database import init_db, get_db
import hashlib

def create_test_user():
    """Create a test user"""
    # Initialize database
    init_db()
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if test user already exists
    cursor.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
    if cursor.fetchone():
        print("✅ Test user already exists!")
        print("   Username: testuser")
        print("   Password: testpass123")
        return
    
    # Create test user
    password_hash = hashlib.sha256('testpass123'.encode()).hexdigest()
    
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, admin, is_email_verified)
        VALUES (?, ?, ?, ?, ?)
    """, ('testuser', 'test@just.trades', password_hash, False, True))
    
    db.commit()
    
    print("✅ Test user created successfully!")
    print("   Username: testuser")
    print("   Password: testpass123")
    print("\nYou can now log in with these credentials.")

if __name__ == '__main__':
    create_test_user()

