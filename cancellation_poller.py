"""
Polls for cancellations on dates where the midnight booking failed.
Runs hourly via GitHub Actions. Sends an email when the exact requested
session (duration + optional start time) opens up so you can book it
manually — no auth token required.
"""

import json
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo
from notifier import send_email

TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOCAL_TZ = ZoneInfo("America/New_York")
BOOKING_URL = "https://www.fiveirongolf.com/booking"


def load_targets() -> list:
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE) as f:
        return json.load(f).get("targets", [])


def save_targets(targets: list):
    with open(TARGETS_FILE, "w") as f:
        json.dump({"targets": targets}, f, indent=2)


def main():
    targets = load_targets()
    polling = [t for t in targets if t.get("status") == "polling"]

    if not polling:
        print("No cancellation polling targets.")
        return

    today = datetime.now(LOCAL_TZ).date()
    still_watching = []

    from availability import check_availability
    from book import find_session

    for target in polling:
        date_str = target["date"]
        time_str = target.get("time")
        duration_hours = target.get("duration_hours", 1.0)
        label = f"{date_str} {time_str or 'post-9pm'} {duration_hours}hr"

        target_date = date.fromisoformat(date_str)
        if target_date < today:
            print(f"Dropping expired polling target: {date_str}")
            continue
        if target_date == today:
            # Drop once the session start time has passed (or end of happy hour if no time specified)
            h, m = (int(x) for x in time_str.split(":")) if time_str else (23, 0)
            cutoff = datetime.now(LOCAL_TZ).replace(hour=h, minute=m, second=0, microsecond=0)
            if datetime.now(LOCAL_TZ) >= cutoff:
                print(f"Dropping expired polling target: {date_str} {time_str or '23:00'} has passed.")
                continue

        print(f"Checking cancellations for {label}...")
        slots = check_availability(date_str)

        if not slots:
            print(f"No availability yet for {date_str}.")
            still_watching.append(target)
            continue

        matched = find_session(slots, duration_hours, time_str)
        if not matched:
            print(f"No matching {duration_hours}hr session yet for {label}.")
            still_watching.append(target)
            continue

        session_times = [
            f"{s['start_time'].strftime('%I:%M %p')}–{s['end_time'].strftime('%I:%M %p')}"
            for s in matched
        ]
        body = (
            f"A cancellation just opened up for Five Iron on {date_str}!\n\n"
            f"Your requested {duration_hours}hr session is available:\n"
            + "\n".join(f"  • {t}" for t in session_times)
            + f"\n\nBook now (act fast):\n{BOOKING_URL}\n\n"
            "— Your Five Iron Bot"
        )
        print(f"Cancellation found for {label} — notifying.")
        send_email(subject=f"Cancellation available: Five Iron {date_str}", body=body)

    non_polling = [t for t in targets if t.get("status") != "polling"]
    save_targets(non_polling + still_watching)


if __name__ == "__main__":
    main()
