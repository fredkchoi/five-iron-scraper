"""
Google Calendar integration — creates an event after a successful booking.

Credentials are loaded from env vars (never hardcoded):
  GOOGLE_CLIENT_ID      — OAuth2 client ID from Google Cloud Console
  GOOGLE_CLIENT_SECRET  — OAuth2 client secret
  GOOGLE_REFRESH_TOKEN  — obtained once via setup_gcal.py
  GOOGLE_CALENDAR_ID    — target calendar (e.g. "primary" or shared calendar ID)
  GOOGLE_EVENT_COLOR    — optional color name (default: Basil)

Run setup_gcal.py once locally to obtain GOOGLE_REFRESH_TOKEN.
"""

import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_TZ = "America/New_York"

# Google Calendar color name -> colorId mapping
_COLOR_IDS = {
    "tomato": "11",
    "flamingo": "4",
    "tangerine": "6",
    "banana": "5",
    "sage": "2",
    "basil": "8",
    "peacock": "7",
    "blueberry": "9",
    "lavender": "1",
    "grape": "3",
    "graphite": "8",
}


def _get_access_token() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN must all be set")

    resp = requests.post(_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_booking_event(start_dt: datetime, end_dt: datetime, location_name: str = "Five Iron Golf - LIC") -> str:
    """
    Create a Google Calendar event for a confirmed Five Iron booking.
    Returns the created event URL, or '' on failure.

    start_dt / end_dt should be naive ET datetimes (as returned by the booking API).
    """
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    color_name = os.getenv("GOOGLE_EVENT_COLOR", "tangerine").lower()
    color_id = _COLOR_IDS.get(color_name, "8")

    # Attach ET timezone info
    tz = ZoneInfo(_TZ)
    start_et = start_dt.replace(tzinfo=tz)
    end_et = end_dt.replace(tzinfo=tz)

    event = {
        "summary": "Five Iron Golf 🏌️",
        "location": location_name,
        "colorId": color_id,
        "start": {"dateTime": start_et.isoformat(), "timeZone": _TZ},
        "end": {"dateTime": end_et.isoformat(), "timeZone": _TZ},
    }

    try:
        access_token = _get_access_token()
        resp = requests.post(
            _EVENTS_URL.format(calendar_id=calendar_id),
            json=event,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        event_url = resp.json().get("htmlLink", "")
        print(f"[gcal] Event created: {event_url}")
        return event_url
    except Exception as e:
        print(f"[gcal] Failed to create calendar event: {e}")
        return ""
