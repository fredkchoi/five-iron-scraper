"""
Nightly runner — validates targets, then books at midnight ET.

Triggered by GitHub Actions at ~11:25pm ET, or run manually for testing.
Flow:
  1. Load and validate targets.json — email errors and exit if invalid
  2. Check if any target opens tonight at midnight
  3. Wait until midnight ET
  4. Book each session for tonight's target; email result per booking
  5. Remove tonight's target from targets.json
"""

import json
import time
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from notifier import send_email

TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOCAL_TZ = ZoneInfo("America/New_York")
# Five Iron releases bookings at midnight on the date 14 days before the bookable date.
# When this script runs the night before that midnight, the target is today+15 days away.
DAYS_IN_ADVANCE = 15


def load_targets() -> list:
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE) as f:
        data = json.load(f)
    return data.get("targets", [])


def save_targets(targets: list):
    with open(TARGETS_FILE, "w") as f:
        json.dump({"targets": targets}, f, indent=2)


def validate_targets(targets: list) -> list:
    """Return a list of error strings. Empty list means all targets are valid."""
    errors = []
    valid_durations = {0.5, 1.0, 1.5, 2.0}

    for i, t in enumerate(targets):
        prefix = f"Target {i + 1}"
        if not isinstance(t, dict):
            errors.append(f"{prefix}: must be an object with 'date' and 'duration_hours'")
            continue

        date_str = t.get("date")
        if not date_str:
            errors.append(f"{prefix}: missing 'date' field")
        else:
            try:
                d = date.fromisoformat(date_str)
                if d <= datetime.now(LOCAL_TZ).date():
                    errors.append(f"{prefix}: date {date_str} is in the past")
            except ValueError:
                errors.append(f"{prefix}: invalid date '{date_str}' — expected YYYY-MM-DD")

        dur = t.get("duration_hours")
        if dur is None:
            errors.append(f"{prefix}: missing 'duration_hours' field")
        elif dur not in valid_durations:
            errors.append(f"{prefix}: duration_hours must be 0.5, 1, 1.5, or 2 (got {dur})")

        time_str = t.get("time")
        if time_str is not None:
            try:
                h, m = time_str.split(":")
                if not (0 <= int(h) <= 23 and int(m) in (0, 30)):
                    raise ValueError
            except (ValueError, AttributeError):
                errors.append(f"{prefix}: time '{time_str}' must be HH:MM in 30-min increments (e.g. '21:00', '21:30')")

    return errors


def get_tonight_targets(targets: list) -> list:
    """Return all targets whose bookings open tonight at midnight (exactly 15 days out)."""
    today = datetime.now(LOCAL_TZ).date()
    booking_open_date = (today + timedelta(days=DAYS_IN_ADVANCE)).isoformat()
    return [t for t in targets if t.get("date") == booking_open_date]


def get_already_open_targets(targets: list) -> list:
    """Return targets whose booking window is already open (1–14 days out)."""
    today = datetime.now(LOCAL_TZ).date()
    return [
        t for t in targets
        if today.isoformat() < t.get("date", "") <= (today + timedelta(days=DAYS_IN_ADVANCE - 1)).isoformat()
    ]



def wait_until_midnight_et():
    now = datetime.now(LOCAL_TZ)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    sleep_secs = (midnight - now).total_seconds()
    if sleep_secs > 0:
        print(f"Waiting {sleep_secs:.0f}s ({sleep_secs / 60:.1f} min) until midnight ET...")
        time.sleep(sleep_secs)
    else:
        print("Already past midnight ET — proceeding immediately.")


def _add_calendar_event(start_dt: datetime, end_dt: datetime):
    """Create a Google Calendar event if credentials are configured."""
    if not os.getenv("GOOGLE_REFRESH_TOKEN"):
        return
    try:
        from gcal import create_booking_event
        create_booking_event(start_dt, end_dt)
    except Exception as e:
        print(f"[gcal] Skipping calendar event: {e}")


def book_target(target: dict) -> bool:
    """Attempt to book a single target entry. Returns True if all sessions booked."""
    from book import attempt_booking
    date_str = target["date"]
    duration_hours = target.get("duration_hours", 1.0)
    time_str = target.get("time")
    label = f"{date_str} {time_str or 'first post-9pm'} {duration_hours}hr"
    max_minutes = 5
    deadline = datetime.now(LOCAL_TZ) + timedelta(minutes=max_minutes)
    attempt = 0

    while datetime.now(LOCAL_TZ) < deadline:
        attempt += 1
        print(f"[Attempt {attempt}] Booking {label}...")
        try:
            bookings = attempt_booking(date_str, duration_hours, time_str)
            if bookings:
                lines = []
                for b in bookings:
                    start = datetime.fromisoformat(b["startDateTime"])
                    end = datetime.fromisoformat(b["endDateTime"])
                    lines.append(f"  • {start.strftime('%I:%M %p')}–{end.strftime('%I:%M %p')}  (ID: {b['id']})")
                    _add_calendar_event(start, end)
                body = (
                    f"Successfully booked Five Iron on {date_str}!\n\n"
                    + "\n".join(lines)
                    + "\n\n— Your Five Iron Bot"
                )
                print(body)
                send_email(subject=f"Booked: Five Iron {date_str}", body=body)
                return True
        except ValueError as e:
            print(f"[Error] {e}")
            return False
        except Exception as e:
            print(f"[Attempt {attempt}] Error: {e}")
        time.sleep(10)

    body = (
        f"Failed to book Five Iron: {label} "
        f"after retrying for {max_minutes} minutes.\n\n— Your Five Iron Bot"
    )
    print(body)
    send_email(subject=f"FAILED: Five Iron booking for {date_str}", body=body)
    return False


def main():
    targets = load_targets()

    errors = validate_targets(targets)
    if errors:
        body = "targets.json has validation errors — please fix before the next booking night:\n\n"
        body += "\n".join(f"  • {e}" for e in errors)
        body += "\n\n— Your Five Iron Bot"
        print(body)
        send_email(subject="Five Iron: targets.json has errors", body=body)
        return

    tonight = get_tonight_targets(targets)
    already_open = get_already_open_targets(targets)

    if not tonight and not already_open:
        print(f"No bookings to attempt tonight. Current targets: {[t['date'] for t in targets]}")
        return

    # Get a fresh session token before doing anything time-sensitive
    print("Getting session token via magic link...")
    from book import refresh_token
    token = refresh_token()
    if not token:
        dates = [t["date"] for t in tonight + already_open]
        body = (
            f"Five Iron booking(s) for {', '.join(dates)} could not proceed — "
            "magic link flow failed, no session token obtained.\n\n"
            "Check that FIVE_IRON_EMAIL, SENDER_EMAIL, and SENDER_PASSWORD are set correctly.\n\n"
            "— Your Five Iron Bot"
        )
        print(body)
        send_email(subject="Action required: Five Iron token refresh failed", body=body)
        return
    print("Session token obtained.")

    failed = []

    # Already-open targets: booking window is live, try immediately (no midnight wait)
    for target in already_open:
        print(f"Attempting already-open target: {target['date']}")
        success = book_target(target)
        if not success:
            failed.append({**target, "status": "polling"})

    # Midnight targets: wait until 12:00am then book
    if tonight:
        date_str = tonight[0]["date"]
        print(f"Tonight: {len(tonight)} session(s) for {date_str} open at midnight ET.")
        wait_until_midnight_et()
        for target in tonight:
            success = book_target(target)
            if not success:
                failed.append({**target, "status": "polling"})

    # Remove all attempted targets; re-add failures as polling targets
    attempted_dates = {t["date"] for t in tonight + already_open}
    updated = [t for t in targets if t.get("date") not in attempted_dates] + failed
    save_targets(updated)


if __name__ == "__main__":
    main()
