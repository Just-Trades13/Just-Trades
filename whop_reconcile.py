"""
Whop Reconciliation Script — One-Time Full Sync
================================================
Fetches ALL memberships from Whop, compares against local DB,
cancels stale subscriptions, and revokes access for users with
no remaining active subs.

Usage:
    railway run python3 whop_reconcile.py          # Against production
    python3 whop_reconcile.py                      # Local (needs DATABASE_URL + WHOP_API_KEY)
    python3 whop_reconcile.py --dry-run             # Preview only, no changes
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger('whop_reconcile')

DRY_RUN = '--dry-run' in sys.argv


def main():
    from whop_integration import whop_api_request, WHOP_PRODUCT_MAP
    from subscription_models import (
        get_subscription_db_connection, cancel_subscription,
        has_user_had_any_trial
    )
    from user_auth import unapprove_user

    # ── Step 1: Fetch ALL memberships from Whop ──────────────────────────
    print("=" * 60)
    print("WHOP RECONCILIATION SCRIPT")
    print(f"Mode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE — will modify DB'}")
    print("=" * 60)

    all_memberships = []
    page = 1
    while True:
        result = whop_api_request('GET', f'/memberships?per=100&page={page}')
        if not result:
            if page == 1:
                print("FATAL: Whop API returned None — check WHOP_API_KEY")
                sys.exit(1)
            break

        batch = result.get('data', [])
        if not batch:
            break
        all_memberships.extend(batch)
        print(f"  Fetched page {page}: {len(batch)} memberships")

        pagination = result.get('pagination', {})
        if not pagination.get('next_page'):
            break
        page += 1

    print(f"\nTotal memberships from Whop: {len(all_memberships)}")

    # ── Step 2: Categorize memberships ───────────────────────────────────
    valid_membership_ids = set()
    invalid_membership_ids = set()

    for m in all_memberships:
        mid = m.get('id')
        if not mid:
            continue
        if m.get('valid'):
            valid_membership_ids.add(mid)
        else:
            invalid_membership_ids.add(mid)

    print(f"  Valid (active/trialing): {len(valid_membership_ids)}")
    print(f"  Invalid (cancelled/expired): {len(invalid_membership_ids)}")

    # ── Step 3: Find local subscriptions that should be cancelled ────────
    conn, db_type = get_subscription_db_connection()
    cursor = conn.cursor()
    ph = '%s' if db_type == 'postgresql' else '?'

    try:
        # Get all local active/trialing subscriptions with a whop_membership_id
        cursor.execute(
            "SELECT id, user_id, plan_slug, whop_membership_id, status "
            "FROM user_subscriptions "
            "WHERE status IN ('active', 'trialing') AND whop_membership_id IS NOT NULL"
        )
        local_active = [dict(row) for row in cursor.fetchall()]
        print(f"\nLocal active/trialing subscriptions with Whop ID: {len(local_active)}")

        # Find mismatches: locally active but Whop says invalid
        # Skip admin-granted subs — those were manually assigned, not from Whop
        to_cancel = []
        skipped_admin = 0
        for sub in local_active:
            whop_mid = sub.get('whop_membership_id')
            if whop_mid and whop_mid.startswith('admin_granted_'):
                skipped_admin += 1
                continue
            if whop_mid and whop_mid.startswith('mem_test_'):
                skipped_admin += 1
                continue
            if whop_mid in invalid_membership_ids:
                to_cancel.append(sub)
            elif whop_mid not in valid_membership_ids:
                # Not in Whop response at all — might be old/deleted
                # Verify individually before cancelling
                from whop_integration import verify_membership
                verification = verify_membership(whop_mid)
                if verification is None or not verification.get('valid'):
                    to_cancel.append(sub)
                    print(f"  Individually verified {whop_mid} → invalid/not found")
        if skipped_admin:
            print(f"  Skipped {skipped_admin} admin-granted/test subscriptions")

        print(f"\nSubscriptions to CANCEL (locally active, Whop says invalid): {len(to_cancel)}")
        for sub in to_cancel:
            print(f"  - user_id={sub['user_id']}, plan={sub['plan_slug']}, "
                  f"membership={sub['whop_membership_id']}, local_status={sub['status']}")

        # ── Step 4: Cancel stale subscriptions ───────────────────────────
        cancelled_count = 0
        if to_cancel and not DRY_RUN:
            for sub in to_cancel:
                try:
                    cancel_subscription(whop_membership_id=sub['whop_membership_id'])
                    cancelled_count += 1
                    print(f"  CANCELLED: user_id={sub['user_id']}, {sub['plan_slug']}")
                except Exception as e:
                    print(f"  ERROR cancelling {sub['whop_membership_id']}: {e}")

        # ── Step 5: Find users with NO remaining active subs ─────────────
        # Re-query after cancellations
        cursor2 = conn.cursor()
        try:
            cursor2.execute(
                "SELECT DISTINCT us.user_id FROM user_subscriptions us "
                "JOIN users u ON u.id = us.user_id "
                "WHERE us.status = 'cancelled' "
                "AND u.is_approved = TRUE "
                "AND u.is_admin = FALSE "
                "AND us.user_id > 0 "
                "AND NOT EXISTS ("
                "    SELECT 1 FROM user_subscriptions us2 "
                "    WHERE us2.user_id = us.user_id "
                "    AND us2.status IN ('active', 'trialing')"
                ")"
            )
            users_to_unapprove = [dict(row)['user_id'] for row in cursor2.fetchall()]
        finally:
            cursor2.close()

        print(f"\nUsers to UNAPPROVE (is_approved=TRUE, zero active subs, non-admin): {len(users_to_unapprove)}")

        # Get emails for reporting
        if users_to_unapprove:
            cursor3 = conn.cursor()
            try:
                placeholders = ', '.join([ph] * len(users_to_unapprove))
                cursor3.execute(
                    f"SELECT id, email, username FROM users WHERE id IN ({placeholders})",
                    tuple(users_to_unapprove)
                )
                user_details = [dict(row) for row in cursor3.fetchall()]
                for u in user_details:
                    print(f"  - user_id={u['id']}, email={u.get('email', '?')}, username={u.get('username', '?')}")
            finally:
                cursor3.close()

        # ── Step 6: Revoke access ────────────────────────────────────────
        unapproved_count = 0
        if users_to_unapprove and not DRY_RUN:
            for uid in users_to_unapprove:
                try:
                    unapprove_user(uid)
                    unapproved_count += 1
                except Exception as e:
                    print(f"  ERROR unapproving user {uid}: {e}")

        # ── Summary ──────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("RECONCILIATION SUMMARY")
        print("=" * 60)
        print(f"Whop memberships fetched:     {len(all_memberships)}")
        print(f"  Valid:                       {len(valid_membership_ids)}")
        print(f"  Invalid:                     {len(invalid_membership_ids)}")
        print(f"Local active subs checked:     {len(local_active)}")
        print(f"Subscriptions cancelled:       {cancelled_count if not DRY_RUN else f'{len(to_cancel)} (dry run)'}")
        print(f"Users access revoked:          {unapproved_count if not DRY_RUN else f'{len(users_to_unapprove)} (dry run)'}")

        if DRY_RUN:
            print("\n** DRY RUN — no changes were made. Run without --dry-run to apply. **")

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
