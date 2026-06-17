# Five Iron Scraper

Five Iron Golf offers a special **$29/hour** simulator rate during "5i After Dark" — Sun–Thu after 9pm and Fri–Sat after 10pm — significantly cheaper than the standard $75–90/hour daytime rate. The catch: bookings open exactly 2 weeks in advance at midnight ET, and these slots get snapped up almost instantly due to the price.

This tool automates the entire process. It watches your target dates, fires at midnight the moment bookings open, and grabs your slot before anyone else can.

## Features

- **Availability notifier** (`main.py`) — polls on demand and emails when slots open
- **Auto-booker** — books at midnight ET when Five Iron releases slots 2 weeks out; also books immediately if you add a date that's already within the 2-week window
- **Weekly prompt** — emails you every Monday with upcoming booking nights; edit one JSON file to confirm
- **Cancellation poller** — if midnight booking fails, watches hourly for cancellations and emails when your slot opens
- **Google Calendar** — optionally creates an event on any calendar (including shared) after each successful booking

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your .env values (see below)
```

## Configuration

| Variable | Description |
|---|---|
| `SENDER_EMAIL` | Gmail address to send notifications from |
| `SENDER_PASSWORD` | Gmail [App Password](https://myaccount.google.com/apppasswords) (not your regular password) |
| `RECIPIENT_EMAIL` | Email address to receive notifications |
| `LOCATION_ID` | Your Five Iron location ID (see below) |
| `PARTY_SIZE` | Number of people (default: 2) |
| `FIVE_IRON_EMAIL` | Your Five Iron account email |
| `GOOGLE_CLIENT_ID` | (Optional) Google OAuth2 client ID — for calendar events |
| `GOOGLE_CLIENT_SECRET` | (Optional) Google OAuth2 client secret |
| `GOOGLE_REFRESH_TOKEN` | (Optional) Obtained once via `python setup_gcal.py` |
| `GOOGLE_CALENDAR_ID` | (Optional) Target calendar ID (default: `primary`) |
| `GOOGLE_EVENT_COLOR` | (Optional) Event color (default: `tangerine`) |

### How booking works

The bot authenticates fresh before every booking run — no stored token needed:

1. `POST /auth/login` → triggers a magic link email to your Five Iron account
2. Gmail IMAP polls for the link (up to 120 seconds) → `GET /auth/verify` → session token
3. `POST /appointments/pricing` — gets the correct session type and confirmed price for the slot
4. `POST /appointments/book/{locationId}` — places the booking using the pricing result

Happy hour pricing (`$29/hr`) is resolved automatically in step 3 — no promo code needed.

### Google Calendar (optional)

After each successful booking the bot can automatically create a calendar event. To enable it:

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project → enable the **Google Calendar API**
2. **APIs & Services → Credentials → Create Credentials → OAuth client ID** — choose **Desktop app**
3. Add the client ID and secret to `.env`
4. Add yourself as a test user: **OAuth consent screen → Test users → Add users**
5. **Publish your OAuth app** (important, see caveat below): **APIs & Services → OAuth consent screen → Audience → Publish app**. No verification is required for personal use with the calendar scope.
6. Run `python setup_gcal.py` — it opens a browser, you approve, it prints your `GOOGLE_REFRESH_TOKEN`
7. Find your calendar ID: Google Calendar → gear → Settings → click your calendar → **Integrate calendar → Calendar ID**

> **Caveat: refresh tokens expire after 7 days in "Testing" mode.** If you skip step 5 and leave the OAuth app in Testing status, Google silently invalidates your refresh token every 7 days, and `gcal.py` will fail with `400 Bad Request` at the token endpoint on the next booking. Publishing the app to "In production" removes this limit (tokens then only expire if unused for 6 months, manually revoked, or after a password change). If your existing token has already expired, re-run `setup_gcal.py` after publishing to mint a fresh one and update the GitHub `GOOGLE_REFRESH_TOKEN` secret.

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth2 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth2 client secret |
| `GOOGLE_REFRESH_TOKEN` | Obtained once via `python setup_gcal.py` |
| `GOOGLE_CALENDAR_ID` | Target calendar ID (default: `primary`). Use the `@group.calendar.google.com` ID for shared calendars |
| `GOOGLE_EVENT_COLOR` | Event color: `tomato`, `flamingo`, `tangerine`, `banana`, `sage`, `basil`, `peacock`, `blueberry`, `lavender`, `grape`, `graphite` (default: `tangerine`) |

If `GOOGLE_REFRESH_TOKEN` is not set, calendar integration is silently skipped.

### Finding your Location ID

1. Go to [fiveirongolf.com](https://fiveirongolf.com) and start the booking flow for your location
2. Open Chrome DevTools (F12) → **Network** tab → filter by `api.booking.fiveirongolf.com`
3. The `locationId` query parameter in any availability request is your location ID

## targets.json

Pre-populate this file with all the dates you want to book — you can set the whole year at once. The nightly scheduler checks each night whether any target is exactly 14 days out, and if so, books it at midnight.

```json
{
  "targets": [
    {"date": "2026-06-03", "time": "21:00", "duration_hours": 1},
    {"date": "2026-06-10", "time": "21:00", "duration_hours": 1.5},
    {"date": "2026-06-17", "time": "21:00", "duration_hours": 2}
  ]
}
```

`time` is optional — omit it to book the first available post-9pm slot.

| Field | Values | Description |
|---|---|---|
| `date` | `YYYY-MM-DD` | The date you want to play |
| `time` | `HH:MM` 24hr (optional) | Exact start time. Omit to take the first available post-9pm slot |
| `duration_hours` | `0.5`, `1`, `1.5`, `2` | Session length. `1.5` = one 1-hr + one consecutive 0.5-hr; `2` = two consecutive 1-hr. For multi-slot durations, sub-sessions may land on different bays. |

Multiple entries for the same date book multiple sessions that night. After each successful booking, the date is removed from the file automatically.

## Usage

### Manual availability check

```bash
python main.py
# Enter a date (YYYY-MM-DD) — polls every 30 min and emails when post-9pm slots open
```

### Add dates interactively

```bash
python monday_prompt.py
# Enter dates (YYYY-MM-DD) and durations to append to targets.json
# Or just edit targets.json directly — pre-populate the whole year at once
```

### Nightly scheduler

```bash
python scheduler.py
# Validates targets.json
# Already-open targets (within 2-week window): books immediately
# Tonight's target (exactly 14 days out): waits until midnight, then books
# On failure: moves target to polling; emails you either way
```

## GitHub Actions (automated, no PC required)

Scheduling runs entirely in the cloud — your PC can be off.

### Setup

1. Push this repo to GitHub (private recommended)
2. Go to **Settings → Secrets and variables → Actions** and add all variables from `.env` as repository secrets (Google Calendar secrets are optional)
3. Enable Actions on the repo

### How it works

| Workflow | Schedule | What it does |
|---|---|---|
| `monday-prompt.yml` | Every Monday ~9am ET | Emails a summary of upcoming booking nights for the next 2 weeks with a link to edit `targets.json` |
| `midnight-booker.yml` | Nightly 11:00pm ET (Cloudflare Worker `repository_dispatch`; GHA `schedule` as backup) | Gets fresh session token, waits until midnight, books, emails confirmation with booking details |
| `cancellation-poller.yml` | Hourly | On polling targets: checks for cancellations and auto-books when your exact requested session opens (manual-action email fallback if token refresh fails) |
| `validate-targets.yml` | On push/PR to `targets.json` | Lints `targets.json` — blocks merge if dates are invalid, in the past, not during happy hour, or have duplicate entries |

### Cloudflare Worker trigger (recommended)

GitHub Actions `schedule:` cron is unreliable for time-critical jobs — runs are routinely delayed 25–55min and occasionally dropped entirely. The [`cf-trigger/`](./cf-trigger) directory contains a tiny Cloudflare Worker that fires `repository_dispatch` at 03:00 UTC daily as the primary trigger; the GHA `schedule` cron stays in place as a backup.

See [`cf-trigger/README.md`](./cf-trigger/README.md) for setup. TL;DR: create a fine-grained GitHub PAT (scoped to `actions: write` on this repo), set it as a Worker secret via `npx wrangler secret put GITHUB_TOKEN`, then `npx wrangler deploy` from inside `cf-trigger/`.

### Linting targets.json locally

```bash
python validate_targets.py
```

Exits 0 (OK) or 1 (errors found). Run this before pushing a `targets.json` edit to catch mistakes early. Checks:

- Valid JSON and schema (`targets` array present)
- Dates are `YYYY-MM-DD` and in the future
- `duration_hours` is one of `0.5`, `1`, `1.5`, `2`
- `time` (if set) is `HH:MM` in 30-minute increments
- Time is during happy hour for that day of week (Sun–Thu 21:00+, Fri–Sat 22:00+)
- No duplicate dates
- No unknown fields

After receiving the Monday email, click the link, edit `targets.json` in the GitHub UI, and commit. The nightly job picks it up automatically.
