"""
Five Iron booking — authenticated 3-step flow:
  1. POST /auth/login (no bookingUUID) + poll Gmail + GET /auth/verify  -> session token
  2. POST /appointments/pricing                                          -> real sessionTypeId + cost
  3. POST /appointments/book/{locationId}                                -> confirmed booking

No pre-booking or promo code needed; happy hour pricing applied automatically by the pricing step.
"""

import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from availability import check_availability
from config import (
    FIVE_IRON_EMAIL,
    LOCATION_ID,
    PARTY_SIZE,
    SENDER_EMAIL,
    SENDER_PASSWORD,
)
from token_refresh import fetch_fresh_token

BASE_URL = "https://api.booking.fiveirongolf.com"
_TZ = ZoneInfo("America/New_York")

_token_override = ""


def set_token(token: str):
    global _token_override
    _token_override = token


def get_valid_token() -> str:
    """Return the current in-memory token, or '' if none."""
    return _token_override


def refresh_token() -> str:
    """
    Fetch a fresh session token via magic link + Gmail IMAP.
    Stores it in memory and returns it. Returns '' on failure.
    """
    access, _ = fetch_fresh_token(FIVE_IRON_EMAIL, LOCATION_ID, SENDER_EMAIL, SENDER_PASSWORD)
    if access:
        set_token(access)
    return access


def _get_pricing(token: str, slot: dict) -> list:
    """
    POST /appointments/pricing to get the real sessionTypeId and cost for a slot.
    Returns a list of staff pricing entries, each with costSummary[].
    """
    resp = requests.post(
        f"{BASE_URL}/appointments/pricing",
        json={
            "email": FIVE_IRON_EMAIL,
            "startDateTime": slot["start_time"].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDateTime": slot["end_time"].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "locationId": LOCATION_ID,
            "staffIds": [slot["staff_id"]],
            "partySize": PARTY_SIZE,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if not resp.ok:
        print(f"[pricing] HTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    return resp.json()


def _post_booking(token: str, pricing_result: list) -> dict:
    """
    POST /appointments/book/{locationId} using appointments built from the pricing result.
    Returns the first booking dict from the API response.
    """
    appointments = []
    for entry in pricing_result:
        for cs in entry.get("costSummary", []):
            appointments.append({
                "startDateTime": cs["startTime"],
                "endDateTime": cs["endTime"],
                "staffId": entry["staffId"],
                "sessionTypeId": cs["sessionTypeId"],
                "notes": "",
                "resourceId": None,
                "cost": cs["price"],
            })

    resp = requests.post(
        f"{BASE_URL}/appointments/book/{LOCATION_ID}",
        json={
            "email": FIVE_IRON_EMAIL,
            "partySize": PARTY_SIZE,
            "leftHanded": False,
            "clubRental": False,
            "appointments": appointments,
            "addOns": [],
            "multiSportSimRental": False,
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=60,
    )
    if not resp.ok:
        print(f"[book] HTTP {resp.status_code}: {resp.text[:400]}")
    resp.raise_for_status()
    bookings = resp.json()
    if not isinstance(bookings, list) or not any(b.get("status") == "Booked" for b in bookings):
        raise RuntimeError(f"Unexpected booking response: {resp.text[:200]}")
    return bookings[0]


def _slots_for_duration(slots: list, duration_hours: float) -> list:
    return sorted(
        [s for s in slots if abs(s["duration_hours"] - duration_hours) < 0.01],
        key=lambda s: s["start_time"],
    )


def find_session(slots: list, duration_hours: float, time_str: str = None) -> list:
    """
    Pick slot(s) satisfying the requested session.
    Returns a list of slot dicts — one entry for 0.5/1.0hr, two for 1.5/2.0hr.
    For multi-slot durations, sub-sessions must be time-consecutive (any bay).
    time_str pins only the first sub-session's start.
    """
    def matches_time(s):
        if not time_str:
            return True
        h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        return s["start_time"].hour == h and s["start_time"].minute == m

    if duration_hours == 0.5:
        return next(([s] for s in _slots_for_duration(slots, 0.5) if matches_time(s)), [])

    if duration_hours == 1.0:
        return next(([s] for s in _slots_for_duration(slots, 1.0) if matches_time(s)), [])

    if duration_hours == 1.5:
        one_hr = _slots_for_duration(slots, 1.0)
        half_hr = _slots_for_duration(slots, 0.5)
        for first in one_hr:
            if not matches_time(first):
                continue
            for second in half_hr:
                if second["start_time"] == first["end_time"]:
                    return [first, second]
        return []

    if duration_hours == 2.0:
        one_hr = _slots_for_duration(slots, 1.0)
        for first in one_hr:
            if not matches_time(first):
                continue
            for second in one_hr:
                if second["start_time"] == first["end_time"]:
                    return [first, second]
        return []

    return []


def attempt_booking(date_str: str, duration_hours: float = 1.0, time_str: str = None) -> list:
    """
    Find available slot(s) and book them.

    Requires a valid in-memory token (set via set_token() or refresh_token()).
    time_str: optional "HH:MM" (24hr) for the first sub-session's start.
    Returns a list of booking confirmation dicts. Empty list means nothing booked.
    """
    token = get_valid_token()
    if not token:
        raise ValueError("No session token — call refresh_token() before attempt_booking()")

    slots = check_availability(date_str)
    if not slots:
        return []

    matched = find_session(slots, duration_hours, time_str)
    if not matched:
        if time_str:
            print(f"[Error] No matching {duration_hours}hr session at {time_str} on {date_str}")
        return []

    results = []
    for slot in matched:
        pricing = _get_pricing(token, slot)
        booking = _post_booking(token, pricing)
        results.append(booking)
        start = datetime.fromisoformat(booking["startDateTime"]).strftime("%I:%M %p")
        end = datetime.fromisoformat(booking["endDateTime"]).strftime("%I:%M %p")
        print(f"Booked: {start}-{end}  ID={booking['id']}")

    return results
