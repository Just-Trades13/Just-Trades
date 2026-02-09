from __future__ import annotations
import json, uuid
from datetime import datetime, timedelta
from dateutil import tz, parser

# Simple style map for embed colors and emojis
EVENT_STYLES = {
    "CPI": {"color": 0xE67E22, "emoji": "📈", "tier": 1},
    "PPI": {"color": 0xE67E22, "emoji": "🏭", "tier": 1},
    "NFP": {"color": 0xC0392B, "emoji": "🧰", "tier": 1},
    "FOMC": {"color": 0x8E44AD, "emoji": "🏛️", "tier": 1},
    "FED": {"color": 0x8E44AD, "emoji": "🏛️", "tier": 1},
    "GDP": {"color": 0x3498DB, "emoji": "📊", "tier": 1},
    "ISM": {"color": 0x27AE60, "emoji": "🏭", "tier": 2},
    "EARN": {"color": 0x2ECC71, "emoji": "💼", "tier": 2},
    "OTHER": {"color": 0x95A5A6, "emoji": "⚠️", "tier": 2},
}

def load_json(path: str, default):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        with open(path, 'w') as f:
            json.dump(default, f, indent=2)
        return default

def save_json(path: str, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def local_to_utc(dt_local_str: str, tz_name: str) -> str:
    # 'YYYY-MM-DD HH:MM'
    local = tz.gettz(tz_name)
    dt = datetime.strptime(dt_local_str, "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=local)
    return dt.astimezone(tz.UTC).isoformat()

def utc_to_local(dt_iso: str, tz_name: str) -> str:
    local = tz.gettz(tz_name)
    dt = parser.isoparse(dt_iso)
    return dt.astimezone(local).strftime("%Y-%m-%d %H:%M")

def normalize_events(events, tz_name):
    out = []
    for e in events:
        # Accept either start_local/end_local OR start_utc/end_utc
        if "start_utc" not in e and "start_local" in e:
            e["start_utc"] = local_to_utc(e["start_local"], tz_name)
        if "end_utc" not in e and "end_local" in e:
            e["end_utc"] = local_to_utc(e["end_local"], tz_name)
        if "id" not in e:
            e["id"] = f"evt-{uuid.uuid4().hex[:8]}"
        out.append(e)
    return out

def overlapping(now_utc, start_iso, end_iso):
    return parser.isoparse(start_iso) <= now_utc <= parser.isoparse(end_iso)

def window_status(now_utc, events):
    active = [e for e in events if overlapping(now_utc, e["start_utc"], e["end_utc"])]
    return active

def upcoming(now_utc, events, days=14):
    horizon = now_utc + timedelta(days=days)
    return sorted([e for e in events if parser.isoparse(e["start_utc"]) >= now_utc and parser.isoparse(e["start_utc"]) <= horizon],
                  key=lambda e: e["start_utc"])

def format_event_line(e, tz_name):
    style = EVENT_STYLES.get(e.get("type","OTHER"), EVENT_STYLES["OTHER"])
    start_loc = utc_to_local(e["start_utc"], tz_name)
    end_loc = utc_to_local(e["end_utc"], tz_name)
    return f"{style['emoji']} **{e['title']}** ({e.get('type','OTHER')})\n`{start_loc}` → `{end_loc}`  • id: `{e['id']}`"
