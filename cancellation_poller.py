"""
Polls for cancellations on dates where the midnight booking failed.
Runs hourly via GitHub Actions. Sends an email when a slot opens up
so you can book it manually — no auth token required.
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

    for target in polling:
        date_str = target["date"]
        time_str = target.get("time")
        duration_hours = target.get("duration_hours", 1.0)
        label = f"{date_str} {time_str or 'post-9pm'} {duration_hours}hr"

        # Drop expired targets silently
        if date.fromisoformat(date_str) < today:
            print(f"Dropping expired polling target: {date_str}")
            continue

        print(f"Checking cancellations for {label}...")

        from availability import check_availability
        slots = check_availability(date_str)

        if not slots:
            print(f"No availability yet for {date_str}.")
            still_watching.append(target)
            continue

        if time_str:
            h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
            matching = [s for s in slots if s["start_time"].hour == h and s["start_time"].minute == m]
        else:
            matching = slots

        if not matching:
            print(f"No matching slot yet for {label}.")
            still_watching.append(target)
            continue

        # Slot found — notify and stop watching this target
        slot_times = sorted({s["start_time"].strftime("%I:%M %p") for s in matching})
        body = (
            f"A cancellation just opened up for Five Iron on {date_str}!\n\n"
            f"Available times:\n"
            + "\n".join(f"  • {t}" for t in slot_times)
            + f"\n\nBook now (act fast):\n{BOOKING_URL}\n\n"
            "— Your Five Iron Bot"
        )
        print(f"Cancellation found for {label} — notifying.")
        send_email(subject=f"Cancellation available: Five Iron {date_str}", body=body)

    non_polling = [t for t in targets if t.get("status") != "polling"]
    save_targets(non_polling + still_watching)


if __name__ == "__main__":
    main()
