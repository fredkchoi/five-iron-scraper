import time
from datetime import datetime
from availability import check_availability
from notifier import send_email
from config import LOCAL_TZ, POLL_INTERVAL_SECONDS


def main():
    date_str = input("Enter booking date (YYYY-MM-DD): ").strip()
    print(f"Polling Five Iron availability for {date_str}...")

    while True:
        slots = check_availability(date_str)
        if slots:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found availability!")

            unique_times = sorted({s["start_time"].astimezone(LOCAL_TZ).strftime("%I:%M %p") for s in slots})
            body_lines = [f"• {t}" for t in unique_times]

            body = (
                "Hello,\n\n"
                f"The following simulator times are available at Five Iron Golf on {date_str}:\n\n"
                + "\n".join(body_lines)
                + "\n\n— Your Five Iron Notifier Bot"
            )

            send_email(subject=f"Five Iron Availability for {date_str}", body=body)
            break
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No slots yet, checking again in {POLL_INTERVAL_SECONDS / 60:.0f} minutes...")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
