import os
from datetime import datetime
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
FIVE_IRON_AUTH_TOKEN = os.getenv("FIVE_IRON_AUTH_TOKEN", "")
FIVE_IRON_EMAIL = os.getenv("FIVE_IRON_EMAIL", "")
FIVE_IRON_SESSION_TYPE_ID = int(os.getenv("FIVE_IRON_SESSION_TYPE_ID", "44"))  # 44=1hr, 45=30min
FIVE_IRON_PROMO_CODE = os.getenv("FIVE_IRON_PROMO_CODE", "")

LOCAL_TZ = ZoneInfo("America/New_York")
POLL_INTERVAL_SECONDS = 30 * 60


def is_happy_hour(dt: datetime) -> bool:
    """
    5i After Dark schedule: Sun–Thu 9pm–close, Fri–Sat 10pm–close.
    dt must be in ET (or naive ET).
    """
    # weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if dt.weekday() in (4, 5):   # Fri, Sat
        return dt.hour >= 22
    return dt.hour >= 21          # Sun–Thu
