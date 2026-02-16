"""
Account Activation Module — Whop Purchase -> Email -> Website Access

Flow:
1. Whop webhook fires -> auto_create_user_from_whop(email, whop_user_id)
2. Account created + activation token generated + email sent via Brevo
3. User clicks link in email -> /activate?token=xxxx
4. User sets username + password -> account activated
"""

import os
import logging
import secrets
import string
from datetime import datetime, timedelta
from flask import Blueprint, request, flash, redirect, url_for, render_template

logger = logging.getLogger(__name__)

activation_bp = Blueprint('activation', __name__)

PLATFORM_URL = os.environ.get('PLATFORM_URL', 'https://www.justtrades.app')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', 'noreply@justtrades.com')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'Just Trades')


# ============================================================================
# DATABASE — activation_tokens table
# ============================================================================
def init_activation_tokens_table():
    """Create activation_tokens table if it doesn't exist. Safe to call repeatedly."""
    try:
        from user_auth import get_auth_db_connection
        conn, db_type = get_auth_db_connection()
        cursor = conn.cursor()

        try:
            if db_type == 'postgresql':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activation_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token VARCHAR(100) UNIQUE NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_activation_tokens_token
                    ON activation_tokens(token)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_activation_tokens_user_id
                    ON activation_tokens(user_id)
                ''')
            else:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activation_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        token TEXT UNIQUE NOT NULL,
                        email TEXT NOT NULL,
                        used INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_activation_tokens_token
                    ON activation_tokens(token)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_activation_tokens_user_id
                    ON activation_tokens(user_id)
                ''')

            conn.commit()
            logger.info("activation_tokens table initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to create activation_tokens table: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"DB connection error in init_activation_tokens_table: {e}")
        return False


_tokens_table_initialized = False


def generate_activation_token(user_id, email):
    """
    Generate a secure activation token and store it in DB.
    Token expires in 72 hours.

    Returns token string or None on failure.
    """
    global _tokens_table_initialized
    if not _tokens_table_initialized:
        init_activation_tokens_table()
        _tokens_table_initialized = True

    try:
        from user_auth import get_auth_db_connection

        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=72)

        conn, db_type = get_auth_db_connection()
        cursor = conn.cursor()

        try:
            placeholder = '%s' if db_type == 'postgresql' else '?'
            cursor.execute(
                f'INSERT INTO activation_tokens (user_id, token, email, expires_at) '
                f'VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})',
                (user_id, token, email.lower(), expires_at)
            )
            conn.commit()
            logger.info(f"Activation token generated for user_id={user_id}, email={email}")
            return token
        except Exception as e:
            logger.error(f"Failed to store activation token for {email}: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Token generation error for {email}: {e}")
        return None


def validate_activation_token(token):
    """
    Validate an activation token.

    Returns (user_id, email) if valid, (None, None) if invalid/expired/used.
    """
    try:
        from user_auth import get_auth_db_connection
        conn, db_type = get_auth_db_connection()
        cursor = conn.cursor()

        try:
            placeholder = '%s' if db_type == 'postgresql' else '?'

            if db_type == 'postgresql':
                cursor.execute(
                    f'SELECT user_id, email, used, expires_at FROM activation_tokens '
                    f'WHERE token = {placeholder}',
                    (token,)
                )
            else:
                cursor.execute(
                    f'SELECT user_id, email, used, expires_at FROM activation_tokens '
                    f'WHERE token = {placeholder}',
                    (token,)
                )

            row = cursor.fetchone()
            if not row:
                return None, None

            # Handle both dict-like and tuple rows
            if hasattr(row, 'keys'):
                user_id = row['user_id']
                email = row['email']
                used = row['used']
                expires_at = row['expires_at']
            else:
                user_id = row[0]
                email = row[1]
                used = row[2]
                expires_at = row[3]

            # Check if already used
            if used and used not in (0, False):
                return None, None

            # Check expiration
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00').replace('+00:00', ''))
            if datetime.utcnow() > expires_at:
                return None, None

            return user_id, email
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None, None


def mark_token_used(token):
    """Mark an activation token as used."""
    try:
        from user_auth import get_auth_db_connection
        conn, db_type = get_auth_db_connection()
        cursor = conn.cursor()

        try:
            placeholder = '%s' if db_type == 'postgresql' else '?'
            if db_type == 'postgresql':
                cursor.execute(
                    f'UPDATE activation_tokens SET used = TRUE WHERE token = {placeholder}',
                    (token,)
                )
            else:
                cursor.execute(
                    f'UPDATE activation_tokens SET used = 1 WHERE token = {placeholder}',
                    (token,)
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark token as used: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"mark_token_used error: {e}")
        return False


# ============================================================================
# EMAIL — Brevo (Sendinblue) transactional email
# ============================================================================
def send_activation_email(email, token):
    """
    Send activation email via Brevo API.

    Returns True if sent, False on any failure.
    Failures are logged but never raise — account creation must not break.
    """
    if not BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not configured — skipping activation email")
        return False

    try:
        import brevo_python
        from brevo_python.rest import ApiException

        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = BREVO_API_KEY
        api_instance = brevo_python.TransactionalEmailsApi(brevo_python.ApiClient(configuration))

        activation_url = f"{PLATFORM_URL}/activate?token={token}"

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0b1221;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#0b1221;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td align="center" style="padding-bottom:30px;">
              <span style="font-size:28px;font-weight:700;letter-spacing:0.15em;color:#f8fafc;">JUST.TRADES.</span>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td style="background-color:#111a2f;border-radius:16px;padding:40px 36px;border:1px solid rgba(148,163,184,0.12);">

              <h1 style="margin:0 0 16px;font-size:24px;font-weight:600;color:#f8fafc;text-align:center;">
                Welcome to Just Trades!
              </h1>

              <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#7f8db2;text-align:center;">
                Your subscription is confirmed. Click the button below to set your username and password and start trading.
              </p>

              <!-- CTA Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center" style="padding:8px 0 24px;">
                    <a href="{activation_url}"
                       style="display:inline-block;padding:16px 40px;background:linear-gradient(135deg,#19b8ff,#0c6bbd);
                              color:#ffffff;font-size:16px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;
                              text-decoration:none;border-radius:12px;">
                      ACTIVATE MY ACCOUNT
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 8px;font-size:13px;color:#7f8db2;text-align:center;">
                Or copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px;font-size:13px;color:#19b8ff;text-align:center;word-break:break-all;">
                {activation_url}
              </p>

              <hr style="border:none;border-top:1px solid rgba(148,163,184,0.12);margin:24px 0;">

              <p style="margin:0;font-size:12px;color:#7f8db2;text-align:center;">
                This link expires in 72 hours. If you didn't purchase a subscription, you can safely ignore this email.
              </p>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" style="padding-top:24px;">
              <p style="margin:0;font-size:12px;color:#7f8db2;">Just Trades - Automated Trading Platform</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        send_smtp_email = brevo_python.SendSmtpEmail(
            to=[brevo_python.SendSmtpEmailTo(email=email)],
            sender=brevo_python.SendSmtpEmailSender(
                name=BREVO_SENDER_NAME,
                email=BREVO_SENDER_EMAIL
            ),
            subject="Activate Your Just Trades Account",
            html_content=html_content
        )

        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Activation email sent to {email}")
        return True

    except ImportError:
        logger.warning("brevo-python not installed — skipping activation email")
        return False
    except Exception as e:
        logger.error(f"Failed to send activation email to {email}: {e}")
        return False


# ============================================================================
# USER OPERATIONS
# ============================================================================
def auto_create_user_from_whop(email, whop_user_id):
    """
    Auto-create a user account when someone buys on Whop.

    Creates account with:
    - username: whop_<random8chars> (temporary, user changes via /activate)
    - email: from Whop webhook
    - password: random 32-char (user sets their own via /activate)
    - is_approved: True (they paid)

    Also generates an activation token and sends an email.

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

            # Send activation email on every Whop purchase
            try:
                token = generate_activation_token(existing.id, email)
                if token:
                    send_activation_email(email, token)
            except Exception as e:
                logger.error(f"Failed to send activation email for existing user {email}: {e}")

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

            # Generate token and send activation email
            # Wrapped in try/except — email failure must NEVER break account creation
            try:
                token = generate_activation_token(user.id, email)
                if token:
                    send_activation_email(email, token)
            except Exception as e:
                logger.error(f"Failed to send activation email for new user {email}: {e}")

            return user.id
        else:
            logger.error(f"create_user() returned None for {email}")
            return None

    except Exception as e:
        logger.error(f"Failed to auto-create user for {email}: {e}")
        return None


def activate_user_account_by_id(user_id, new_username, new_password):
    """
    Set username and password for a user identified by user_id (from token lookup).

    Returns (success: bool, message: str)
    """
    try:
        from user_auth import get_user_by_id, get_user_by_username, get_auth_db_connection
        from werkzeug.security import generate_password_hash

        user = get_user_by_id(user_id)
        if not user:
            return False, "Account not found. Please contact support."

        # Check if already activated
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
            logger.info(f"Account activated: user_id={user_id} -> username={new_username}")
            return True, "Account activated! You can now sign in."
        except Exception as e:
            logger.error(f"Failed to update account for user_id={user_id}: {e}")
            conn.rollback()
            return False, "Failed to update account. Please try again."
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.error(f"Activation error for user_id={user_id}: {e}")
        return False, "An error occurred. Please try again."


# ============================================================================
# ROUTES
# ============================================================================
@activation_bp.route('/activate', methods=['GET', 'POST'])
def activate():
    """Activation page — token-based flow."""
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not token:
            flash('Invalid activation link. Please use the link from your email.', 'error')
            return render_template('activate.html', has_token=False)

        # Validate token
        user_id, email = validate_activation_token(token)
        if not user_id:
            flash('This activation link is invalid or has expired. Please request a new one below.', 'error')
            return render_template('activate.html', has_token=False)

        # Basic validation
        if not username or not password:
            flash('All fields are required.', 'error')
            return render_template('activate.html', has_token=True, token=token, email=email, username=username)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('activate.html', has_token=True, token=token, email=email, username=username)

        success, message = activate_user_account_by_id(user_id, username, password)

        if success:
            mark_token_used(token)
            flash(message, 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
            return render_template('activate.html', has_token=True, token=token, email=email, username=username)

    # GET request
    token = request.args.get('token', '').strip()

    if token:
        # Validate the token
        user_id, email = validate_activation_token(token)
        if user_id:
            return render_template('activate.html', has_token=True, token=token, email=email, username='')
        else:
            flash('This activation link is invalid or has expired. Please request a new one below.', 'error')
            return render_template('activate.html', has_token=False)

    # No token — show "check your email" page
    return render_template('activate.html', has_token=False)


@activation_bp.route('/activate/resend', methods=['POST'])
def activate_resend():
    """Resend activation email."""
    email = request.form.get('email', '').strip().lower()

    if not email:
        flash('Please enter your email address.', 'error')
        return render_template('activate.html', has_token=False)

    try:
        from user_auth import get_user_by_email

        user = get_user_by_email(email)
        if not user:
            # Don't reveal whether email exists — generic message
            flash('If an account exists for that email, a new activation link has been sent.', 'info')
            return render_template('activate.html', has_token=False)

        # Only resend if account hasn't been activated yet
        if not user.username.startswith('whop_'):
            flash('This account has already been activated. Please sign in.', 'info')
            return render_template('activate.html', has_token=False)

        # Generate new token and send email
        token = generate_activation_token(user.id, email)
        if token:
            sent = send_activation_email(email, token)
            if sent:
                flash('A new activation link has been sent to your email.', 'success')
            else:
                flash('Unable to send email right now. Please try again later or contact support.', 'error')
        else:
            flash('Unable to generate activation link. Please try again later.', 'error')

    except Exception as e:
        logger.error(f"Resend activation error for {email}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return render_template('activate.html', has_token=False)
