"""
Runs every Monday morning — sends a summary of upcoming booking nights
for the next 2 weeks so you know what's coming and can update targets.json if needed.

Also usable interactively to add dates to targets.json.
"""

import sys
import json
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from notifier import send_email

TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOCAL_TZ = ZoneInfo("America/New_York")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
DAYS_IN_ADVANCE = 15
VALID_DURATIONS = [0.5, 1.0, 2.0]


def load_targets() -> list:
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE) as f:
        return json.load(f).get("targets", [])


def write_targets(entries: list):
    with open(TARGETS_FILE, "w") as f:
        json.dump({"targets": entries}, f, indent=2)
    print(f"Saved {len(entries)} session(s) to targets.json")


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


def get_upcoming_booking_nights() -> list:
    """Return targets that have a booking night within the next 14 days."""
    today = datetime.now(LOCAL_TZ).date()
    upcoming = []
    targets = load_targets()
    for t in targets:
        try:
            d = date.fromisoformat(t["date"])
            nights_away = (d - today).days - DAYS_IN_ADVANCE + 1
            if 0 <= nights_away <= 14:
                upcoming.append({**t, "books_in_days": nights_away})
        except (KeyError, ValueError):
            pass
    return sorted(upcoming, key=lambda t: t["date"])


def send_summary_email():
    wait_until_9am_et()
    edit_url = f"https://github.com/{GITHUB_REPOSITORY}/edit/master/targets.json"
    upcoming = get_upcoming_booking_nights()

    if upcoming:
        lines = []
        for t in upcoming:
            d = date.fromisoformat(t["date"])
            days = t["books_in_days"]
            when = "tonight" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            time_label = t.get("time", "first post-9pm")
            lines.append(f"  • {d.strftime('%A, %b')} {d.day} — {time_label} {t['duration_hours']}hr — books {when} at midnight")
        schedule_section = "Upcoming booking nights:\n\n" + "\n".join(lines)
    else:
        schedule_section = "No booking nights scheduled in the next 2 weeks."

    body = (
        "Five Iron Golf — weekly schedule summary\n\n"
        + schedule_section
        + f"\n\nEdit your targets.json:\n{edit_url}"
        + "\n\n— Your Five Iron Bot"
    )
    send_email(subject="Five Iron: weekly booking schedule", body=body)
    print("Weekly summary email sent.")


def ask_time(d: date) -> str:
    while True:
        raw = input(f"  Start time for {d.strftime('%A')} (HH:MM 24hr, e.g. 21:00) [default: 21:00]: ").strip()
        if not raw:
            return "21:00"
        try:
            h, m = raw.split(":")
            if 0 <= int(h) <= 23 and int(m) in (0, 30):
                return raw
        except (ValueError, AttributeError):
            pass
        print("  Please enter a valid time in HH:MM format with 30-min increments (e.g. 21:00, 21:30).")


def ask_duration(d: date) -> float:
    while True:
        raw = input(f"  Duration for {d.strftime('%A')} (0.5 / 1 / 2 hours) [default: 1]: ").strip()
        if not raw:
            return 1.0
        try:
            val = float(raw)
            if val in VALID_DURATIONS:
                return val
        except ValueError:
            pass
        print("  Please enter 0.5, 1, or 2.")


def interactive_prompt():
    targets = load_targets()

    print("\nCurrent targets:")
    if targets:
        for t in targets:
            print(f"  {t['date']} — {t['duration_hours']}hr")
    else:
        print("  (none)")

    print("\nEnter dates to add (YYYY-MM-DD), one per line. Empty line to finish:")
    new_entries = []
    while True:
        raw = input("> ").strip()
        if not raw:
            break
        try:
            date.fromisoformat(raw)
            d = date.fromisoformat(raw)
            time_str = ask_time(d)
            duration = ask_duration(d)
            new_entries.append({"date": raw, "time": time_str, "duration_hours": duration})
        except ValueError:
            print(f"  Invalid date format: {raw}")

    if new_entries:
        write_targets(targets + new_entries)
    else:
        print("No changes made.")


def main():
    if sys.stdin.isatty():
        interactive_prompt()
    else:
        send_summary_email()


if __name__ == "__main__":
    main()
