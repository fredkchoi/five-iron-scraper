"""
Automated token refresh via Five Iron's magic link login + Gmail IMAP.

Triggers /auth/login to send a verification email, then polls Gmail inbox
for the JWT in the verify URL. No bookingUUID required — pure auth flow.
"""

import email as email_lib
import html
import imaplib
import re
import time
import urllib.parse
import requests

BASE_URL = "https://api.booking.fiveirongolf.com"
_VERIFY_URL_RE = re.compile(r"(https://booking\.fiveirongolf\.com/verify\?[^\s\"<]+)")
_POLL_INTERVAL = 5    # seconds between IMAP checks
_MAX_WAIT = 120       # seconds to wait for the email


def _request_magic_link(five_iron_email: str, location_id: str) -> bool:
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": five_iron_email, "locationId": location_id},
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[token_refresh] Magic link requested (HTTP {resp.status_code}).")
        return True
    except Exception as e:
        print(f"[token_refresh] /auth/login failed: {e}")
        return False


def _extract_body(msg) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    parts.append(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
                except Exception:
                    pass
        return "\n".join(parts)
    try:
        return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _poll_for_verify_url(gmail_user: str, gmail_password: str, deadline: float) -> str:
    """Poll Gmail until the Five Iron verify email arrives. Returns the full verify URL or ''."""
    while time.time() < deadline:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
                imap.login(gmail_user, gmail_password)
                imap.select("INBOX")
                _, data = imap.search(None, 'UNSEEN SUBJECT "Account Verification"')
                for mid in (data[0].split() if data[0] else []):
                    _, msg_data = imap.fetch(mid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw)
                    body = _extract_body(msg)
                    match = _VERIFY_URL_RE.search(body)
                    if match:
                        imap.store(mid, "+FLAGS", "\\Seen")
                        return match.group(1).rstrip(".")
        except Exception as e:
            print(f"[token_refresh] IMAP error: {e}")
        time.sleep(_POLL_INTERVAL)
    return ""


def _exchange_verify_url(verify_url: str):
    """
    Exchange a magic link verify URL for a session token.
    Returns (access_token, refresh_token) — refresh_token may be ''.
    """
    parsed = urllib.parse.urlparse(html.unescape(verify_url))
    params = urllib.parse.parse_qs(parsed.query)
    magic_token = params.get("token", [""])[0]
    email = params.get("email", [""])[0]

    booking = params.get("booking", [""])[0]
    verify_params = {"token": magic_token, "email": email, "redirectTo": ""}
    if booking:
        verify_params["booking"] = booking

    try:
        resp = requests.get(
            f"{BASE_URL}/auth/verify",
            params=verify_params,
            timeout=15,
        )
        print(f"[token_refresh] GET /auth/verify HTTP {resp.status_code}")
        if resp.ok:
            data = resp.json()
            access = data.get("accessToken", "")
            refresh = data.get("refreshToken", "")
            if access:
                return access, refresh
    except Exception as e:
        print(f"[token_refresh] /auth/verify failed: {e!r}")

    return "", ""


def refresh_access_token(refresh_token: str) -> str:
    """
    Use a stored refresh token to get a new access token without a magic link.
    Returns the new access token, or '' on failure.
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"refreshToken": refresh_token},
            timeout=15,
        )
        print(f"[token_refresh] POST /auth/refresh HTTP {resp.status_code}")
        if resp.ok:
            data = resp.json()
            return data.get("accessToken", "")
    except Exception as e:
        print(f"[token_refresh] /auth/refresh failed: {e!r}")
    return ""


def fetch_fresh_token(five_iron_email: str, location_id: str, gmail_user: str, gmail_password: str):
    """
    Trigger Five Iron's magic link login, extract the verify URL from Gmail,
    and exchange it for (access_token, refresh_token).
    Returns ('', '') on failure.
    """
    if not _request_magic_link(five_iron_email, location_id):
        return "", ""
    print(f"[token_refresh] Polling Gmail for up to {_MAX_WAIT}s...")
    verify_url = _poll_for_verify_url(gmail_user, gmail_password, time.time() + _MAX_WAIT)
    if not verify_url:
        print("[token_refresh] Timed out — no verify email received.")
        return "", ""
    print("[token_refresh] Verify URL found — exchanging for session token...")
    access, refresh = _exchange_verify_url(verify_url)
    if access:
        print("[token_refresh] Fresh token obtained.")
    else:
        print("[token_refresh] Token exchange failed.")
    return access, refresh
