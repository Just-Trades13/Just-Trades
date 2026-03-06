"""
Marketing & Static Routes for Just Trades Platform.
Flask Blueprint extracted from ultra_simple_server.py.

Usage:
    from marketing_routes import marketing_bp, init_marketing_routes

    init_marketing_routes(
        user_auth_available=USER_AUTH_AVAILABLE,
        is_logged_in_fn=is_logged_in if USER_AUTH_AVAILABLE else (lambda: False),
    )
    app.register_blueprint(marketing_bp)
"""
import os
import logging
from flask import (
    Blueprint, request, jsonify, redirect, url_for,
    render_template, send_from_directory, Response,
)

logger = logging.getLogger(__name__)

marketing_bp = Blueprint('marketing', __name__)

# Module-level state, initialized via init_marketing_routes()
_user_auth_available = False
_is_logged_in = None


def init_marketing_routes(user_auth_available, is_logged_in_fn):
    """Initialize marketing routes with required dependencies."""
    global _user_auth_available, _is_logged_in
    _user_auth_available = user_auth_available
    _is_logged_in = is_logged_in_fn


# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@marketing_bp.route('/static/js/<path:filename>')
def handle_static_js(filename):
    """Handle static JS files and source maps"""
    # If it's a source map request, return 204 (they're optional)
    if filename.endswith('.map'):
        return Response(status=204)  # No Content - source maps are optional

    # Otherwise try to serve the actual file
    static_dir = os.path.join(os.path.dirname(__file__), 'static', 'js')
    file_path = os.path.join(static_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(static_dir, filename)

    # File doesn't exist
    return Response(status=404)


@marketing_bp.route('/static/<path:filename>')
def handle_static_file(filename):
    """Handle static files and source maps"""
    # If it's a source map request, return 204 (they're optional)
    if filename.endswith('.map'):
        return Response(status=204)  # No Content - source maps are optional

    # Otherwise try to serve the actual file
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    file_path = os.path.join(static_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(static_dir, filename)

    # File doesn't exist
    return Response(status=404)


# ============================================================================
# LANDING / INDEX
# ============================================================================

@marketing_bp.route('/')
def index():
    """Root route - redirect to dashboard if logged in, otherwise show landing page."""
    if _user_auth_available and _is_logged_in():
        return redirect(url_for('dashboard'))
    return redirect(url_for('marketing.pricing'))


# ============================================================================
# PRICING & LEGAL PAGES
# ============================================================================

@marketing_bp.route('/pricing')
def pricing():
    """Public pricing page. Accepts ?ref=CODE for affiliate link tracking."""
    ref_code = request.args.get('ref', '').strip()
    affiliate_links = {}
    if ref_code:
        try:
            from ultra_simple_server import get_db_connection, is_using_postgres
            conn = get_db_connection()
            cursor = conn.cursor()
            is_postgres = is_using_postgres()
            placeholder = '%s' if is_postgres else '?'
            cursor.execute(
                f"SELECT whop_link_platform_basic, whop_link_platform_premium, whop_link_platform_elite, "
                f"whop_link_discord_basic, whop_link_discord_premium "
                f"FROM affiliate_applications WHERE affiliate_code = {placeholder} AND status = 'approved'",
                (ref_code,)
            )
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                affiliate_links = {k: v for k, v in row_dict.items() if v}
            cursor.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Pricing affiliate lookup error: {e}")
    return render_template('pricing.html', affiliate_links=affiliate_links, ref_code=ref_code)


@marketing_bp.route('/terms')
def terms():
    """Terms of Service page."""
    return render_template('terms.html')


@marketing_bp.route('/privacy')
def privacy():
    """Privacy Policy page."""
    return render_template('privacy.html')


@marketing_bp.route('/risk-disclosure')
def risk_disclosure():
    """Risk Disclosure page."""
    return render_template('risk_disclosure.html')


# ============================================================================
# BLOG ROUTES
# ============================================================================

BLOG_SLUG_MAP = {
    'tradingview-to-tradovate-automation': 'blog_post_tradingview.html',
    'best-automation-apex-trader-funding-accounts': 'blog_post_apex.html',
    'multi-account-futures-trading-complete-guide': 'blog_post_multi_account.html',
}


@marketing_bp.route('/blog')
def blog_index():
    """Blog landing page."""
    return render_template('blog_index.html')


@marketing_bp.route('/blog/<slug>')
def blog_post(slug):
    """Individual blog post by SEO slug."""
    template = BLOG_SLUG_MAP.get(slug)
    if template:
        return render_template(template)
    return redirect(url_for('marketing.blog_index'))


# ============================================================================
# SEO FILES
# ============================================================================

@marketing_bp.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml for SEO."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'static'),
        'sitemap.xml',
        mimetype='application/xml',
    )


@marketing_bp.route('/robots.txt')
def robots():
    """Serve robots.txt for crawlers."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'static'),
        'robots.txt',
        mimetype='text/plain',
    )


# ============================================================================
# PUBLIC API
# ============================================================================

@marketing_bp.route('/api/public/stats')
def public_stats():
    """
    Public API endpoint for platform statistics.
    Returns real counts from the database.
    """
    try:
        from ultra_simple_server import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count total trades executed
        try:
            cursor.execute('SELECT COUNT(*) FROM recorded_trades')
            total_trades = cursor.fetchone()[0] or 0
        except:
            total_trades = 0

        # Count total users
        total_users = 0
        if _user_auth_available:
            try:
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0] or 0
            except:
                total_users = 0

        cursor.close()
        conn.close()

        return jsonify({
            'total_trades': total_trades,
            'total_users': total_users,
            'uptime': 99,
            'support': '24/7'
        })
    except Exception as e:
        logger.warning(f"Stats API error: {e}")
        return jsonify({
            'total_trades': 0,
            'total_users': 0,
            'uptime': 99,
            'support': '24/7'
        })
