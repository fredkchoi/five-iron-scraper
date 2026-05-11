import requests
from datetime import datetime, timedelta
from config import LOCATION_ID, PARTY_SIZE, is_happy_hour


def check_availability(date_str: str):
    """
    Return all available 5i After Dark slots for the given date, any duration.
    Sun–Thu: 9pm+, Fri–Sat: 10pm+.
    Each slot dict contains all fields needed to make a booking.
    """
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
        if is_happy_hour(start_time):
            for avail in slot["availabilities"]:
                for duration_entry in avail["durations"]:
                    duration_minutes = duration_entry["duration"]
                    results.append({
                        "start_time": start_time,
                        "end_time": start_time + timedelta(minutes=duration_minutes),
                        "duration_hours": duration_minutes / 60,
                        "cost": duration_entry["cost"],
                        "staff_id": avail["staffId"],
                    })

    return results
