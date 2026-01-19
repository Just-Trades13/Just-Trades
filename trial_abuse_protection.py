"""
Trial Abuse Protection Module
=============================
Prevents free trial abuse by tracking multiple fingerprints:
- Device fingerprint (via FingerprintJS)
- IP address
- Payment method fingerprint (card last 4 + brand)
- Whop user ID
- Email patterns

When abuse is detected, users are blocked from accessing the platform
even if they obtained a trial through Whop.
"""

import os
import re
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from functools import wraps

logger = logging.getLogger('trial_abuse')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Disposable email domains to flag
DISPOSABLE_EMAIL_DOMAINS = {
    'tempmail.com', 'throwaway.email', 'guerrillamail.com', 'mailinator.com',
    'temp-mail.org', '10minutemail.com', 'fakeinbox.com', 'trashmail.com',
    'sharklasers.com', 'guerrillamail.info', 'grr.la', 'guerrillamail.biz',
    'guerrillamail.de', 'guerrillamail.net', 'guerrillamail.org', 'spam4.me',
    'dispostable.com', 'yopmail.com', 'tempail.com', 'mohmal.com',
    'emailondeck.com', 'getnada.com', 'maildrop.cc', 'mailnesia.com',
    'mintemail.com', 'mytemp.email', 'tempr.email', 'discard.email',
    'discardmail.com', 'spamgourmet.com', 'getairmail.com', 'moakt.com',
    'tempmailo.com', 'burnermail.io', 'inboxkitten.com'
}

# How long to remember trial usage (days)
TRIAL_MEMORY_DAYS = 365

# Similarity threshold for email patterns (0-1)
EMAIL_SIMILARITY_THRESHOLD = 0.7


# ============================================================================
# DATABASE SETUP
# ============================================================================

def get_db_connection():
    """Get database connection - imports from main app"""
    from ultra_simple_server import get_db_connection as get_conn
    return get_conn()


def init_trial_abuse_tables():
    """Create trial abuse tracking tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if PostgreSQL or SQLite
    is_postgres = 'psycopg2' in str(type(conn))

    if is_postgres:
        # PostgreSQL schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_fingerprints (
                id SERIAL PRIMARY KEY,
                fingerprint_type VARCHAR(50) NOT NULL,
                fingerprint_value VARCHAR(500) NOT NULL,
                whop_membership_id VARCHAR(100),
                whop_user_id VARCHAR(100),
                email VARCHAR(255),
                ip_address VARCHAR(45),
                user_agent TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_count INTEGER DEFAULT 1,
                is_blocked BOOLEAN DEFAULT FALSE,
                block_reason TEXT,
                metadata JSONB DEFAULT '{}',
                UNIQUE(fingerprint_type, fingerprint_value)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_abuse_log (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                fingerprint_type VARCHAR(50),
                fingerprint_value VARCHAR(500),
                whop_membership_id VARCHAR(100),
                email VARCHAR(255),
                ip_address VARCHAR(45),
                details JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Indexes for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fingerprints_value
            ON trial_fingerprints(fingerprint_type, fingerprint_value)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fingerprints_email
            ON trial_fingerprints(email)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fingerprints_ip
            ON trial_fingerprints(ip_address)
        ''')

    else:
        # SQLite schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_type TEXT NOT NULL,
                fingerprint_value TEXT NOT NULL,
                whop_membership_id TEXT,
                whop_user_id TEXT,
                email TEXT,
                ip_address TEXT,
                user_agent TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_count INTEGER DEFAULT 1,
                is_blocked INTEGER DEFAULT 0,
                block_reason TEXT,
                metadata TEXT DEFAULT '{}',
                UNIQUE(fingerprint_type, fingerprint_value)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_abuse_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                fingerprint_type TEXT,
                fingerprint_value TEXT,
                whop_membership_id TEXT,
                email TEXT,
                ip_address TEXT,
                details TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    logger.info("✅ Trial abuse protection tables initialized")


# ============================================================================
# FINGERPRINT TRACKING
# ============================================================================

def record_fingerprint(
    fingerprint_type: str,
    fingerprint_value: str,
    whop_membership_id: str = None,
    whop_user_id: str = None,
    email: str = None,
    ip_address: str = None,
    user_agent: str = None,
    metadata: dict = None
) -> Tuple[bool, str]:
    """
    Record a fingerprint and check if it's been used before.

    Returns:
        Tuple of (is_abuse, message)
    """
    if not fingerprint_value:
        return False, "No fingerprint provided"

    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    # Check if this fingerprint exists
    if is_postgres:
        cursor.execute('''
            SELECT id, trial_count, is_blocked, block_reason, first_seen, email
            FROM trial_fingerprints
            WHERE fingerprint_type = %s AND fingerprint_value = %s
        ''', (fingerprint_type, fingerprint_value))
    else:
        cursor.execute('''
            SELECT id, trial_count, is_blocked, block_reason, first_seen, email
            FROM trial_fingerprints
            WHERE fingerprint_type = ? AND fingerprint_value = ?
        ''', (fingerprint_type, fingerprint_value))

    row = cursor.fetchone()

    if row:
        # Fingerprint exists - this is a repeat trial attempt
        fp_id, trial_count, is_blocked, block_reason, first_seen, original_email = row

        # Update the record
        new_count = trial_count + 1
        metadata_json = json.dumps(metadata or {})

        if is_postgres:
            cursor.execute('''
                UPDATE trial_fingerprints
                SET trial_count = %s, last_seen = CURRENT_TIMESTAMP,
                    whop_membership_id = COALESCE(%s, whop_membership_id),
                    whop_user_id = COALESCE(%s, whop_user_id),
                    ip_address = COALESCE(%s, ip_address),
                    is_blocked = TRUE,
                    block_reason = COALESCE(block_reason, %s)
                WHERE id = %s
            ''', (new_count, whop_membership_id, whop_user_id, ip_address,
                  f'Repeat trial attempt #{new_count}', fp_id))
        else:
            cursor.execute('''
                UPDATE trial_fingerprints
                SET trial_count = ?, last_seen = CURRENT_TIMESTAMP,
                    whop_membership_id = COALESCE(?, whop_membership_id),
                    whop_user_id = COALESCE(?, whop_user_id),
                    ip_address = COALESCE(?, ip_address),
                    is_blocked = 1,
                    block_reason = COALESCE(block_reason, ?)
                WHERE id = ?
            ''', (new_count, whop_membership_id, whop_user_id, ip_address,
                  f'Repeat trial attempt #{new_count}', fp_id))

        # Log the abuse attempt
        log_abuse_event(
            'repeat_trial_attempt',
            fingerprint_type,
            fingerprint_value,
            whop_membership_id,
            email,
            ip_address,
            {'trial_count': new_count, 'original_email': original_email}
        )

        conn.commit()
        logger.warning(f"🚨 Trial abuse detected: {fingerprint_type}={fingerprint_value[:20]}... (attempt #{new_count})")
        return True, f"This {fingerprint_type} has already been used for a free trial"

    else:
        # New fingerprint - record it
        metadata_json = json.dumps(metadata or {})

        if is_postgres:
            cursor.execute('''
                INSERT INTO trial_fingerprints
                (fingerprint_type, fingerprint_value, whop_membership_id, whop_user_id,
                 email, ip_address, user_agent, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (fingerprint_type, fingerprint_value, whop_membership_id, whop_user_id,
                  email, ip_address, user_agent, metadata_json))
        else:
            cursor.execute('''
                INSERT INTO trial_fingerprints
                (fingerprint_type, fingerprint_value, whop_membership_id, whop_user_id,
                 email, ip_address, user_agent, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fingerprint_type, fingerprint_value, whop_membership_id, whop_user_id,
                  email, ip_address, user_agent, metadata_json))

        conn.commit()
        logger.info(f"✅ New fingerprint recorded: {fingerprint_type}")
        return False, "Fingerprint recorded"


def check_fingerprint(fingerprint_type: str, fingerprint_value: str) -> Tuple[bool, str]:
    """
    Check if a fingerprint is blocked.

    Returns:
        Tuple of (is_blocked, reason)
    """
    if not fingerprint_value:
        return False, ""

    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    if is_postgres:
        cursor.execute('''
            SELECT is_blocked, block_reason, trial_count
            FROM trial_fingerprints
            WHERE fingerprint_type = %s AND fingerprint_value = %s
        ''', (fingerprint_type, fingerprint_value))
    else:
        cursor.execute('''
            SELECT is_blocked, block_reason, trial_count
            FROM trial_fingerprints
            WHERE fingerprint_type = ? AND fingerprint_value = ?
        ''', (fingerprint_type, fingerprint_value))

    row = cursor.fetchone()

    if row:
        is_blocked, block_reason, trial_count = row
        if is_blocked:
            return True, block_reason or f"Trial already used ({trial_count} attempts)"
        elif trial_count > 1:
            return True, f"Multiple trial attempts detected ({trial_count})"

    return False, ""


def log_abuse_event(
    event_type: str,
    fingerprint_type: str = None,
    fingerprint_value: str = None,
    whop_membership_id: str = None,
    email: str = None,
    ip_address: str = None,
    details: dict = None
):
    """Log an abuse event for auditing"""
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    details_json = json.dumps(details or {})

    if is_postgres:
        cursor.execute('''
            INSERT INTO trial_abuse_log
            (event_type, fingerprint_type, fingerprint_value, whop_membership_id, email, ip_address, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (event_type, fingerprint_type, fingerprint_value, whop_membership_id, email, ip_address, details_json))
    else:
        cursor.execute('''
            INSERT INTO trial_abuse_log
            (event_type, fingerprint_type, fingerprint_value, whop_membership_id, email, ip_address, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (event_type, fingerprint_type, fingerprint_value, whop_membership_id, email, ip_address, details_json))

    conn.commit()


# ============================================================================
# EMAIL ANALYSIS
# ============================================================================

def is_disposable_email(email: str) -> bool:
    """Check if email is from a disposable email provider"""
    if not email:
        return False

    domain = email.lower().split('@')[-1]
    return domain in DISPOSABLE_EMAIL_DOMAINS


def get_email_fingerprint(email: str) -> str:
    """
    Create a fingerprint from email that catches pattern abuse.
    E.g., john.doe+1@gmail.com and johndoe+2@gmail.com are same person.
    """
    if not email:
        return ""

    email = email.lower().strip()
    local, domain = email.split('@') if '@' in email else (email, '')

    # Remove dots from local part (Gmail ignores them)
    local = local.replace('.', '')

    # Remove plus addressing
    local = local.split('+')[0]

    # Create fingerprint
    return f"{local}@{domain}"


def check_similar_emails(email: str) -> List[Dict]:
    """Find similar emails that might indicate abuse"""
    if not email:
        return []

    email_fp = get_email_fingerprint(email)

    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    # Get all emails with trials
    if is_postgres:
        cursor.execute('''
            SELECT DISTINCT email, trial_count, first_seen
            FROM trial_fingerprints
            WHERE fingerprint_type = 'email' AND email IS NOT NULL
        ''')
    else:
        cursor.execute('''
            SELECT DISTINCT email, trial_count, first_seen
            FROM trial_fingerprints
            WHERE fingerprint_type = 'email' AND email IS NOT NULL
        ''')

    similar = []
    for row in cursor.fetchall():
        stored_email, trial_count, first_seen = row
        stored_fp = get_email_fingerprint(stored_email)

        if stored_fp == email_fp and stored_email != email:
            similar.append({
                'email': stored_email,
                'trial_count': trial_count,
                'first_seen': str(first_seen)
            })

    return similar


# ============================================================================
# COMPREHENSIVE ABUSE CHECK
# ============================================================================

def check_trial_abuse(
    device_fingerprint: str = None,
    ip_address: str = None,
    email: str = None,
    card_fingerprint: str = None,
    whop_user_id: str = None
) -> Tuple[bool, str, List[str]]:
    """
    Comprehensive trial abuse check across all fingerprint types.

    Returns:
        Tuple of (is_blocked, reason, list_of_flags)
    """
    flags = []
    block_reasons = []

    # Check device fingerprint
    if device_fingerprint:
        is_blocked, reason = check_fingerprint('device', device_fingerprint)
        if is_blocked:
            flags.append('device_reuse')
            block_reasons.append(f"Device: {reason}")

    # Check IP address (less strict - just flag, don't block)
    if ip_address:
        is_blocked, reason = check_fingerprint('ip', ip_address)
        if is_blocked:
            flags.append('ip_reuse')
            # Don't add to block_reasons - IPs can be shared

    # Check email
    if email:
        # Check disposable email
        if is_disposable_email(email):
            flags.append('disposable_email')
            block_reasons.append("Disposable email addresses are not allowed for free trials")

        # Check email fingerprint (catches +addressing abuse)
        email_fp = get_email_fingerprint(email)
        is_blocked, reason = check_fingerprint('email_fingerprint', email_fp)
        if is_blocked:
            flags.append('email_pattern_reuse')
            block_reasons.append(f"Email pattern: {reason}")

        # Check for similar emails
        similar = check_similar_emails(email)
        if similar:
            flags.append('similar_email_found')
            block_reasons.append(f"Similar email detected: {similar[0]['email']}")

    # Check card fingerprint (most definitive)
    if card_fingerprint:
        is_blocked, reason = check_fingerprint('card', card_fingerprint)
        if is_blocked:
            flags.append('card_reuse')
            block_reasons.append(f"Payment method: {reason}")

    # Check Whop user ID
    if whop_user_id:
        is_blocked, reason = check_fingerprint('whop_user', whop_user_id)
        if is_blocked:
            flags.append('whop_user_reuse')
            block_reasons.append(f"Whop account: {reason}")

    # Determine if should block
    # Block if: device reuse, card reuse, email pattern reuse, or disposable email
    should_block = bool(set(flags) & {'device_reuse', 'card_reuse', 'email_pattern_reuse', 'disposable_email'})

    reason = "; ".join(block_reasons) if block_reasons else ""

    if should_block:
        logger.warning(f"🚨 Trial abuse blocked: {flags}")

    return should_block, reason, flags


def record_trial_start(
    whop_membership_id: str,
    whop_user_id: str,
    email: str,
    device_fingerprint: str = None,
    ip_address: str = None,
    card_fingerprint: str = None,
    user_agent: str = None,
    metadata: dict = None
) -> Tuple[bool, str]:
    """
    Record all fingerprints when a trial starts.
    Call this from the Whop webhook handler.

    Returns:
        Tuple of (is_abuse, message)
    """
    abuse_detected = False
    messages = []

    # Record device fingerprint
    if device_fingerprint:
        is_abuse, msg = record_fingerprint(
            'device', device_fingerprint,
            whop_membership_id, whop_user_id, email, ip_address, user_agent, metadata
        )
        if is_abuse:
            abuse_detected = True
            messages.append(msg)

    # Record IP
    if ip_address:
        record_fingerprint(
            'ip', ip_address,
            whop_membership_id, whop_user_id, email, ip_address, user_agent, metadata
        )

    # Record email fingerprint
    if email:
        email_fp = get_email_fingerprint(email)
        is_abuse, msg = record_fingerprint(
            'email_fingerprint', email_fp,
            whop_membership_id, whop_user_id, email, ip_address, user_agent, metadata
        )
        if is_abuse:
            abuse_detected = True
            messages.append(msg)

    # Record card fingerprint
    if card_fingerprint:
        is_abuse, msg = record_fingerprint(
            'card', card_fingerprint,
            whop_membership_id, whop_user_id, email, ip_address, user_agent, metadata
        )
        if is_abuse:
            abuse_detected = True
            messages.append(msg)

    # Record Whop user ID
    if whop_user_id:
        is_abuse, msg = record_fingerprint(
            'whop_user', whop_user_id,
            whop_membership_id, whop_user_id, email, ip_address, user_agent, metadata
        )
        if is_abuse:
            abuse_detected = True
            messages.append(msg)

    return abuse_detected, "; ".join(messages) if messages else "Trial recorded"


# ============================================================================
# ADMIN FUNCTIONS
# ============================================================================

def get_abuse_stats() -> Dict:
    """Get trial abuse statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    stats = {}

    # Total fingerprints
    cursor.execute('SELECT COUNT(*) FROM trial_fingerprints')
    stats['total_fingerprints'] = cursor.fetchone()[0]

    # Blocked fingerprints
    if is_postgres:
        cursor.execute('SELECT COUNT(*) FROM trial_fingerprints WHERE is_blocked = TRUE')
    else:
        cursor.execute('SELECT COUNT(*) FROM trial_fingerprints WHERE is_blocked = 1')
    stats['blocked_fingerprints'] = cursor.fetchone()[0]

    # Repeat offenders (trial_count > 1)
    cursor.execute('SELECT COUNT(*) FROM trial_fingerprints WHERE trial_count > 1')
    stats['repeat_offenders'] = cursor.fetchone()[0]

    # By fingerprint type
    cursor.execute('''
        SELECT fingerprint_type, COUNT(*), SUM(trial_count)
        FROM trial_fingerprints
        GROUP BY fingerprint_type
    ''')
    stats['by_type'] = {row[0]: {'count': row[1], 'total_attempts': row[2]} for row in cursor.fetchall()}

    # Recent abuse events
    cursor.execute('''
        SELECT COUNT(*) FROM trial_abuse_log
        WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
    ''' if is_postgres else '''
        SELECT COUNT(*) FROM trial_abuse_log
        WHERE created_at > datetime('now', '-1 day')
    ''')
    stats['abuse_events_24h'] = cursor.fetchone()[0]

    return stats


def get_flagged_users(limit: int = 50) -> List[Dict]:
    """Get list of flagged/blocked users"""
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    if is_postgres:
        cursor.execute('''
            SELECT fingerprint_type, fingerprint_value, email, ip_address,
                   trial_count, block_reason, first_seen, last_seen
            FROM trial_fingerprints
            WHERE is_blocked = TRUE OR trial_count > 1
            ORDER BY last_seen DESC
            LIMIT %s
        ''', (limit,))
    else:
        cursor.execute('''
            SELECT fingerprint_type, fingerprint_value, email, ip_address,
                   trial_count, block_reason, first_seen, last_seen
            FROM trial_fingerprints
            WHERE is_blocked = 1 OR trial_count > 1
            ORDER BY last_seen DESC
            LIMIT ?
        ''', (limit,))

    users = []
    for row in cursor.fetchall():
        users.append({
            'fingerprint_type': row[0],
            'fingerprint_value': row[1][:30] + '...' if len(row[1]) > 30 else row[1],
            'email': row[2],
            'ip_address': row[3],
            'trial_count': row[4],
            'block_reason': row[5],
            'first_seen': str(row[6]),
            'last_seen': str(row[7])
        })

    return users


def unblock_fingerprint(fingerprint_type: str, fingerprint_value: str) -> bool:
    """Manually unblock a fingerprint (for legitimate users)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = 'psycopg2' in str(type(conn))

    if is_postgres:
        cursor.execute('''
            UPDATE trial_fingerprints
            SET is_blocked = FALSE, block_reason = 'Manually unblocked'
            WHERE fingerprint_type = %s AND fingerprint_value = %s
        ''', (fingerprint_type, fingerprint_value))
    else:
        cursor.execute('''
            UPDATE trial_fingerprints
            SET is_blocked = 0, block_reason = 'Manually unblocked'
            WHERE fingerprint_type = ? AND fingerprint_value = ?
        ''', (fingerprint_type, fingerprint_value))

    conn.commit()

    log_abuse_event('manual_unblock', fingerprint_type, fingerprint_value)
    logger.info(f"✅ Manually unblocked: {fingerprint_type}={fingerprint_value[:20]}...")

    return cursor.rowcount > 0


# ============================================================================
# FLASK INTEGRATION
# ============================================================================

def register_trial_abuse_routes(app):
    """Register Flask routes for trial abuse protection"""
    from flask import request, jsonify, session

    @app.route('/api/trial-abuse/record-fingerprint', methods=['POST'])
    def api_record_device_fingerprint():
        """
        Record device fingerprint from frontend.
        Call this when user logs in or accesses trial features.
        """
        data = request.get_json() or {}

        device_fp = data.get('fingerprint')
        if not device_fp:
            return jsonify({'success': False, 'error': 'No fingerprint provided'}), 400

        # Get user info from session if available
        user_id = session.get('user_id')
        user_email = session.get('email')

        # Get IP
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        user_agent = request.headers.get('User-Agent', '')

        # Check if blocked
        is_blocked, reason, flags = check_trial_abuse(
            device_fingerprint=device_fp,
            ip_address=ip_address,
            email=user_email
        )

        if is_blocked:
            return jsonify({
                'success': False,
                'blocked': True,
                'reason': reason,
                'flags': flags
            })

        # Record the fingerprint
        record_fingerprint(
            'device', device_fp,
            email=user_email,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return jsonify({
            'success': True,
            'blocked': False
        })

    @app.route('/api/trial-abuse/check', methods=['POST'])
    def api_check_trial_abuse():
        """Check if current user/device is flagged for trial abuse"""
        data = request.get_json() or {}

        device_fp = data.get('fingerprint')
        email = data.get('email') or session.get('email')

        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        is_blocked, reason, flags = check_trial_abuse(
            device_fingerprint=device_fp,
            ip_address=ip_address,
            email=email
        )

        return jsonify({
            'blocked': is_blocked,
            'reason': reason if is_blocked else None,
            'flags': flags
        })

    @app.route('/api/admin/trial-abuse/stats', methods=['GET'])
    def api_trial_abuse_stats():
        """Get trial abuse statistics (admin only)"""
        # TODO: Add admin auth check
        stats = get_abuse_stats()
        return jsonify({'success': True, 'stats': stats})

    @app.route('/api/admin/trial-abuse/flagged', methods=['GET'])
    def api_flagged_users():
        """Get list of flagged users (admin only)"""
        # TODO: Add admin auth check
        limit = request.args.get('limit', 50, type=int)
        users = get_flagged_users(limit)
        return jsonify({'success': True, 'users': users})

    @app.route('/api/admin/trial-abuse/unblock', methods=['POST'])
    def api_unblock_user():
        """Manually unblock a user (admin only)"""
        # TODO: Add admin auth check
        data = request.get_json() or {}
        fp_type = data.get('fingerprint_type')
        fp_value = data.get('fingerprint_value')

        if not fp_type or not fp_value:
            return jsonify({'success': False, 'error': 'Missing fingerprint info'}), 400

        success = unblock_fingerprint(fp_type, fp_value)
        return jsonify({'success': success})

    logger.info("✅ Trial abuse protection routes registered")


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_trial_abuse_protection(app=None):
    """Initialize trial abuse protection system"""
    logger.info("🛡️ Initializing trial abuse protection...")

    try:
        init_trial_abuse_tables()

        if app:
            register_trial_abuse_routes(app)

        logger.info("✅ Trial abuse protection initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize trial abuse protection: {e}")
        return False
