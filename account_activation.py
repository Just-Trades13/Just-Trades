"""
Account Activation Module — Whop Purchase -> Website Access

Handles auto-creating user accounts when Whop webhook fires,
and letting users set their own username + password via /activate.
"""

import logging
import secrets
import string
from flask import Blueprint, request, flash, redirect, url_for, render_template

logger = logging.getLogger(__name__)

activation_bp = Blueprint('activation', __name__)


def auto_create_user_from_whop(email, whop_user_id):
    """
    Auto-create a user account when someone buys on Whop.

    Creates account with:
    - username: whop_<random8chars> (temporary, user changes via /activate)
    - email: from Whop webhook
    - password: random 32-char (user sets their own via /activate)
    - is_approved: True (they paid)

    Returns user_id or None on failure.
    """
    try:
        from user_auth import get_user_by_email, create_user, approve_user

        # Check if user already exists (idempotent)
        existing = get_user_by_email(email)
        if existing:
            # Auto-approve if they paid
            if not existing.is_approved:
                approve_user(existing.id)
                logger.info(f"Auto-approved existing user {email} (Whop purchase)")
            return existing.id

        # Generate temporary username and random password
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        temp_username = f"whop_{random_suffix}"
        temp_password = secrets.token_urlsafe(32)

        user = create_user(
            username=temp_username,
            email=email,
            password=temp_password,
            display_name=f"Whop User ({whop_user_id[:8]})" if whop_user_id else "Whop User"
        )

        if user:
            # Auto-approve — they paid via Whop
            approve_user(user.id)
            logger.info(f"Auto-created user {email} as {temp_username} (id={user.id})")
            return user.id
        else:
            logger.error(f"create_user() returned None for {email}")
            return None

    except Exception as e:
        logger.error(f"Failed to auto-create user for {email}: {e}")
        return None


def activate_user_account(email, new_username, new_password):
    """
    Let a Whop user set their own username and password.

    Finds the auto-created account by email (username starts with whop_),
    updates username and password.

    Returns (success: bool, message: str)
    """
    try:
        from user_auth import get_user_by_email, get_user_by_username, get_auth_db_connection
        from werkzeug.security import generate_password_hash

        # Find the auto-created account
        user = get_user_by_email(email)
        if not user:
            return False, "No account found for this email. Please purchase a subscription on Whop first."

        # Check if already activated (username no longer starts with whop_)
        if not user.username.startswith('whop_'):
            return False, "This account has already been activated. Please sign in."

        # Validate new username
        new_username = new_username.strip().lower()
        if len(new_username) < 3:
            return False, "Username must be at least 3 characters."
        if not new_username.replace('_', '').replace('-', '').isalnum():
            return False, "Username can only contain letters, numbers, underscores, and hyphens."

        # Check username not taken
        existing = get_user_by_username(new_username)
        if existing and existing.id != user.id:
            return False, "That username is already taken. Please choose another."

        # Validate password
        if len(new_password) < 6:
            return False, "Password must be at least 6 characters."

        # Update username and password
        password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')

        conn, db_type = get_auth_db_connection()
        cursor = conn.cursor()

        try:
            placeholder = '%s' if db_type == 'postgresql' else '?'
            cursor.execute(
                f'UPDATE users SET username = {placeholder}, password_hash = {placeholder}, '
                f'display_name = {placeholder} WHERE id = {placeholder}',
                (new_username, password_hash, new_username, user.id)
            )
            conn.commit()
            logger.info(f"Account activated: {email} -> username={new_username}")
            return True, "Account activated! You can now sign in."
        except Exception as e:
            logger.error(f"Failed to update account for {email}: {e}")
            conn.rollback()
            return False, "Failed to update account. Please try again."
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.error(f"Activation error for {email}: {e}")
        return False, "An error occurred. Please try again."


@activation_bp.route('/activate', methods=['GET', 'POST'])
def activate():
    """Activation page where Whop users set their credentials."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Basic validation
        if not email or not username or not password:
            flash('All fields are required.', 'error')
            return render_template('activate.html', email=email, username=username)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('activate.html', email=email, username=username)

        success, message = activate_user_account(email, username, password)

        if success:
            flash(message, 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
            return render_template('activate.html', email=email, username=username)

    # GET request — show the form
    return render_template('activate.html', email='', username='')
