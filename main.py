import requests
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config import (
    SENDER_EMAIL,
    SENDER_PASSWORD,
    RECIPIENT_EMAIL,
    LOCATION_ID,
    PARTY_SIZE,
    LOCAL_TZ,
    POLL_INTERVAL_SECONDS,
)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())


def check_availability(date_str: str):
    url = (
        f"https://api.booking.fiveirongolf.com/appointments/available/simulator"
        f"?locationId={LOCATION_ID}&partySize={PARTY_SIZE}"
        f"&startDateTime={date_str}&endDateTime={date_str}"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[Error] Failed to fetch availability: {e}")
        return None

    results = []

    for slot in data:
        start_time = datetime.fromisoformat(slot["time"].replace("Z", ""))

        if start_time.hour >= 21:
            for avail in slot["availabilities"]:
                for duration_entry in avail["durations"]:
                    duration = duration_entry["duration"] / 60
                    if duration >= 1:
                        results.append(
                            (
                                start_time,
                                duration,
                                duration_entry["cost"],
                            )
                        )

    return results


def main():
    date_str = input("Enter booking date (YYYY-MM-DD): ").strip()
    print(f"Polling Five Iron availability for {date_str}...")

    while True:
        slots = check_availability(date_str)
        if slots:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found availability!")

            unique_times = sorted({s[0].astimezone(LOCAL_TZ).strftime("%I:%M %p") for s in slots})
            body_lines = [f"• {t}" for t in unique_times]

            body = (
                f"Hello,\n\n"
                f"The following simulator times are available at Five Iron Golf on {date_str}:\n\n"
                + "\n".join(body_lines)
                + "\n\n"
                "— Your Five Iron Notifier Bot"
            )

            send_email(
                subject=f"Five Iron Availability for {date_str}",
                body=body,
            )
            break
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No slots yet, checking again in {POLL_INTERVAL_SECONDS / 60:.0f} minutes...")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
