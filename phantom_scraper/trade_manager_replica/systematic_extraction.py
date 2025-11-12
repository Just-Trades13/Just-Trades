#!/usr/bin/env python3
"""
Systematic Extraction Script for Trade Manager
This script will help track what we've extracted and what's missing
"""

import json
from datetime import datetime

EXTRACTION_STATUS = {
    "metadata": {
        "project_name": "Just.Trades",
        "source_site": "trademanagergroup.com",
        "extraction_date": datetime.now().isoformat(),
        "goal": "Complete exact replica of Trade Manager"
    },
    "pages": {
        "/user/dashboard": {
            "status": "extracted",
            "api_endpoints": [
                "/api/auth/check-auth/",
                "/api/trades/",
                "/api/trades/open/",
                "/api/profiles/get-stat-config/",
                "/api/profiles/get-favorites/",
                "/api/profiles/get-widget-info/",
                "/api/strategies/get-strat/"
            ],
            "ui_components": "extracted",
            "workflows": "extracted"
        },
        "/user/strats": {
            "status": "extracted",
            "api_endpoints": [
                "/api/strategies/"
            ],
            "ui_components": "extracted",
            "workflows": "extracted"
        },
        "/user/strat": {
            "status": "extracted",
            "api_endpoints": [
                "/api/strategies/?val=DirStrat",
                "/api/trades/tickers/",
                "/api/trades/timeframes/"
            ],
            "form_fields": "extracted",
            "missing": "POST request payload when submitting form"
        },
        "/user/at/accnts": {
            "status": "extracted",
            "api_endpoints": [
                "/api/accounts/get-all-at-accounts/",
                "/api/profiles/get-limits/"
            ],
            "ui_components": "extracted",
            "actions": [
                "Edit Account Credentials",
                "Refresh SubAccount",
                "Delete",
                "Clear Trade"
            ]
        },
        "/user/at/accntsetup": {
            "status": "in_progress",
            "api_endpoints": [],
            "form_fields": "extracting",
            "platforms": ["Tradovate", "Webull", "Tradier", "Blofin", "ProjectX", "Rithmic"]
        },
        "/user/at/strats": {
            "status": "pending",
            "api_endpoints": [],
            "notes": "Different from /user/strats (My Recorders)"
        },
        "/user/at/controls": {
            "status": "pending",
            "api_endpoints": [],
            "notes": "Control Center functionality"
        },
        "/user/settings": {
            "status": "pending",
            "api_endpoints": [],
            "notes": "User settings, Discord integration"
        }
    },
    "api_endpoints": {
        "discovered": 20,
        "with_payloads": 3,
        "missing_payloads": 17
    },
    "data_models": {
        "status": "partial",
        "tables_identified": [
            "users",
            "accounts",
            "subaccounts",
            "strategies",
            "recorded_positions",
            "strategy_logs",
            "trades"
        ]
    },
    "next_steps": [
        "Complete Add Account form extraction",
        "Capture POST request when adding account",
        "Navigate to My Trader page",
        "Navigate to Control Center",
        "Navigate to Settings",
        "Extract all POST/PUT/DELETE payloads",
        "Extract all response formats",
        "Document complete UI component structure",
        "Map all user workflows"
    ]
}

def save_status():
    """Save extraction status to file"""
    import os
    file_path = os.path.join(os.path.dirname(__file__), 'EXTRACTION_STATUS.json')
    with open(file_path, 'w') as f:
        json.dump(EXTRACTION_STATUS, f, indent=2)
    print("✅ Extraction status saved!")

if __name__ == "__main__":
    save_status()
    print(f"\n📊 Extraction Progress:")
    print(f"   Pages extracted: {sum(1 for p in EXTRACTION_STATUS['pages'].values() if p['status'] == 'extracted')}")
    print(f"   Pages in progress: {sum(1 for p in EXTRACTION_STATUS['pages'].values() if p['status'] == 'in_progress')}")
    print(f"   Pages pending: {sum(1 for p in EXTRACTION_STATUS['pages'].values() if p['status'] == 'pending')}")
    print(f"   API endpoints: {EXTRACTION_STATUS['api_endpoints']['discovered']}")
    print(f"   Missing payloads: {EXTRACTION_STATUS['api_endpoints']['missing_payloads']}")

