"""
One-time setup: obtain a Google OAuth2 refresh token for Calendar access.

Run this locally once:
    python setup_gcal.py

It will open a browser for you to approve access, then print the refresh token.
Copy it into your .env as GOOGLE_REFRESH_TOKEN, and into GitHub Secrets.

Prerequisites:
  1. Go to https://console.cloud.google.com
  2. Create a project (or use an existing one)
  3. Enable the Google Calendar API
  4. Go to APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
     - Application type: Desktop app
  5. Download the credentials and set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env
"""

import os
import webbrowser
import urllib.parse
import http.server
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/calendar.events"

_auth_code = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")

    def log_message(self, *args):
        pass


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env first.")
        return

    # Start local callback server
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    # Build auth URL and open browser
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        })
    )
    print("Opening browser for Google authorization...")
    webbrowser.open(auth_url)
    thread.join(timeout=120)

    if not _auth_code:
        print("Error: No authorization code received.")
        return

    # Exchange code for tokens
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": _auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        print("Error: No refresh token returned. Make sure you set prompt=consent.")
        return

    print("\n=== Success ===")
    print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
    print("\nAdd this to your .env and GitHub Secrets (Settings -> Secrets -> Actions).")


if __name__ == "__main__":
    main()
