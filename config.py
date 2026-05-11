import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Missing required env var: {key}")
    return val


SENDER_EMAIL = _require("SENDER_EMAIL")
SENDER_PASSWORD = _require("SENDER_PASSWORD")
RECIPIENT_EMAIL = _require("RECIPIENT_EMAIL")
LOCATION_ID = _require("LOCATION_ID")
PARTY_SIZE = int(os.getenv("PARTY_SIZE", "2"))

LOCAL_TZ = ZoneInfo("America/New_York")
POLL_INTERVAL_SECONDS = 30 * 60
