"""
Whop Integration Module
=======================
Handles integration with Whop.com for subscription management.

Features:
- Verify Whop memberships via API
- Process webhooks for subscription events
- Link Whop purchases to platform user accounts

Setup:
1. Get your API key from Whop Dashboard > Settings > Developer > API Keys
2. Set WHOP_API_KEY environment variable
3. Set WHOP_WEBHOOK_SECRET for webhook verification
4. Configure webhook URL in Whop: https://yourdomain.com/webhooks/whop

Whop API Docs: https://dev.whop.com/
"""

import os
import hmac
import hashlib
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger('whop')

# ============================================================================
# CONFIGURATION
# ============================================================================
WHOP_API_KEY = os.environ.get('WHOP_API_KEY', '')
WHOP_WEBHOOK_SECRET = os.environ.get('WHOP_WEBHOOK_SECRET', '')
WHOP_API_BASE_URL = 'https://api.whop.com/api/v2'

# Map Whop plan/product IDs to our plan slugs
# These are from the justtradesgroup Whop store
# TODO: Replace these with real IDs from Whop Dashboard > Products
WHOP_PRODUCT_MAP = {
    # Format: 'whop_plan_or_product_id': 'our_plan_slug'
    'prod_PLACEHOLDER_COPY': 'pro_copy_trader',    # Pro Copy Trader $100/mo — TODO: replace with real Whop product ID
    'prod_l3u1RLWEjMIS7': 'platform_basic',        # Basic+ $200/mo
    'prod_3RCOfsuDNX4cs': 'platform_premium',       # Premium+ $500/mo
    'prod_oKaNSNRKgxXS3': 'platform_elite',         # Elite+ $1000/mo
}

# Reverse map for looking up Whop product from our plan
PLAN_TO_WHOP_MAP = {v: k for k, v in WHOP_PRODUCT_MAP.items()}


# ============================================================================
# API HELPERS
# ============================================================================
def get_whop_headers() -> Dict[str, str]:
    """Get headers for Whop API requests."""
    return {
        'Authorization': f'Bearer {WHOP_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def whop_api_request(method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
    """
    Make a request to the Whop API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint (e.g., '/memberships')
        data: Request body data (optional)
    
    Returns:
        Response JSON or None if error
    """
    if not WHOP_API_KEY:
        logger.error("❌ WHOP_API_KEY not configured")
        return None
    
    url = f"{WHOP_API_BASE_URL}{endpoint}"
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=get_whop_headers(),
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            logger.error("❌ Whop API: Unauthorized - check your API key")
        elif response.status_code == 404:
            logger.warning(f"⚠️ Whop API: Not found - {endpoint}")
        else:
            logger.error(f"❌ Whop API error {response.status_code}: {response.text}")
        
        return None
    except requests.RequestException as e:
        logger.error(f"❌ Whop API request failed: {e}")
        return None


# ============================================================================
# MEMBERSHIP VERIFICATION
# ============================================================================
def verify_membership(membership_id: str) -> Optional[Dict]:
    """
    Verify a Whop membership by ID.
    
    Returns membership details if valid, None if invalid/expired.
    """
    result = whop_api_request('GET', f'/memberships/{membership_id}')
    
    if result and result.get('valid'):
        return {
            'membership_id': result.get('id'),
            'user_id': result.get('user', {}).get('id'),
            'user_email': result.get('user', {}).get('email'),
            'product_id': result.get('product', {}).get('id'),
            'plan_slug': WHOP_PRODUCT_MAP.get(result.get('product', {}).get('id')),
            'status': result.get('status'),
            'valid': result.get('valid'),
            'created_at': result.get('created_at'),
            'renewal_period_end': result.get('renewal_period_end'),
        }
    
    return None


def get_membership_by_email(email: str) -> List[Dict]:
    """
    Get all memberships for a user by email.
    
    Returns list of active memberships.
    """
    # Search for user by email first
    result = whop_api_request('GET', f'/memberships?email={email}')
    
    if not result:
        return []
    
    memberships = []
    for membership in result.get('data', []):
        if membership.get('valid'):
            memberships.append({
                'membership_id': membership.get('id'),
                'product_id': membership.get('product', {}).get('id'),
                'product_name': membership.get('product', {}).get('name'),
                'plan_slug': WHOP_PRODUCT_MAP.get(membership.get('product', {}).get('id')),
                'status': membership.get('status'),
                'valid': membership.get('valid'),
            })
    
    return memberships


def get_user_by_whop_id(whop_user_id: str) -> Optional[Dict]:
    """Get Whop user details by their Whop user ID."""
    result = whop_api_request('GET', f'/users/{whop_user_id}')
    
    if result:
        return {
            'whop_user_id': result.get('id'),
            'email': result.get('email'),
            'username': result.get('username'),
            'name': result.get('name'),
        }
    
    return None


def check_valid_membership(email: str, plan_type: str = 'platform') -> Optional[Dict]:
    """
    Check if an email has a valid membership for the specified plan type.
    
    Args:
        email: User's email address
        plan_type: 'platform' or 'discord'
    
    Returns:
        Best matching membership or None
    """
    memberships = get_membership_by_email(email)
    
    if not memberships:
        return None
    
    # Filter by plan type and find highest tier
    valid_memberships = []
    for m in memberships:
        plan_slug = m.get('plan_slug')
        if plan_slug and plan_slug.startswith('platform_'):
            valid_memberships.append(m)

    if not valid_memberships:
        return None

    # Return highest tier (by price order: elite > premium > basic)
    tier_order = {'platform_elite': 3, 'platform_premium': 2, 'platform_basic': 1}
    
    valid_memberships.sort(key=lambda x: tier_order.get(x.get('plan_slug'), 0), reverse=True)
    return valid_memberships[0]


# ============================================================================
# WEBHOOK HANDLING
# ============================================================================
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Whop webhook signature.
    
    Args:
        payload: Raw request body
        signature: X-Whop-Signature header value
    
    Returns:
        True if signature is valid
    """
    if not WHOP_WEBHOOK_SECRET:
        logger.warning("⚠️ WHOP_WEBHOOK_SECRET not configured - skipping verification")
        return True  # Skip verification in development
    
    expected_signature = hmac.new(
        WHOP_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def process_webhook_event(event_type: str, data: Dict) -> Dict:
    """
    Process a Whop webhook event.
    
    Event types:
    - membership.went_valid: New subscription activated
    - membership.went_invalid: Subscription cancelled/expired
    - membership.renewed: Subscription renewed
    - payment.succeeded: Payment completed
    - payment.failed: Payment failed
    
    Returns:
        Result dict with 'success' and 'message' keys
    """
    from subscription_models import (
        create_subscription, update_subscription_status, 
        cancel_subscription, get_subscription_by_whop_membership
    )
    
    # Normalize v1 event names to v2/v5 names
    V1_EVENT_MAP = {
        'membership.activated': 'membership.went_valid',
        'membership.deactivated': 'membership.went_invalid',
        'membership.cancelled': 'membership.went_invalid',
        'membership.expired': 'membership.went_invalid',
    }
    event_type = V1_EVENT_MAP.get(event_type, event_type)

    logger.info(f"📥 Processing Whop webhook: {event_type}")

    membership_id = data.get('id') or data.get('membership_id')
    product_id = data.get('product', {}).get('id') if isinstance(data.get('product'), dict) else data.get('product_id')
    user_email = data.get('user', {}).get('email') if isinstance(data.get('user'), dict) else data.get('email')
    whop_user_id = data.get('user', {}).get('id') if isinstance(data.get('user'), dict) else data.get('user_id')
    
    plan_slug = WHOP_PRODUCT_MAP.get(product_id)
    
    if not plan_slug:
        logger.warning(f"⚠️ Unknown Whop product ID: {product_id}")
        return {'success': False, 'message': f'Unknown product: {product_id}'}
    
    if event_type == 'membership.went_valid':
        # New subscription or reactivation
        is_trial = data.get('status') == 'trialing'

        # Track trial usage for abuse prevention
        if is_trial:
            try:
                from trial_abuse_protection import record_trial_start, is_disposable_email

                # Check for disposable email
                if is_disposable_email(user_email):
                    logger.warning(f"🚨 Disposable email detected for trial: {user_email}")
                    # Still create subscription but flag it

                # Extract payment info if available (Whop may include card fingerprint)
                payment_info = data.get('payment_method', {})
                card_fingerprint = None
                if payment_info:
                    # Create card fingerprint from last4 + brand
                    last4 = payment_info.get('last4', '')
                    brand = payment_info.get('brand', '')
                    if last4:
                        card_fingerprint = f"{brand}_{last4}"

                # Record trial fingerprints
                abuse_detected, abuse_msg = record_trial_start(
                    whop_membership_id=membership_id,
                    whop_user_id=whop_user_id,
                    email=user_email,
                    card_fingerprint=card_fingerprint,
                    metadata={
                        'plan': plan_slug,
                        'product_id': product_id,
                        'webhook_data': {k: v for k, v in data.items() if k not in ['user', 'product']}
                    }
                )

                if abuse_detected:
                    logger.warning(f"🚨 Trial abuse detected at signup (fingerprint): {abuse_msg}")
                    is_trial = False  # Convert to paid — no free days
                    logger.info(f"🚫 Trial converted to paid for {user_email} (fingerprint abuse on {plan_slug})")

            except ImportError:
                logger.debug("Trial abuse protection not available")
            except Exception as e:
                logger.error(f"Trial abuse tracking error: {e}")

        # Cross-tier trial abuse check: has this user ever had ANY trial?
        if is_trial:
            try:
                from subscription_models import has_user_had_any_trial
                if has_user_had_any_trial(email=user_email, whop_customer_id=whop_user_id):
                    is_trial = False  # Convert to paid — no free days
                    logger.warning(f"🚫 Cross-tier trial blocked for {user_email} on {plan_slug} — prior trial exists, converting to paid")
            except Exception as e:
                logger.error(f"Cross-tier trial check error (failing open): {e}")

        # Try to find existing user by email
        from user_auth import get_user_by_email
        user = get_user_by_email(user_email) if user_email else None

        if user:
            # Create/update subscription for existing user
            create_subscription(
                user_id=user.id,
                plan_slug=plan_slug,
                whop_membership_id=membership_id,
                whop_customer_id=whop_user_id,
                trial_days=7 if is_trial else 0
            )
            # Auto-approve user if they paid via Whop
            if not user.is_approved:
                try:
                    from user_auth import approve_user
                    approve_user(user.id)
                    logger.info(f"Auto-approved user {user.email} (paid via Whop)")
                except Exception as e:
                    logger.warning(f"Could not auto-approve {user.email}: {e}")
            # Send activation email (for new or existing users)
            try:
                from account_activation import generate_activation_token, send_activation_email
                token = generate_activation_token(user.id, user.email)
                if token:
                    send_activation_email(user.email, token)
            except Exception as e:
                logger.warning(f"Could not send activation email to {user.email}: {e}")
            logger.info(f"✅ Subscription created for user {user.email}: {plan_slug}")
            return {'success': True, 'message': f'Subscription activated for {user.email}'}
        else:
            # User doesn't exist — auto-create account and link subscription
            try:
                from account_activation import auto_create_user_from_whop
                new_user_id = auto_create_user_from_whop(user_email, whop_user_id or 'unknown')
                if new_user_id:
                    create_subscription(
                        user_id=new_user_id,
                        plan_slug=plan_slug,
                        whop_membership_id=membership_id,
                        whop_customer_id=whop_user_id,
                        trial_days=7 if is_trial else 0
                    )
                    logger.info(f"✅ Auto-created user + subscription for {user_email}: {plan_slug}")
                    return {'success': True, 'message': f'Account created for {user_email}'}
                else:
                    # Fallback to legacy pending behavior
                    create_subscription(
                        user_id=0,
                        plan_slug=plan_slug,
                        whop_membership_id=membership_id,
                        whop_customer_id=whop_user_id,
                        trial_days=7 if is_trial else 0
                    )
                    logger.warning(f"Auto-create failed, pending subscription for {user_email}")
                    return {'success': True, 'message': f'Pending subscription for {user_email}'}
            except Exception:
                # Any failure -> fall back to exact current behavior
                create_subscription(
                    user_id=0,
                    plan_slug=plan_slug,
                    whop_membership_id=membership_id,
                    whop_customer_id=whop_user_id,
                    trial_days=7 if is_trial else 0
                )
                logger.info(f"✅ Pending subscription created for {user_email}: {plan_slug}")
                return {'success': True, 'message': f'Pending subscription for {user_email}'}
    
    elif event_type == 'membership.went_invalid':
        # Subscription cancelled or expired
        cancel_subscription(whop_membership_id=membership_id)
        logger.info(f"✅ Subscription cancelled: {membership_id}")
        return {'success': True, 'message': 'Subscription cancelled'}
    
    elif event_type == 'membership.renewed':
        # Subscription renewed
        update_subscription_status(whop_membership_id=membership_id, status='active')
        logger.info(f"✅ Subscription renewed: {membership_id}")
        return {'success': True, 'message': 'Subscription renewed'}
    
    elif event_type == 'payment.succeeded':
        # Payment successful - ensure subscription is active
        update_subscription_status(whop_membership_id=membership_id, status='active')
        return {'success': True, 'message': 'Payment recorded'}
    
    elif event_type == 'payment.failed':
        # Payment failed - mark as past due
        update_subscription_status(whop_membership_id=membership_id, status='past_due')
        logger.warning(f"⚠️ Payment failed for membership: {membership_id}")
        return {'success': True, 'message': 'Payment failure recorded'}
    
    else:
        logger.info(f"ℹ️ Unhandled webhook event: {event_type}")
        return {'success': True, 'message': f'Event {event_type} acknowledged'}


# ============================================================================
# FLASK ROUTE HANDLERS
# ============================================================================
def create_webhook_handler(app):
    """
    Create Flask route for Whop webhooks.
    
    Usage:
        from whop_integration import create_webhook_handler
        create_webhook_handler(app)
    """
    
    @app.route('/webhooks/whop', methods=['POST'])
    def whop_webhook():
        """Handle incoming Whop webhooks."""
        # Get signature from header
        signature = request.headers.get('X-Whop-Signature', '')
        
        # Verify signature
        if not verify_webhook_signature(request.data, signature):
            logger.warning("⚠️ Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse event
        try:
            payload = request.get_json()
            event_type = payload.get('event') or payload.get('action')
            data = payload.get('data', payload)
            
            result = process_webhook_event(event_type, data)
            
            return jsonify(result), 200 if result.get('success') else 400
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")
            return jsonify({'error': str(e)}), 500
    
    logger.info("✅ Whop webhook handler registered at /webhooks/whop")


# ============================================================================
# USER LINKING
# ============================================================================
def link_user_to_whop(user_id: int, user_email: str) -> Dict:
    """
    Attempt to link a platform user to their Whop membership.
    
    Called when:
    1. User registers with email that has existing Whop membership
    2. User manually enters membership ID
    
    Returns:
        Result dict with subscription info if found
    """
    from subscription_models import (
        create_subscription, get_subscription_by_whop_membership,
        get_user_subscription
    )
    
    # Check if user already has a subscription
    existing = get_user_subscription(user_id)
    if existing:
        return {
            'success': True,
            'already_subscribed': True,
            'plan': existing.get('plan_name'),
            'message': f"Already subscribed to {existing.get('plan_name')}"
        }
    
    # Look for Whop membership by email
    memberships = get_membership_by_email(user_email)
    
    if not memberships:
        return {
            'success': False,
            'message': 'No Whop membership found for this email'
        }
    
    # Link all valid memberships
    linked = []
    for membership in memberships:
        plan_slug = membership.get('plan_slug')
        if plan_slug:
            create_subscription(
                user_id=user_id,
                plan_slug=plan_slug,
                whop_membership_id=membership.get('membership_id'),
            )
            linked.append(membership.get('product_name') or plan_slug)
    
    if linked:
        logger.info(f"✅ Linked Whop memberships for user {user_id}: {linked}")
        return {
            'success': True,
            'linked': linked,
            'message': f"Successfully linked: {', '.join(linked)}"
        }
    
    return {
        'success': False,
        'message': 'Could not link any memberships'
    }


def verify_membership_code(membership_id: str, user_id: int) -> Dict:
    """
    Verify a membership ID/code entered by user.
    
    Returns:
        Result dict with subscription info if valid
    """
    from subscription_models import create_subscription
    
    membership = verify_membership(membership_id)
    
    if not membership:
        return {
            'success': False,
            'message': 'Invalid or expired membership ID'
        }
    
    if not membership.get('valid'):
        return {
            'success': False,
            'message': 'This membership is no longer active'
        }
    
    plan_slug = membership.get('plan_slug')
    if not plan_slug:
        return {
            'success': False,
            'message': 'Unrecognized product - please contact support'
        }
    
    # Create subscription
    create_subscription(
        user_id=user_id,
        plan_slug=plan_slug,
        whop_membership_id=membership_id,
        whop_customer_id=membership.get('user_id'),
    )
    
    from subscription_models import get_plan_by_slug
    plan = get_plan_by_slug(plan_slug)
    
    return {
        'success': True,
        'plan_name': plan.get('name') if plan else plan_slug,
        'plan_slug': plan_slug,
        'message': f"Successfully activated {plan.get('name') if plan else plan_slug}!"
    }


# ============================================================================
# ACCESS CONTROL DECORATORS
# ============================================================================
def subscription_required(plan_type: str = 'platform'):
    """
    Decorator to require an active subscription for a route.
    
    Usage:
        @app.route('/dashboard')
        @login_required
        @subscription_required('platform')
        def dashboard():
            return render_template('dashboard.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session, redirect, url_for, flash
            from subscription_models import get_user_subscription
            
            user_id = session.get('user_id')
            if not user_id:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            
            subscription = get_user_subscription(user_id, plan_type=plan_type)
            
            if not subscription:
                flash('This feature requires an active subscription.', 'warning')
                return redirect(url_for('pricing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def feature_required(feature_name: str):
    """
    Decorator to require a specific feature for a route.
    
    Usage:
        @app.route('/quant-screener')
        @login_required
        @feature_required('quant_screener')
        def quant_screener():
            return render_template('quant_screener.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session, redirect, url_for, flash
            from subscription_models import check_feature_access
            
            user_id = session.get('user_id')
            if not user_id:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))

            # Admins always have access to all features
            from user_auth import get_user_by_id
            current_user = get_user_by_id(user_id)
            if current_user and current_user.is_admin:
                return f(*args, **kwargs)

            if not check_feature_access(user_id, feature_name):
                flash(f'This feature requires a higher subscription tier.', 'warning')
                return redirect(url_for('pricing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# CONFIGURATION HELPERS
# ============================================================================
def update_whop_product_map(product_id: str, plan_slug: str):
    """
    Update the Whop product to plan mapping.
    
    Call this when you get your actual Whop product IDs.
    """
    global WHOP_PRODUCT_MAP, PLAN_TO_WHOP_MAP
    WHOP_PRODUCT_MAP[product_id] = plan_slug
    PLAN_TO_WHOP_MAP = {v: k for k, v in WHOP_PRODUCT_MAP.items()}
    logger.info(f"✅ Mapped Whop product {product_id} -> {plan_slug}")


def get_whop_checkout_url(plan_slug: str) -> Optional[str]:
    """
    Get the Whop checkout URL for a plan.
    
    Returns the direct link to purchase on Whop.
    """
    # You'll need to set these URLs from your Whop dashboard
    CHECKOUT_URLS = {
        'pro_copy_trader': 'https://whop.com/justtradesgroup/procopytrader/',  # TODO: update with real URL
        'platform_basic': 'https://whop.com/justtradesgroup/basicplus/',
        'platform_premium': 'https://whop.com/justtradesgroup/premiumtier/',
        'platform_elite': 'https://whop.com/justtradesgroup/eliteplus/',
    }
    return CHECKOUT_URLS.get(plan_slug)


def is_whop_configured() -> bool:
    """Check if Whop integration is properly configured."""
    return bool(WHOP_API_KEY)


def get_configuration_status() -> Dict:
    """Get current Whop configuration status."""
    return {
        'api_key_configured': bool(WHOP_API_KEY),
        'webhook_secret_configured': bool(WHOP_WEBHOOK_SECRET),
        'product_map': WHOP_PRODUCT_MAP,
    }


# ============================================================================
# TESTING HELPERS
# ============================================================================
def simulate_webhook(event_type: str, membership_id: str, product_id: str, 
                     email: str = 'test@example.com') -> Dict:
    """
    Simulate a Whop webhook for local testing.
    
    Usage:
        result = simulate_webhook(
            'membership.went_valid',
            'mem_test123',
            'prod_ZZZZZZZZZ',  # platform_basic
            'user@example.com'
        )
    """
    logger.warning("⚠️ SIMULATING WEBHOOK - for testing only!")
    
    test_data = {
        'id': membership_id,
        'product': {'id': product_id},
        'user': {'id': 'user_test', 'email': email},
        'status': 'active',
        'valid': True,
    }
    
    return process_webhook_event(event_type, test_data)


# ============================================================================
# INITIALIZATION
# ============================================================================
def init_whop_integration():
    """Initialize Whop integration. Call on app startup."""
    logger.info("🔗 Initializing Whop integration...")
    
    status = get_configuration_status()
    
    if not status['api_key_configured']:
        logger.warning("⚠️ WHOP_API_KEY not set - Whop API calls will fail")
        logger.warning("   Set it with: export WHOP_API_KEY='your_api_key'")
    
    if not status['webhook_secret_configured']:
        logger.warning("⚠️ WHOP_WEBHOOK_SECRET not set - webhook signatures won't be verified")
    
    logger.info("✅ Whop integration initialized")
    return True


if __name__ == '__main__':
    # Test the module
    logging.basicConfig(level=logging.INFO)
    
    print("Whop Integration Status:")
    print("=" * 40)
    
    status = get_configuration_status()
    print(f"API Key configured: {status['api_key_configured']}")
    print(f"Webhook secret configured: {status['webhook_secret_configured']}")
    print(f"\nProduct mapping:")
    for whop_id, plan_slug in status['product_map'].items():
        print(f"  {whop_id} -> {plan_slug}")
    
    print("\n" + "=" * 40)
    print("To configure, set environment variables:")
    print("  export WHOP_API_KEY='your_api_key'")
    print("  export WHOP_WEBHOOK_SECRET='your_webhook_secret'")
