"""
Subscription Models Module
==========================
Manages subscription plans and user subscriptions for Just.Trades.

Plans:
- Discord Basic ($39.99/mo) - Learning content, community access
- Discord Premium ($79.99/mo) - All indicators, charts, live streams
- Auto Trader Basic ($200/mo) - 5 accounts, no screener/signals
- Auto Trader Premium ($500/mo) - 100 accounts, 2 premium strategies, screener, signals
- Auto Trader Elite ($1000/mo) - Unlimited everything

Integration: Whop.com for payment processing
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger('subscriptions')

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')
SQLITE_PATH = os.environ.get('SQLITE_PATH', 'just_trades.db')


def get_subscription_db_connection():
    """Get database connection for subscription operations."""
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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn, 'sqlite'


# ============================================================================
# PLAN DEFINITIONS
# ============================================================================
# These define what each plan includes
PLAN_FEATURES = {
    'platform_basic': {
        'name': 'Basic+',
        'price': 200.00,
        'type': 'platform',
        'features': {
            'platform_access': True,
            'dashboard': True,
            'recorders': True,
            'auto_trader': True,
            'manual_copy_trader': True,
            'control_center': True,
            'quant_screener': False,
            'insider_signals': False,
            'premium_strategies': False,
            'api_access': False,
        },
        'limits': {
            'max_broker_accounts': 5,
            'max_strategies': -1,  # -1 = unlimited
            'max_recorders': -1,
        }
    },
    'platform_premium': {
        'name': 'Premium+',
        'price': 500.00,
        'type': 'platform',
        'features': {
            'platform_access': True,
            'dashboard': True,
            'recorders': True,
            'auto_trader': True,
            'manual_copy_trader': True,
            'control_center': True,
            'quant_screener': True,
            'insider_signals': True,
            'premium_strategies': True,  # JADNQ, JADVIX
            'api_access': False,
        },
        'limits': {
            'max_broker_accounts': 10,
            'max_strategies': -1,
            'max_recorders': -1,
            'premium_strategy_count': 2,  # JADNQ, JADVIX
        }
    },
    'platform_elite': {
        'name': 'Elite+',
        'price': 1000.00,
        'type': 'platform',
        'features': {
            'platform_access': True,
            'dashboard': True,
            'recorders': True,
            'auto_trader': True,
            'manual_copy_trader': True,
            'control_center': True,
            'quant_screener': True,
            'insider_signals': True,
            'premium_strategies': True,  # ALL 13 strategies
            'api_access': True,
            'priority_support': True,
        },
        'limits': {
            'max_broker_accounts': 25,
            'max_strategies': -1,
            'max_recorders': -1,
            'premium_strategy_count': -1,  # All strategies
        }
    },
}

# Premium strategies available
PREMIUM_STRATEGIES = ['JADNQ', 'JADVIX']  # Add more as you create them


# ============================================================================
# DATABASE SCHEMA
# ============================================================================
def init_subscription_tables():
    """Initialize subscription tables if they don't exist."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    id SERIAL PRIMARY KEY,
                    slug VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    price DECIMAL(10,2) NOT NULL,
                    plan_type VARCHAR(20) NOT NULL,
                    whop_product_id VARCHAR(100),
                    features_json TEXT DEFAULT '{}',
                    limits_json TEXT DEFAULT '{}',
                    is_active BOOLEAN DEFAULT TRUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    plan_slug VARCHAR(50) NOT NULL,
                    whop_membership_id VARCHAR(100),
                    whop_customer_id VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'active',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    trial_ends_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, plan_slug)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id 
                ON user_subscriptions(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_subscriptions_whop_membership 
                ON user_subscriptions(whop_membership_id)
            ''')
        else:
            # SQLite schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    plan_type TEXT NOT NULL,
                    whop_product_id TEXT,
                    features_json TEXT DEFAULT '{}',
                    limits_json TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_slug TEXT NOT NULL,
                    whop_membership_id TEXT,
                    whop_customer_id TEXT,
                    status TEXT DEFAULT 'active',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    trial_ends_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, plan_slug)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id 
                ON user_subscriptions(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_subscriptions_whop_membership 
                ON user_subscriptions(whop_membership_id)
            ''')
        
        conn.commit()
        logger.info("✅ Subscription tables initialized successfully")
        
        # Seed default plans
        seed_default_plans()
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize subscription tables: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def seed_default_plans():
    """Insert default subscription plans if they don't exist."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        for order, (slug, plan_data) in enumerate(PLAN_FEATURES.items()):
            features_json = json.dumps(plan_data['features'])
            limits_json = json.dumps(plan_data['limits'])
            
            if db_type == 'postgresql':
                cursor.execute('''
                    INSERT INTO subscription_plans 
                    (slug, name, price, plan_type, features_json, limits_json, display_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        name = EXCLUDED.name,
                        price = EXCLUDED.price,
                        features_json = EXCLUDED.features_json,
                        limits_json = EXCLUDED.limits_json
                ''', (slug, plan_data['name'], plan_data['price'], 
                      plan_data['type'], features_json, limits_json, order))
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO subscription_plans 
                    (slug, name, price, plan_type, features_json, limits_json, display_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (slug, plan_data['name'], plan_data['price'], 
                      plan_data['type'], features_json, limits_json, order))
        
        conn.commit()
        logger.info("✅ Default subscription plans seeded")
    except Exception as e:
        logger.error(f"❌ Failed to seed plans: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# SUBSCRIPTION QUERIES
# ============================================================================
def get_all_plans(plan_type: str = None) -> List[Dict]:
    """
    Get all subscription plans.
    
    Args:
        plan_type: Filter by 'discord' or 'platform' (optional)
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if plan_type:
            if db_type == 'postgresql':
                cursor.execute('''
                    SELECT * FROM subscription_plans 
                    WHERE is_active = TRUE AND plan_type = %s
                    ORDER BY display_order
                ''', (plan_type,))
            else:
                cursor.execute('''
                    SELECT * FROM subscription_plans 
                    WHERE is_active = 1 AND plan_type = ?
                    ORDER BY display_order
                ''', (plan_type,))
        else:
            if db_type == 'postgresql':
                cursor.execute('''
                    SELECT * FROM subscription_plans 
                    WHERE is_active = TRUE
                    ORDER BY display_order
                ''')
            else:
                cursor.execute('''
                    SELECT * FROM subscription_plans 
                    WHERE is_active = 1
                    ORDER BY display_order
                ''')
        
        rows = cursor.fetchall()
        plans = []
        for row in rows:
            plan = dict(row)
            plan['features'] = json.loads(plan.get('features_json', '{}'))
            plan['limits'] = json.loads(plan.get('limits_json', '{}'))
            plans.append(plan)
        return plans
    finally:
        cursor.close()
        conn.close()


def get_plan_by_slug(slug: str) -> Optional[Dict]:
    """Get a specific plan by its slug."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('SELECT * FROM subscription_plans WHERE slug = %s', (slug,))
        else:
            cursor.execute('SELECT * FROM subscription_plans WHERE slug = ?', (slug,))
        
        row = cursor.fetchone()
        if row:
            plan = dict(row)
            plan['features'] = json.loads(plan.get('features_json', '{}'))
            plan['limits'] = json.loads(plan.get('limits_json', '{}'))
            return plan
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_subscription(user_id: int, plan_type: str = 'platform') -> Optional[Dict]:
    """
    Get a user's active subscription.
    
    Args:
        user_id: The user's ID
        plan_type: 'platform' or 'discord'
    
    Returns:
        Subscription dict with plan details, or None if no active subscription
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.price, sp.features_json, sp.limits_json
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.user_id = %s 
                  AND sp.plan_type = %s
                  AND us.status IN ('active', 'trialing')
                  AND (us.expires_at IS NULL OR us.expires_at > NOW())
                ORDER BY sp.price DESC
                LIMIT 1
            ''', (user_id, plan_type))
        else:
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.price, sp.features_json, sp.limits_json
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.user_id = ? 
                  AND sp.plan_type = ?
                  AND us.status IN ('active', 'trialing')
                  AND (us.expires_at IS NULL OR us.expires_at > datetime('now'))
                ORDER BY sp.price DESC
                LIMIT 1
            ''', (user_id, plan_type))
        
        row = cursor.fetchone()
        if row:
            sub = dict(row)
            sub['features'] = json.loads(sub.get('features_json', '{}'))
            sub['limits'] = json.loads(sub.get('limits_json', '{}'))
            return sub
        return None
    finally:
        cursor.close()
        conn.close()


def get_all_user_subscriptions(user_id: int) -> List[Dict]:
    """Get all subscriptions for a user (active and inactive)."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.price, sp.plan_type
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.user_id = %s
                ORDER BY us.created_at DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.price, sp.plan_type
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.user_id = ?
                ORDER BY us.created_at DESC
            ''', (user_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================================
def create_subscription(user_id: int, plan_slug: str, whop_membership_id: str = None,
                        whop_customer_id: str = None, trial_days: int = 0) -> Optional[int]:
    """
    Create a new subscription for a user.
    
    Returns:
        Subscription ID if created, None if failed
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        status = 'trialing' if trial_days > 0 else 'active'
        trial_ends = None
        if trial_days > 0:
            trial_ends = datetime.now() + timedelta(days=trial_days)
        
        if db_type == 'postgresql':
            cursor.execute('''
                INSERT INTO user_subscriptions 
                (user_id, plan_slug, whop_membership_id, whop_customer_id, status, trial_ends_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, plan_slug) DO UPDATE SET
                    whop_membership_id = EXCLUDED.whop_membership_id,
                    whop_customer_id = EXCLUDED.whop_customer_id,
                    status = EXCLUDED.status,
                    trial_ends_at = EXCLUDED.trial_ends_at,
                    updated_at = NOW()
                RETURNING id
            ''', (user_id, plan_slug, whop_membership_id, whop_customer_id, status, trial_ends))
            result = cursor.fetchone()
            sub_id = result['id'] if result else None
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO user_subscriptions 
                (user_id, plan_slug, whop_membership_id, whop_customer_id, status, trial_ends_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (user_id, plan_slug, whop_membership_id, whop_customer_id, status, trial_ends))
            sub_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"✅ Created subscription: user={user_id}, plan={plan_slug}")
        return sub_id
    except Exception as e:
        logger.error(f"❌ Failed to create subscription: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def link_pending_subscription(user_id: int, email: str) -> bool:
    """
    Link a pending subscription (user_id=0) to a real user.

    When a Whop webhook fires before the user registers, the subscription is created
    with user_id=0. This function finds those pending rows by email (stored in
    whop_customer_id or looked up via Whop API) and updates them to the real user_id.

    Returns True if a pending subscription was linked, False otherwise.
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()

    try:
        placeholder = '%s' if db_type == 'postgresql' else '?'
        # Find subscriptions with user_id=0 — these are pending Whop purchases
        cursor.execute(
            f"SELECT id, plan_slug, whop_membership_id FROM user_subscriptions "
            f"WHERE user_id = 0 AND status IN ('active', 'trialing')"
        )
        rows = cursor.fetchall()

        if not rows:
            return False

        # For each pending subscription, check if the Whop membership email matches
        linked = False
        for row in rows:
            row_dict = dict(row)
            membership_id = row_dict.get('whop_membership_id')
            if not membership_id:
                continue

            # Check via Whop API if this membership belongs to this email
            try:
                from whop_integration import verify_membership
                membership = verify_membership(membership_id)
                if membership and membership.get('user_email', '').lower() == email.lower():
                    # Match — update user_id
                    sub_id = row_dict['id']
                    if db_type == 'postgresql':
                        cursor.execute(
                            f"UPDATE user_subscriptions SET user_id = {placeholder}, updated_at = NOW() WHERE id = {placeholder}",
                            (user_id, sub_id)
                        )
                    else:
                        cursor.execute(
                            f"UPDATE user_subscriptions SET user_id = {placeholder}, updated_at = datetime('now') WHERE id = {placeholder}",
                            (user_id, sub_id)
                        )
                    linked = True
                    logger.info(f"Linked pending subscription {sub_id} ({row_dict.get('plan_slug')}) to user {user_id}")
            except Exception as e:
                logger.warning(f"Could not verify membership {membership_id}: {e}")
                continue

        if linked:
            conn.commit()
        return linked
    except Exception as e:
        logger.error(f"link_pending_subscription error: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def update_subscription_status(user_id: int = None, whop_membership_id: str = None,
                                status: str = 'active', expires_at: datetime = None) -> bool:
    """
    Update a subscription's status.
    
    Can lookup by user_id or whop_membership_id.
    Status can be: 'active', 'trialing', 'cancelled', 'expired', 'past_due'
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if whop_membership_id:
            if db_type == 'postgresql':
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = %s, expires_at = %s, updated_at = NOW()
                    WHERE whop_membership_id = %s
                ''', (status, expires_at, whop_membership_id))
            else:
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = ?, expires_at = ?, updated_at = datetime('now')
                    WHERE whop_membership_id = ?
                ''', (status, expires_at, whop_membership_id))
        elif user_id:
            if db_type == 'postgresql':
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = %s, expires_at = %s, updated_at = NOW()
                    WHERE user_id = %s
                ''', (status, expires_at, user_id))
            else:
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = ?, expires_at = ?, updated_at = datetime('now')
                    WHERE user_id = ?
                ''', (status, expires_at, user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"❌ Failed to update subscription: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def cancel_subscription(user_id: int = None, whop_membership_id: str = None) -> bool:
    """Cancel a subscription (sets status to cancelled)."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if whop_membership_id:
            if db_type == 'postgresql':
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
                    WHERE whop_membership_id = %s
                ''', (whop_membership_id,))
            else:
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = 'cancelled', cancelled_at = datetime('now'), updated_at = datetime('now')
                    WHERE whop_membership_id = ?
                ''', (whop_membership_id,))
        elif user_id:
            if db_type == 'postgresql':
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
                    WHERE user_id = %s
                ''', (user_id,))
            else:
                cursor.execute('''
                    UPDATE user_subscriptions 
                    SET status = 'cancelled', cancelled_at = datetime('now'), updated_at = datetime('now')
                    WHERE user_id = ?
                ''', (user_id,))
        
        conn.commit()
        logger.info(f"✅ Subscription cancelled")
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"❌ Failed to cancel subscription: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# FEATURE ACCESS CHECKS
# ============================================================================
def check_feature_access(user_id: int, feature_name: str) -> bool:
    """
    Check if a user has access to a specific feature.
    
    Args:
        user_id: The user's ID
        feature_name: Feature to check (e.g., 'quant_screener', 'insider_signals')
    
    Returns:
        True if user has access, False otherwise
    """
    subscription = get_user_subscription(user_id, plan_type='platform')
    
    if not subscription:
        return False
    
    features = subscription.get('features', {})
    return features.get(feature_name, False)


def check_limit(user_id: int, limit_name: str, current_count: int) -> bool:
    """
    Check if a user is within their plan limits.
    
    Args:
        user_id: The user's ID
        limit_name: Limit to check (e.g., 'max_broker_accounts')
        current_count: Current count of the resource
    
    Returns:
        True if within limit, False if at/over limit
    """
    subscription = get_user_subscription(user_id, plan_type='platform')
    
    if not subscription:
        return False
    
    limits = subscription.get('limits', {})
    max_limit = limits.get(limit_name, 0)
    
    # -1 means unlimited
    if max_limit == -1:
        return True
    
    return current_count < max_limit


def get_user_plan_tier(user_id: int) -> str:
    """
    Get the user's current plan tier.
    
    Returns:
        'none', 'basic', 'premium', or 'elite'
    """
    subscription = get_user_subscription(user_id, plan_type='platform')
    
    if not subscription:
        return 'none'
    
    plan_slug = subscription.get('plan_slug', '')
    
    if 'elite' in plan_slug:
        return 'elite'
    elif 'premium' in plan_slug:
        return 'premium'
    elif 'basic' in plan_slug:
        return 'basic'
    
    return 'none'


def get_feature_status(user_id: int) -> Dict[str, Any]:
    """
    Get complete feature status for a user.
    
    Returns dict with all features and their access status.
    Useful for rendering UI with greyed-out features.
    """
    subscription = get_user_subscription(user_id, plan_type='platform')
    tier = get_user_plan_tier(user_id)
    
    if not subscription:
        return {
            'has_subscription': False,
            'tier': 'none',
            'plan_name': None,
            'features': {
                'platform_access': False,
                'dashboard': False,
                'recorders': False,
                'auto_trader': False,
                'manual_copy_trader': False,
                'control_center': False,
                'quant_screener': False,
                'insider_signals': False,
                'premium_strategies': False,
                'api_access': False,
            },
            'limits': {
                'max_broker_accounts': 0,
                'max_strategies': 0,
                'max_recorders': 0,
            }
        }
    
    return {
        'has_subscription': True,
        'tier': tier,
        'plan_name': subscription.get('plan_name'),
        'plan_slug': subscription.get('plan_slug'),
        'status': subscription.get('status'),
        'expires_at': subscription.get('expires_at'),
        'trial_ends_at': subscription.get('trial_ends_at'),
        'features': subscription.get('features', {}),
        'limits': subscription.get('limits', {}),
    }


# ============================================================================
# WHOP INTEGRATION HELPERS
# ============================================================================
def get_subscription_by_whop_membership(whop_membership_id: str) -> Optional[Dict]:
    """Get subscription by Whop membership ID."""
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.features_json, sp.limits_json
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.whop_membership_id = %s
            ''', (whop_membership_id,))
        else:
            cursor.execute('''
                SELECT us.*, sp.name as plan_name, sp.features_json, sp.limits_json
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_slug = sp.slug
                WHERE us.whop_membership_id = ?
            ''', (whop_membership_id,))
        
        row = cursor.fetchone()
        if row:
            sub = dict(row)
            sub['features'] = json.loads(sub.get('features_json', '{}'))
            sub['limits'] = json.loads(sub.get('limits_json', '{}'))
            return sub
        return None
    finally:
        cursor.close()
        conn.close()


def link_whop_to_user(user_id: int, whop_membership_id: str, whop_customer_id: str = None) -> bool:
    """
    Link a Whop membership to a user account.
    
    Called when user verifies their Whop purchase on the platform.
    """
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    
    try:
        if db_type == 'postgresql':
            cursor.execute('''
                UPDATE user_subscriptions 
                SET user_id = %s, whop_customer_id = %s, updated_at = NOW()
                WHERE whop_membership_id = %s
            ''', (user_id, whop_customer_id, whop_membership_id))
        else:
            cursor.execute('''
                UPDATE user_subscriptions 
                SET user_id = ?, whop_customer_id = ?, updated_at = datetime('now')
                WHERE whop_membership_id = ?
            ''', (user_id, whop_customer_id, whop_membership_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"❌ Failed to link Whop to user: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# INITIALIZATION
# ============================================================================
def init_subscription_system():
    """Initialize the subscription system. Call on app startup."""
    logger.info("💳 Initializing subscription system...")
    
    if not init_subscription_tables():
        logger.error("❌ Failed to initialize subscription tables")
        return False
    
    logger.info("✅ Subscription system initialized")
    return True


# ============================================================================
# TESTING HELPERS (For local development)
# ============================================================================
def grant_test_subscription(user_id: int, plan_slug: str = 'platform_basic') -> bool:
    """
    Grant a test subscription to a user (for local testing only).
    
    DO NOT USE IN PRODUCTION - bypasses payment verification!
    """
    logger.warning(f"⚠️ GRANTING TEST SUBSCRIPTION - user={user_id}, plan={plan_slug}")
    sub_id = create_subscription(
        user_id=user_id,
        plan_slug=plan_slug,
        whop_membership_id=f"test_{user_id}_{plan_slug}",
        trial_days=0
    )
    return sub_id is not None


def revoke_test_subscription(user_id: int) -> bool:
    """Revoke a test subscription."""
    return cancel_subscription(user_id=user_id)


if __name__ == '__main__':
    # Test the module
    logging.basicConfig(level=logging.INFO)
    
    print("Initializing subscription system...")
    init_subscription_system()
    
    print("\nAll plans:")
    for plan in get_all_plans():
        print(f"  - {plan['name']}: ${plan['price']}/mo ({plan['plan_type']})")
    
    print("\nPlatform plans only:")
    for plan in get_all_plans(plan_type='platform'):
        print(f"  - {plan['name']}: ${plan['price']}/mo")
        print(f"    Features: {list(k for k,v in plan['features'].items() if v)}")
        print(f"    Limits: {plan['limits']}")
