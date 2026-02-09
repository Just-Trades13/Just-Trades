"""
Discord Notification Service for Just Trades Platform.
Extracted from ultra_simple_server.py — keeps all existing behavior.

Usage:
    from discord_notifications import init_discord_notifications, send_discord_dm, ...

    # Initialize once at startup:
    init_discord_notifications(
        bot_token=DISCORD_BOT_TOKEN,
        get_db_connection=get_db_connection,
        is_using_postgres=is_using_postgres,
        get_chicago_time=get_chicago_time,
        send_push_notification=send_push_notification,
        push_notifications_enabled=PUSH_NOTIFICATIONS_ENABLED,
        user_auth_available=USER_AUTH_AVAILABLE,
        get_auth_db_connection=get_auth_db_connection
    )
"""
import os
import logging
import threading
import requests

logger = logging.getLogger(__name__)

# Module-level state, initialized via init_discord_notifications()
_bot_token = ''
_notifications_enabled = False
_get_db_connection = None
_is_using_postgres = None
_get_chicago_time = None
_send_push_notification = None
_push_notifications_enabled = False
_user_auth_available = False
_get_auth_db_connection = None


def init_discord_notifications(
    bot_token: str,
    get_db_connection,
    is_using_postgres,
    get_chicago_time,
    send_push_notification=None,
    push_notifications_enabled=False,
    user_auth_available=False,
    get_auth_db_connection=None
):
    """
    Initialize the Discord notification module with required dependencies.
    Called once at startup from ultra_simple_server.py.
    """
    global _bot_token, _notifications_enabled
    global _get_db_connection, _is_using_postgres, _get_chicago_time
    global _send_push_notification, _push_notifications_enabled
    global _user_auth_available, _get_auth_db_connection

    _bot_token = bot_token
    _notifications_enabled = bool(bot_token)
    _get_db_connection = get_db_connection
    _is_using_postgres = is_using_postgres
    _get_chicago_time = get_chicago_time
    _send_push_notification = send_push_notification
    _push_notifications_enabled = push_notifications_enabled
    _user_auth_available = user_auth_available
    _get_auth_db_connection = get_auth_db_connection

    if _notifications_enabled:
        logger.info("Discord notifications initialized")
    else:
        logger.info("Discord notifications disabled (no bot token)")


def is_discord_enabled() -> bool:
    """Check if Discord notifications are enabled."""
    return _notifications_enabled


def send_discord_dm(discord_user_id: str, message: str, embed: dict = None) -> bool:
    """
    Send a direct message to a Discord user via bot.

    Args:
        discord_user_id: The Discord user ID to send to
        message: Text message content
        embed: Optional rich embed dict

    Returns:
        True if sent successfully, False otherwise
    """
    if not _bot_token or not discord_user_id:
        return False

    try:
        # Create DM channel with user
        create_dm_url = "https://discord.com/api/v10/users/@me/channels"
        headers = {
            "Authorization": f"Bot {_bot_token}",
            "Content-Type": "application/json"
        }

        dm_response = requests.post(create_dm_url, headers=headers, json={
            "recipient_id": discord_user_id
        }, timeout=10)

        if dm_response.status_code != 200:
            logger.warning(f"⚠️ Failed to create DM channel: {dm_response.status_code}")
            return False

        channel_id = dm_response.json().get('id')
        if not channel_id:
            return False

        # Send message to DM channel
        send_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        payload = {"content": message}
        if embed:
            payload["embeds"] = [embed]

        send_response = requests.post(send_url, headers=headers, json=payload, timeout=10)

        if send_response.status_code in [200, 201]:
            logger.info(f"✅ Discord DM sent to user {discord_user_id}")
            return True
        else:
            logger.warning(f"⚠️ Failed to send Discord DM: {send_response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Discord DM error: {e}")
        return False


def get_discord_enabled_users(user_id: int = None) -> list:
    """
    Get users who have Discord linked and DMs enabled.

    Args:
        user_id: Optional specific user ID to check

    Returns:
        List of dicts with user_id and discord_user_id
    """
    conn = None
    cursor = None
    try:
        if _user_auth_available and _get_auth_db_connection:
            conn, db_type = _get_auth_db_connection()
            cursor = conn.cursor()

            # Rollback any failed transactions (PostgreSQL specific issue)
            try:
                conn.rollback()
            except:
                pass

            if user_id:
                if db_type == 'postgresql':
                    cursor.execute('''
                        SELECT id, discord_user_id FROM users
                        WHERE id = %s AND discord_user_id IS NOT NULL AND discord_dms_enabled = TRUE
                    ''', (user_id,))
                else:
                    cursor.execute('''
                        SELECT id, discord_user_id FROM users
                        WHERE id = ? AND discord_user_id IS NOT NULL AND discord_dms_enabled = 1
                    ''', (user_id,))
            else:
                if db_type == 'postgresql':
                    cursor.execute('''
                        SELECT id, discord_user_id FROM users
                        WHERE discord_user_id IS NOT NULL AND discord_dms_enabled = TRUE
                    ''')
                else:
                    cursor.execute('''
                        SELECT id, discord_user_id FROM users
                        WHERE discord_user_id IS NOT NULL AND discord_dms_enabled = 1
                    ''')

            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Handle both tuple (SQLite) and dict-like (PostgreSQL RealDictRow) rows
                if isinstance(row, tuple):
                    result.append({'user_id': row[0], 'discord_user_id': row[1]})
                else:
                    result.append({'user_id': row['id'], 'discord_user_id': row['discord_user_id']})
            logger.info(f"🔔 Discord users query returned {len(result)} users")
            return result
    except Exception as e:
        logger.error(f"❌ Error getting Discord users: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass
    return []


def get_users_for_recorder_notifications(recorder_id: int) -> list:
    """
    Get all users who should receive notifications for a recorder.
    This includes the recorder owner AND anyone with traders linked to the recorder.

    Args:
        recorder_id: The recorder ID

    Returns:
        List of unique user_ids who should be notified
    """
    user_ids = set()

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        is_postgres = _is_using_postgres()
        ph = '%s' if is_postgres else '?'

        # Get recorder owner
        cursor.execute(f'SELECT user_id FROM recorders WHERE id = {ph}', (recorder_id,))
        row = cursor.fetchone()
        if row:
            owner_id = row[0] if isinstance(row, tuple) else row.get('user_id')
            if owner_id:
                user_ids.add(owner_id)

        # Get all users with traders linked to this recorder
        cursor.execute(f'SELECT DISTINCT user_id FROM traders WHERE recorder_id = {ph} AND user_id IS NOT NULL', (recorder_id,))
        rows = cursor.fetchall()
        for row in rows:
            uid = row[0] if isinstance(row, tuple) else row.get('user_id')
            if uid:
                user_ids.add(uid)

        cursor.close()
        conn.close()

        logger.info(f"🔔 Users for recorder {recorder_id} notifications: {list(user_ids)}")
        return list(user_ids)
    except Exception as e:
        logger.error(f"❌ Error getting users for recorder notifications: {e}")
        return []


def notify_trade_execution(user_id: int = None, action: str = None, symbol: str = None, quantity: int = None,
                           price: float = None, recorder_name: str = None, pnl: float = None,
                           tp_price: float = None, sl_price: float = None, recorder_id: int = None):
    """
    Send trade execution notification to user via Discord AND push notification.

    Args:
        user_id: Database user ID
        action: 'BUY', 'SELL', 'LONG', 'SHORT', 'DCA LONG', 'DCA SHORT'
        symbol: Trading symbol (e.g., 'MNQH5')
        quantity: Number of contracts
        price: Execution price
        recorder_name: Name of the recorder/strategy
        pnl: Realized P&L (for closing trades)
        tp_price: Take profit price (optional)
        sl_price: Stop loss price (optional)
    """
    logger.info(f"🔔 notify_trade_execution called: user_id={user_id}, action={action}, symbol={symbol}, qty={quantity}")

    # Determine if this is a DCA, open, or close
    action_upper = action.upper()
    is_dca = 'DCA' in action_upper
    is_long = 'BUY' in action_upper or 'LONG' in action_upper
    is_close = pnl is not None

    # Build Discord embed
    if is_close:
        # Closing trade
        embed_color = 0x00FF00 if pnl >= 0 else 0xFF0000  # Green if profit, red if loss
        title = f"{recorder_name or 'Trade'} {symbol}"
        description = f"{symbol} Closed a {'LONG' if is_long else 'SHORT'}"
        fields = [
            {"name": "Close Price", "value": f"{price:,.2f}", "inline": True},
            {"name": "Realized Profit", "value": f"${pnl:,.2f}", "inline": True},
            {"name": "Drawdown", "value": "$0.00", "inline": True}
        ]
    else:
        # Opening trade
        embed_color = 0x00FF00 if is_long else 0xFF0000  # Green for long, red for short
        action_text = "DCA" if is_dca else "Opened"
        side_text = "LONG" if is_long else "SHORT"
        title = f"{recorder_name or 'Trade'} {symbol}"
        description = f"{symbol} {action_text} a {side_text}"
        fields = [
            {"name": "Open Price", "value": f"{price:,.2f}", "inline": True},
            {"name": "Current Pos", "value": f"{quantity}", "inline": True},
            {"name": "First TP", "value": f"{tp_price:,.2f}" if tp_price else "None", "inline": True},
            {"name": "Stoploss", "value": f"{sl_price:,.2f}" if sl_price else "0.00", "inline": False}
        ]

    embed = {
        "title": title,
        "description": description,
        "color": embed_color,
        "fields": fields,
        "thumbnail": {"url": "https://justtrades-production.up.railway.app/static/img/just_trades_logo.png"},
        "footer": {"text": "Just.Trades Notification"},
        "timestamp": _get_chicago_time().isoformat()
    }

    # Push notification (plain text)
    push_title = f"{'📈' if is_long else '📉'} {recorder_name or 'Trade'}"
    if is_close:
        push_body = f"Closed {symbol} @ {price:,.2f} • P&L: ${pnl:,.2f}"
    else:
        push_body = f"{'DCA' if is_dca else 'Opened'} {'LONG' if is_long else 'SHORT'} {symbol} @ {price:,.2f}"

    # Get all users to notify
    # If recorder_id provided, notify ALL users linked to the recorder (not just owner)
    if recorder_id:
        user_ids_to_notify = get_users_for_recorder_notifications(recorder_id)
    elif user_id:
        user_ids_to_notify = [user_id]
    else:
        user_ids_to_notify = []

    logger.info(f"🔔 Users to notify: {user_ids_to_notify}")

    # 🚀 FIRE-AND-FORGET: Send notifications in background thread to avoid blocking order execution
    def send_notifications_background():
        """Background thread for sending Discord and Push notifications."""
        try:
            # Send Discord DM with embed to ALL users
            if _notifications_enabled:
                for uid in user_ids_to_notify:
                    try:
                        users = get_discord_enabled_users(uid)
                        for user in users:
                            try:
                                send_discord_dm(user['discord_user_id'], "", embed)
                            except Exception as dm_err:
                                logger.debug(f"Discord DM error: {dm_err}")
                    except Exception as user_err:
                        logger.debug(f"Discord user lookup error: {user_err}")

            # Send Push Notification to ALL users
            if _push_notifications_enabled and _send_push_notification:
                for uid in user_ids_to_notify:
                    try:
                        _send_push_notification(uid, push_title, push_body, url='/dashboard')
                    except Exception as push_err:
                        logger.debug(f"Push notification error: {push_err}")

            logger.debug(f"🔔 Background notifications completed for {len(user_ids_to_notify)} users")
        except Exception as e:
            logger.error(f"🔔 Background notification error: {e}")

    # Start background thread (non-blocking)
    notification_thread = threading.Thread(target=send_notifications_background, daemon=True)
    notification_thread.start()
    logger.info(f"🔔 Notifications dispatched to background thread")


def notify_tp_sl_hit(user_id: int = None, order_type: str = None, symbol: str = None, quantity: int = None,
                     price: float = None, pnl: float = None, recorder_name: str = None,
                     entry_price: float = None, side: str = None, recorder_id: int = None):
    """
    Send TP/SL hit notification via Discord AND push notification.

    Args:
        user_id: Database user ID (deprecated, use recorder_id instead)
        order_type: 'TP' or 'SL'
        symbol: Trading symbol
        quantity: Contracts closed
        price: Fill price (exit price)
        pnl: Realized P&L
        recorder_name: Name of the recorder/strategy
        entry_price: Original entry price
        side: 'LONG' or 'SHORT'
        recorder_id: Recorder ID - will notify ALL users linked to this recorder
    """
    logger.info(f"🔔 notify_tp_sl_hit called: user_id={user_id}, recorder_id={recorder_id}, type={order_type}, symbol={symbol}, pnl={pnl}")

    is_tp = order_type.upper() == 'TP'

    # Build Discord embed
    embed_color = 0x00FF00 if (pnl and pnl >= 0) else 0xFF0000
    title = f"{recorder_name or 'Trade'} {symbol}"
    description = f"{symbol} Closed a {side or 'POSITION'}"

    fields = [
        {"name": "Close Price", "value": f"{price:,.2f}", "inline": True},
        {"name": "Realized Profit", "value": f"${pnl:,.2f}" if pnl else "$0.00", "inline": True},
        {"name": "Drawdown", "value": "$0.00", "inline": True}
    ]

    embed = {
        "title": title,
        "description": description,
        "color": embed_color,
        "fields": fields,
        "thumbnail": {"url": "https://justtrades-production.up.railway.app/static/img/just_trades_logo.png"},
        "footer": {"text": f"Just.Trades • {'Take Profit' if is_tp else 'Stop Loss'}"},
        "timestamp": _get_chicago_time().isoformat()
    }

    # Push notification (plain text)
    push_title = f"{'🎯' if is_tp else '🛑'} {'TP' if is_tp else 'SL'} Hit"
    push_body = f"{symbol} @ {price:,.2f}"
    if pnl is not None:
        push_body += f" • P&L: ${pnl:,.2f}"

    # Get all users to notify
    if recorder_id:
        user_ids_to_notify = get_users_for_recorder_notifications(recorder_id)
    elif user_id:
        user_ids_to_notify = [user_id]
    else:
        user_ids_to_notify = []

    logger.info(f"🔔 Users to notify for TP/SL: {user_ids_to_notify}")

    # 🚀 FIRE-AND-FORGET: Send notifications in background thread to avoid blocking
    def send_tpsl_notifications_background():
        """Background thread for sending TP/SL Discord and Push notifications."""
        try:
            if _notifications_enabled:
                for uid in user_ids_to_notify:
                    try:
                        users = get_discord_enabled_users(uid)
                        for user in users:
                            try:
                                send_discord_dm(user['discord_user_id'], "", embed)
                            except Exception as dm_err:
                                logger.debug(f"Discord DM error: {dm_err}")
                    except Exception as user_err:
                        logger.debug(f"Discord user lookup error: {user_err}")

            if _push_notifications_enabled and _send_push_notification:
                for uid in user_ids_to_notify:
                    try:
                        _send_push_notification(uid, push_title, push_body, url='/dashboard')
                    except Exception as push_err:
                        logger.debug(f"Push notification error: {push_err}")

            logger.debug(f"🔔 Background TP/SL notifications completed")
        except Exception as e:
            logger.error(f"🔔 Background TP/SL notification error: {e}")

    notification_thread = threading.Thread(target=send_tpsl_notifications_background, daemon=True)
    notification_thread.start()
    logger.info(f"🔔 TP/SL notifications dispatched to background thread")


def notify_error(user_id: int, error_type: str, error_message: str, details: str = None):
    """
    Send error notification to user via Discord AND push notification.

    Args:
        user_id: Database user ID
        error_type: Type of error (e.g., 'Connection Lost', 'Webhook Failed')
        error_message: Brief error description
        details: Optional additional details
    """
    # Discord message
    discord_message = f"⚠️ **{error_type}**\n"
    discord_message += f"❌ {error_message}"
    if details:
        discord_message += f"\n📝 {details}"
    discord_message += f"\n⏰ {_get_chicago_time().strftime('%I:%M:%S %p CT')}"

    # Push notification
    push_title = f"⚠️ {error_type}"
    push_body = error_message
    if details:
        push_body += f" - {details[:50]}"

    # Send Discord DM
    if _notifications_enabled:
        users = get_discord_enabled_users(user_id)
        for user in users:
            send_discord_dm(user['discord_user_id'], discord_message)

    # Send Push Notification
    if _push_notifications_enabled and _send_push_notification:
        _send_push_notification(user_id, push_title, push_body, url='/recorders_list')


def notify_daily_summary(user_id: int, total_trades: int, winners: int, losers: int,
                         total_pnl: float, best_trade: float = None, worst_trade: float = None):
    """
    Send daily P&L summary to user.

    Args:
        user_id: Database user ID
        total_trades: Number of trades today
        winners: Number of winning trades
        losers: Number of losing trades
        total_pnl: Total realized P&L
        best_trade: Best single trade P&L
        worst_trade: Worst single trade P&L
    """
    if not _notifications_enabled:
        return

    users = get_discord_enabled_users(user_id)
    if not users:
        return

    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

    message = f"📊 **Daily Trading Summary**\n"
    message += f"━━━━━━━━━━━━━━━━━━━━\n"
    message += f"{pnl_emoji} **Total P&L: ${total_pnl:,.2f}**\n"
    message += f"📈 Trades: {total_trades} ({winners}W / {losers}L)\n"
    message += f"🎯 Win Rate: {win_rate:.1f}%\n"
    if best_trade is not None:
        message += f"🏆 Best Trade: ${best_trade:,.2f}\n"
    if worst_trade is not None:
        message += f"💔 Worst Trade: ${worst_trade:,.2f}\n"
    message += f"━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📅 {_get_chicago_time().strftime('%B %d, %Y')}"

    for user in users:
        send_discord_dm(user['discord_user_id'], message)


def broadcast_announcement(title: str, message: str, announcement_type: str = 'info'):
    """
    Broadcast announcement to ALL users with Discord linked and DMs enabled.

    Args:
        title: Announcement title
        message: Announcement content
        announcement_type: 'info', 'success', 'warning', 'critical'
    """
    if not _notifications_enabled:
        return 0

    type_emojis = {
        'info': 'ℹ️',
        'success': '✅',
        'warning': '⚠️',
        'critical': '🚨'
    }

    emoji = type_emojis.get(announcement_type, 'ℹ️')

    full_message = f"{emoji} **{title}**\n\n{message}\n\n— Just.Trades Team"

    users = get_discord_enabled_users()
    sent_count = 0

    for user in users:
        if send_discord_dm(user['discord_user_id'], full_message):
            sent_count += 1

    logger.info(f"📢 Broadcast sent to {sent_count}/{len(users)} Discord users")
    return sent_count
