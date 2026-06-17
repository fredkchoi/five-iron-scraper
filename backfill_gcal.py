"""
One-off: backfill a Google Calendar event for a Five Iron booking that
succeeded but failed to create a calendar event (e.g. because the OAuth
refresh token had expired).

Usage:
    python backfill_gcal.py <YYYY-MM-DD> <HH:MM> <duration_hours>

Example:
    python backfill_gcal.py 2026-07-01 21:00 1
"""
import sys
from datetime import datetime, timedelta

from gcal import create_booking_event


def main() -> int:
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <YYYY-MM-DD> <HH:MM> <duration_hours>")
        return 1

    date_str, time_str, duration_str = sys.argv[1], sys.argv[2], sys.argv[3]
    start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=float(duration_str))

    print(f"Creating calendar event for {start_dt} to {end_dt}")
    url = create_booking_event(start_dt, end_dt)
    if not url:
        print("Backfill failed (see [gcal] line above).")
        return 1
    print(f"Backfill OK: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
