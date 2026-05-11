# Five Iron booking implementation.
#
# Auth uses a bearer token captured once after manual login (passwordless — Google
# or magic link). Token typically lasts 24h; recapture via DevTools when it expires:
#   1. Go to fiveirongolf.com, open DevTools (F12) → Network tab
#   2. Log in and browse available times
#   3. Copy the Authorization header from any api.booking.fiveirongolf.com request
#   4. Store the token (after "Bearer ") as FIVE_IRON_AUTH_TOKEN in .env / GitHub secrets

import base64
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from availability import check_availability
from config import (
    FIVE_IRON_AUTH_TOKEN,
    FIVE_IRON_EMAIL,
    FIVE_IRON_SESSION_TYPE_ID,
    FIVE_IRON_PROMO_CODE,
    LOCATION_ID,
    PARTY_SIZE,
)

BASE_URL = "https://api.booking.fiveirongolf.com"
_TZ = ZoneInfo("America/New_York")
_SESSION_TYPE_30MIN = 45
_SESSION_TYPE_60MIN = 44


def _decode_jwt_expiry(token: str):
    """Decode the exp claim from a JWT without verifying the signature."""
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return datetime.fromtimestamp(exp, _TZ) if exp else None
    except Exception:
        return None


def validate_token() -> tuple:
    """
    Check that the token is present, well-formed, and not expired.
    Returns (is_valid, reason) — reason is empty when valid, descriptive when not.
    """
    if not FIVE_IRON_AUTH_TOKEN:
        return False, "FIVE_IRON_AUTH_TOKEN is not set in .env / GitHub secrets"
    parts = FIVE_IRON_AUTH_TOKEN.split(".")
    if len(parts) != 3 or not FIVE_IRON_AUTH_TOKEN.startswith("eyJ"):
        return False, "FIVE_IRON_AUTH_TOKEN does not look like a valid JWT"

    exp = _decode_jwt_expiry(FIVE_IRON_AUTH_TOKEN)
    if exp is not None:
        now = datetime.now(_TZ)
        if exp < now:
            return False, f"Token expired {exp.strftime('%b %d at %I:%M %p ET')}"
        hours_left = (exp - now).total_seconds() / 3600
        if hours_left < 2:
            return False, f"Token expires in {hours_left:.1f}h ({exp.strftime('%I:%M %p ET')}) — too close to midnight"
        return True, f"Token valid until {exp.strftime('%b %d at %I:%M %p ET')} ({hours_left:.0f}h remaining)"

    return True, "Token looks valid (no expiry claim found)"


def _post_booking(slot: dict, session_type_id: int) -> dict:
    """
    POST a single booking. Returns the booking dict from the API on success,
    raises on HTTP error.
    """
    valid, reason = validate_token()
    if not valid:
        raise ValueError(f"Invalid auth token: {reason}")

    is_late_night = slot["start_time"].hour >= 21
    promo = FIVE_IRON_PROMO_CODE if is_late_night else ""

    payload = {
        "email": FIVE_IRON_EMAIL,
        "promoCode": promo,
        "partySize": PARTY_SIZE,
        "leftHanded": False,
        "clubRental": False,
        "appointments": [
            {
                "startDateTime": slot["start_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                "endDateTime": slot["end_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                "staffId": slot["staff_id"],
                "notes": "",
                "sessionTypeId": session_type_id,
                "resourceId": None,
                "cost": slot["cost"],
            }
        ],
        "addOns": [],
        "multiSportSimRental": False,
    }

    response = requests.post(
        f"{BASE_URL}/appointments/book/{LOCATION_ID}",
        json=payload,
        headers={"Authorization": f"Bearer {FIVE_IRON_AUTH_TOKEN}", "Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    bookings = response.json()
    if not isinstance(bookings, list) or not any(b.get("status") == "Booked" for b in bookings):
        raise RuntimeError(f"Unexpected booking response: {response.text[:200]}")
    return bookings[0]


def _slots_for_duration(slots: list, duration_hours: float) -> list:
    return sorted(
        [s for s in slots if abs(s["duration_hours"] - duration_hours) < 0.01],
        key=lambda s: s["start_time"],
    )


def find_session(slots: list, duration_hours: float, time_str: str = None) -> list:
    """
    Pick slot(s) that satisfy the requested session.
    Returns a list of (slot, session_type_id) tuples — one entry for 0.5/1.0,
    two entries for 1.5/2.0. Empty list means no valid combination is available.

    For multi-slot durations, sub-sessions must be time-consecutive; bays may differ.
    time_str pins only the FIRST sub-session's start.
    """
    def matches_time(s):
        if not time_str:
            return True
        h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        return s["start_time"].hour == h and s["start_time"].minute == m

    if duration_hours == 0.5:
        for s in _slots_for_duration(slots, 0.5):
            if matches_time(s):
                return [(s, _SESSION_TYPE_30MIN)]
        return []

    if duration_hours == 1.0:
        for s in _slots_for_duration(slots, 1.0):
            if matches_time(s):
                return [(s, _SESSION_TYPE_60MIN)]
        return []

    if duration_hours == 1.5:
        one_hr = _slots_for_duration(slots, 1.0)
        half_hr = _slots_for_duration(slots, 0.5)
        for first in one_hr:
            if not matches_time(first):
                continue
            for second in half_hr:
                if second["start_time"] == first["end_time"]:
                    return [(first, _SESSION_TYPE_60MIN), (second, _SESSION_TYPE_30MIN)]
        return []

    if duration_hours == 2.0:
        one_hr = _slots_for_duration(slots, 1.0)
        for first in one_hr:
            if not matches_time(first):
                continue
            for second in one_hr:
                if second["start_time"] == first["end_time"]:
                    return [(first, _SESSION_TYPE_60MIN), (second, _SESSION_TYPE_60MIN)]
        return []

    return []


def attempt_booking(date_str: str, duration_hours: float = 1.0, time_str: str = None) -> list:
    """
    Find available slot(s) matching the request and book them.

    time_str: optional "HH:MM" (24hr) for the first sub-session's start.
              Omit to take the earliest available post-9pm slot.
    For 1.5hr / 2hr, sub-sessions must be time-consecutive (any bay).
    Returns a list of booking confirmation dicts. Empty list means nothing booked.
    """
    slots = check_availability(date_str)
    if not slots:
        return []

    matched = find_session(slots, duration_hours, time_str)
    if not matched:
        if time_str:
            print(f"[Error] No matching {duration_hours}hr session at {time_str} on {date_str}")
        return []

    return [_post_booking(slot, type_id) for slot, type_id in matched]
