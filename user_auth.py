"""
User Authentication Module
==========================
Provides user authentication, session management, and access control for Just.Trades.

Features:
- User registration with secure password hashing
- Login/logout with Flask sessions
- login_required decorator for protecting routes
- User data isolation (each user sees only their data)

Usage:
    from user_auth import login_required, get_current_user, init_users_table
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        user = get_current_user()
        return render_template('dashboard.html', user=user)
"""

import os
import sqlite3
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, request, flash, g

logger = logging.getLogger('user_auth')

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')
SQLITE_PATH = os.environ.get('SQLITE_PATH', 'just_trades.db')


def get_auth_db_connection():
    """Get database connection for auth operations."""
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            conn = psycopg2.connect(db_url)
            conn.cursor_factory = RealDictCursor
            return conn, 'postgresql'
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}, falling back to SQLite")
    
    conn = sqlite3.connect(SQLITE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn, 'sqlite'


# ============================================================================
# DATABASE SCHEMA
# ============================================================================
def init_users_table():
    """Initialize the users table if it doesn't exist."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name VARCHAR(100),
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_approved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    settings_json TEXT DEFAULT '{}'
                )
            ''')
            
            # Create index on email for fast lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            ''')
        else:
            # SQLite schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    is_admin INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    is_approved INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    settings_json TEXT DEFAULT '{}'
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        
        conn.commit()
        logger.info("✅ Users table initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize users table: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def migrate_add_is_approved():
    """
    Add is_approved column to users table if it doesn't exist.
    Sets existing users to approved=True (they were created before approval was required).
    """
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            # Check if column exists
            cursor.execute('''
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'is_approved'
            ''')
            if not cursor.fetchone():
                cursor.execute('ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT FALSE')
                # Set existing users to approved (they were created before this feature)
                cursor.execute('UPDATE users SET is_approved = TRUE WHERE is_approved IS NULL OR is_approved = FALSE')
                # Admins are always considered approved
                cursor.execute('UPDATE users SET is_approved = TRUE WHERE is_admin = TRUE')
                logger.info("✅ Added is_approved column to users table")
        else:
            # SQLite - check if column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] if isinstance(row, tuple) else row['name'] for row in cursor.fetchall()]
            if 'is_approved' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0')
                # Set existing users to approved (they were created before this feature)
                cursor.execute('UPDATE users SET is_approved = 1')
                # Admins are always considered approved
                cursor.execute('UPDATE users SET is_approved = 1 WHERE is_admin = 1')
                logger.info("✅ Added is_approved column to users table")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add is_approved column: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def add_user_id_to_tables():
    """
    Add user_id column to existing tables for data isolation.
    This links accounts, traders, etc. to specific users.
    """
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    tables_to_update = ['accounts', 'traders', 'recorded_trades']
    
    try:
        for table in tables_to_update:
            try:
                if db_type == 'postgresql':
                    # Check if column exists
                    cursor.execute(f'''
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'user_id'
                    ''')
                    if not cursor.fetchone():
                        cursor.execute(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER')
                        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)')
                        logger.info(f"✅ Added user_id to {table}")
                else:
                    # SQLite - check if column exists
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] if isinstance(row, tuple) else row['name'] for row in cursor.fetchall()]
                    if 'user_id' not in columns:
                        cursor.execute(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER')
                        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)')
                        logger.info(f"✅ Added user_id to {table}")
            except Exception as e:
                logger.warning(f"Could not add user_id to {table}: {e}")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add user_id columns: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# USER MANAGEMENT FUNCTIONS
# ============================================================================
class User:
    """User model for authentication."""
    
    def __init__(self, id: int, username: str, email: str, display_name: str = None,
                 is_admin: bool = False, is_active: bool = True, is_approved: bool = False, 
                 settings: dict = None, created_at: str = None, last_login: str = None):
        self.id = id
        self.username = username
        self.email = email
        self.display_name = display_name or username
        self.is_admin = is_admin
        self.is_active = is_active
        self.is_approved = is_approved
        self.settings = settings or {}
        self.created_at = created_at
        self.last_login = last_login
    
    @property
    def is_authenticated(self):
        return True
    
    @staticmethod
    def from_row(row) -> Optional['User']:
        """Create User from database row."""
        if not row:
            return None
        
        # Handle both dict and sqlite3.Row
        if hasattr(row, 'keys'):
            data = dict(row)
        else:
            data = row
        
        import json
        settings = {}
        if data.get('settings_json'):
            try:
                settings = json.loads(data['settings_json'])
            except:
                pass
        
        return User(
            id=data['id'],
            username=data['username'],
            email=data['email'],
            display_name=data.get('display_name'),
            is_admin=bool(data.get('is_admin', 0)),
            is_active=bool(data.get('is_active', 1)),
            is_approved=bool(data.get('is_approved', 0)),
            settings=settings,
            created_at=data.get('created_at'),
            last_login=data.get('last_login')
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'is_approved': self.is_approved,
            'settings': self.settings
        }


def create_user(username: str, email: str, password: str, display_name: str = None,
                is_admin: bool = False) -> Optional[User]:
    """
    Create a new user account.
    
    Args:
        username: Unique username (alphanumeric, 3-50 chars)
        email: Unique email address
        password: Plain text password (will be hashed)
        display_name: Optional display name
        is_admin: Whether user has admin privileges
        
    Returns:
        User object if created, None if failed
    """
    # Validate inputs
    if not username or len(username) < 3:
        logger.warning("Username must be at least 3 characters")
        return None
    if not email or '@' not in email:
        logger.warning("Invalid email address")
        return None
    if not password or len(password) < 6:
        logger.warning("Password must be at least 6 characters")
        return None
    
    # Hash password
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, display_name, is_admin)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            ''', (username.lower(), email.lower(), password_hash, display_name or username, is_admin))
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, display_name, is_admin)
                VALUES (?, ?, ?, ?, ?)
            ''', (username.lower(), email.lower(), password_hash, display_name or username, int(is_admin)))
            user_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"✅ Created user: {username} (id={user_id})")
        
        return User(
            id=user_id,
            username=username.lower(),
            email=email.lower(),
            display_name=display_name or username,
            is_admin=is_admin
        )
    except Exception as e:
        logger.error(f"❌ Failed to create user {username}: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        
        row = cursor.fetchone()
        return User.from_row(row)
    finally:
        cursor.close()
        conn.close()


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username (case-insensitive)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        username_lower = username.strip().lower()
        if db_type == 'postgresql':
            # Case-insensitive match
            cursor.execute('SELECT * FROM users WHERE LOWER(username) = %s', (username_lower,))
        else:
            cursor.execute('SELECT * FROM users WHERE LOWER(username) = ?', (username_lower,))
        
        row = cursor.fetchone()
        return User.from_row(row)
    finally:
        cursor.close()
        conn.close()


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email (case-insensitive)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        email_lower = email.strip().lower()
        if db_type == 'postgresql':
            # Case-insensitive match to handle mixed-case emails in DB
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = %s', (email_lower,))
        else:
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email_lower,))
        
        row = cursor.fetchone()
        return User.from_row(row)
    finally:
        cursor.close()
        conn.close()


def authenticate_user(username_or_email: str, password: str) -> Optional[User]:
    """
    Authenticate user with username/email and password.
    
    Args:
        username_or_email: Username or email address
        password: Plain text password
        
    Returns:
        User object if authenticated, None otherwise
    """
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        # Try to find user by username or email (case-insensitive)
        login_value = username_or_email.strip().lower()
        
        if db_type == 'postgresql':
            # Use LOWER() for case-insensitive matching (handles mixed-case emails in DB)
            cursor.execute('''
                SELECT * FROM users 
                WHERE (LOWER(username) = %s OR LOWER(email) = %s) AND is_active = TRUE
            ''', (login_value, login_value))
        else:
            # SQLite LOWER() for consistency
            cursor.execute('''
                SELECT * FROM users 
                WHERE (LOWER(username) = ? OR LOWER(email) = ?) AND is_active = 1
            ''', (login_value, login_value))
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Login failed: User not found - '{username_or_email}' (searched for '{login_value}')")
            return None
        
        # Check if user is approved (admins are always approved)
        is_admin = bool(row['is_admin'] if hasattr(row, 'keys') else row[5])
        is_approved = bool(row['is_approved'] if hasattr(row, 'keys') else row[7])
        if not is_approved and not is_admin:
            logger.warning(f"Login failed: User not approved - {username_or_email}")
            return 'pending_approval'  # Special return value to indicate pending
        
        # Check password
        password_hash = row['password_hash'] if hasattr(row, 'keys') else row[3]
        if not check_password_hash(password_hash, password):
            logger.warning(f"Login failed: Invalid password - {username_or_email}")
            return None
        
        # Update last login time
        user_id = row['id'] if hasattr(row, 'keys') else row[0]
        if db_type == 'postgresql':
            cursor.execute('UPDATE users SET last_login = NOW() WHERE id = %s', (user_id,))
        else:
            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()
        
        logger.info(f"✅ User authenticated: {username_or_email}")
        return User.from_row(row)
        
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def update_user_password(user_id: int, new_password: str) -> bool:
    """Update user's password."""
    if not new_password or len(new_password) < 6:
        return False
    
    password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s
            ''', (password_hash, user_id))
        else:
            cursor.execute('''
                UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (password_hash, user_id))
        
        conn.commit()
        logger.info(f"✅ Password updated for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update password: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def update_user_settings(user_id: int, settings: dict) -> bool:
    """Update user's settings (merges with existing settings)."""
    import json
    
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current settings
        if db_type == 'postgresql':
            cursor.execute('SELECT settings_json FROM users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT settings_json FROM users WHERE id = ?', (user_id,))
        
        row = cursor.fetchone()
        current_settings = {}
        if row:
            settings_json = row[0] if isinstance(row, tuple) else row['settings_json']
            if settings_json:
                try:
                    current_settings = json.loads(settings_json) if isinstance(settings_json, str) else settings_json
                except:
                    current_settings = {}
        
        # Merge with new settings
        current_settings.update(settings)
        new_settings_json = json.dumps(current_settings)
        
        # Update database
        if db_type == 'postgresql':
            cursor.execute('''
                UPDATE users SET settings_json = %s, updated_at = NOW() WHERE id = %s
            ''', (new_settings_json, user_id))
        else:
            cursor.execute('''
                UPDATE users SET settings_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (new_settings_json, user_id))
        
        conn.commit()
        logger.info(f"✅ Settings updated for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update settings: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_all_users() -> list:
    """Get all users (admin function)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        rows = cursor.fetchall()
        return [User.from_row(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


def approve_user(user_id: int) -> bool:
    """Approve a pending user account (admin function)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('UPDATE users SET is_approved = TRUE WHERE id = %s', (user_id,))
        else:
            cursor.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
        
        conn.commit()
        affected = cursor.rowcount
        logger.info(f"✅ User {user_id} approved")
        return affected > 0
    except Exception as e:
        logger.error(f"❌ Failed to approve user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def reject_user(user_id: int) -> bool:
    """Reject (delete) a pending user account (admin function)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('DELETE FROM users WHERE id = %s AND is_approved = FALSE', (user_id,))
        else:
            cursor.execute('DELETE FROM users WHERE id = ? AND is_approved = 0', (user_id,))
        
        conn.commit()
        affected = cursor.rowcount
        logger.info(f"✅ User {user_id} rejected/deleted")
        return affected > 0
    except Exception as e:
        logger.error(f"❌ Failed to reject user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_pending_users() -> list:
    """Get all pending (unapproved) users (admin function)."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('SELECT * FROM users WHERE is_approved = FALSE ORDER BY created_at DESC')
        else:
            cursor.execute('SELECT * FROM users WHERE is_approved = 0 ORDER BY created_at DESC')
        rows = cursor.fetchall()
        return [User.from_row(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================
def login_user(user: User) -> bool:
    """Log in user by storing in session."""
    if not user:
        return False
    
    session['user_id'] = user.id
    session['username'] = user.username
    session['display_name'] = user.display_name
    session['is_admin'] = user.is_admin
    session.permanent = True  # Use permanent session (configurable timeout)
    
    logger.info(f"✅ User logged in: {user.username} (id={user.id})")
    return True


def logout_user():
    """Log out current user by clearing session."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"✅ User logged out: {username}")


def get_current_user() -> Optional[User]:
    """Get currently logged-in user from session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    # Use cached user from g if available
    if hasattr(g, 'current_user') and g.current_user:
        return g.current_user
    
    # Load from database
    user = get_user_by_id(user_id)
    if user:
        g.current_user = user
    return user


def get_current_user_id() -> Optional[int]:
    """Get current user's ID from session (fast, no DB query)."""
    return session.get('user_id')


def is_logged_in() -> bool:
    """Check if user is currently logged in."""
    return 'user_id' in session


# ============================================================================
# DECORATORS
# ============================================================================
def login_required(f):
    """
    Decorator to require login for a route.
    
    Usage:
        @app.route('/dashboard')
        @login_required
        def dashboard():
            return render_template('dashboard.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            # Store the original URL to redirect back after login
            session['next_url'] = request.url
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        
        # Verify user still exists and is active
        user = get_current_user()
        if not user or not user.is_active:
            logout_user()
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin privileges for a route.
    
    Usage:
        @app.route('/admin/users')
        @admin_required
        def admin_users():
            return render_template('admin_users.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            session['next_url'] = request.url
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user or not user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# DATA ISOLATION HELPERS
# ============================================================================
def get_user_accounts(user_id: int) -> list:
    """Get all accounts belonging to a specific user."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('SELECT * FROM accounts WHERE user_id = %s ORDER BY id', (user_id,))
        else:
            cursor.execute('SELECT * FROM accounts WHERE user_id = ? ORDER BY id', (user_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_user_traders(user_id: int) -> list:
    """Get all traders belonging to a specific user."""
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('SELECT * FROM traders WHERE user_id = %s ORDER BY id', (user_id,))
        else:
            cursor.execute('SELECT * FROM traders WHERE user_id = ? ORDER BY id', (user_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def assign_existing_data_to_user(user_id: int):
    """
    Assign all existing unassigned data to a user.
    Useful for initial setup when migrating from single-user to multi-user.
    """
    conn, db_type = get_auth_db_connection()
    cursor = conn.cursor()
    
    tables = ['accounts', 'traders', 'recorded_trades']
    
    try:
        for table in tables:
            try:
                if db_type == 'postgresql':
                    cursor.execute(f'UPDATE {table} SET user_id = %s WHERE user_id IS NULL', (user_id,))
                else:
                    cursor.execute(f'UPDATE {table} SET user_id = ? WHERE user_id IS NULL', (user_id,))
                logger.info(f"✅ Assigned unassigned {table} to user {user_id}")
            except Exception as e:
                logger.warning(f"Could not assign {table} to user: {e}")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to assign data to user: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# INITIALIZATION
# ============================================================================
def init_auth_system():
    """
    Initialize the authentication system.
    Call this on app startup.
    """
    logger.info("🔐 Initializing authentication system...")
    
    # Create users table
    if not init_users_table():
        logger.error("❌ Failed to create users table")
        return False
    
    # Add user_id to existing tables (safe - won't fail if column exists)
    add_user_id_to_tables()
    
    # Add is_approved column to existing users table (migration)
    migrate_add_is_approved()
    
    logger.info("✅ Authentication system initialized")
    return True


def create_initial_admin(username: str = 'admin', email: str = 'admin@justtrades.local',
                         password: str = None) -> Optional[User]:
    """
    Create initial admin user if no users exist.
    
    Args:
        username: Admin username (default: 'admin')
        email: Admin email
        password: Admin password (if None, generates random)
        
    Returns:
        User object if created, None otherwise
    """
    # Check if any users exist
    users = get_all_users()
    if users:
        logger.info("Users already exist, skipping initial admin creation")
        return None
    
    # Generate random password if not provided
    if not password:
        import secrets
        password = secrets.token_urlsafe(12)
        print(f"\n{'='*60}")
        print(f"🔐 INITIAL ADMIN CREATED")
        print(f"{'='*60}")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"{'='*60}")
        print(f"⚠️  SAVE THIS PASSWORD - IT WILL NOT BE SHOWN AGAIN!")
        print(f"{'='*60}\n")
    
    return create_user(username, email, password, display_name='Administrator', is_admin=True)


# ============================================================================
# CONTEXT PROCESSOR - Makes user available in all templates
# ============================================================================
def auth_context_processor():
    """
    Context processor to make auth functions available in templates.
    
    Usage in templates:
        {% if current_user %}
            Hello, {{ current_user.display_name }}!
        {% endif %}
    """
    return {
        'current_user': get_current_user(),
        'is_logged_in': is_logged_in()
    }

