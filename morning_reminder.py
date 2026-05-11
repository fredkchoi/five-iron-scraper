"""
Runs at 9am ET on booking days — sends a reminder with token status
so there's time to recapture it before midnight.
"""

import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from notifier import send_email

TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOCAL_TZ = ZoneInfo("America/New_York")
DAYS_IN_ADVANCE = 15


def get_tonight_targets() -> list:
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE) as f:
        targets = json.load(f).get("targets", [])
    today = datetime.now(LOCAL_TZ).date()
    booking_open_date = (today + timedelta(days=DAYS_IN_ADVANCE)).isoformat()
    return [t for t in targets if t.get("date") == booking_open_date]


def wait_until_9am_et():
    # GitHub cron runs in UTC, so the runner fires at 9am EDT but 8am EST.
    # Sleep to land at exactly 9am ET. Skip for manual runs so testing is instant.
    if os.getenv("GITHUB_EVENT_NAME") != "schedule":
        return
    now = datetime.now(LOCAL_TZ)
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    sleep_secs = (target - now).total_seconds()
    if sleep_secs > 0:
        print(f"Waiting {sleep_secs:.0f}s ({sleep_secs / 60:.1f} min) until 9am ET...")
        time.sleep(sleep_secs)


def main():
    tonight = get_tonight_targets()
    if not tonight:
        print("No booking tonight — nothing to remind.")
        return

    wait_until_9am_et()

    date_str = tonight[0]["date"]
    sessions = [f"  • {t.get('time', 'first post-9pm')} — {t['duration_hours']}hr" for t in tonight]

    from book import validate_token
    valid, reason = validate_token()

    if valid:
        subject = f"Five Iron reminder: booking {date_str} tonight at midnight"
        body = (
            f"Your Five Iron bot will attempt to book {date_str} at midnight ET tonight.\n\n"
            f"Sessions:\n" + "\n".join(sessions) + "\n\n"
            f"Token status: {reason}\n\n"
            "No action needed — you're all set.\n\n"
            "— Your Five Iron Bot"
        )
    else:
        subject = f"Action required: Five Iron token invalid — booking {date_str} tonight"
        body = (
            f"Your Five Iron bot is scheduled to book {date_str} at midnight ET tonight:\n\n"
            + "\n".join(sessions) + "\n\n"
            f"But the auth token is invalid:\n\n"
            f"  {reason}\n\n"
            "To fix this before midnight:\n"
            "  1. Go to fiveirongolf.com, open DevTools (F12) → Network tab\n"
            "  2. Log in and browse available times\n"
            "  3. Copy the Authorization header from any api.booking.fiveirongolf.com request\n"
            "  4. Update FIVE_IRON_AUTH_TOKEN in GitHub Secrets\n"
            "     (Settings → Secrets and variables → Actions)\n\n"
            "— Your Five Iron Bot"
        )

    print(subject)
    send_email(subject=subject, body=body)


if __name__ == "__main__":
    main()
