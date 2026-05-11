# Five Iron Scraper

Five Iron Golf offers a special rate of **$29/hour** on weekday simulator sessions after 9pm — significantly cheaper than the standard $75/hour daytime rate. The catch: bookings open exactly 2 weeks in advance at midnight ET, and these slots get snapped up almost instantly due to the price.

This tool automates the entire process. It watches your target dates, fires at midnight the moment bookings open, and grabs your slot before anyone else can.

## Features

- **Availability notifier** (`main.py`) — polls on demand and emails when slots open
- **Auto-booker** — reserves slots at exactly midnight ET when Five Iron releases them 2 weeks out
- **Weekly prompt** — emails you every Monday asking which dates to target; you edit one JSON file to confirm
- **Morning reminder** — emails you at 9am on booking days with token status and fix instructions if expired

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
| `FIVE_IRON_AUTH_TOKEN` | Bearer token captured from the Five Iron app (see below) |
| `FIVE_IRON_EMAIL` | Your Five Iron account email |
| `FIVE_IRON_SESSION_TYPE_ID` | `44` for 1-hour sessions, `45` for 30-min (default: 44) |
| `FIVE_IRON_PROMO_CODE` | Promo code for the after-9pm special (default: `five`) |

### Capturing your auth token

Five Iron uses passwordless login (Google OAuth or magic link), so we capture the session token once and reuse it. Tokens last ~24 hours.

1. Go to [fiveirongolf.com](https://fiveirongolf.com) and open DevTools (F12) → **Network** tab
2. Log in and browse available times
3. Click any request to `api.booking.fiveirongolf.com` → **Headers** → **Request Headers**
4. Copy the `Authorization` value — it looks like `Bearer eyJ...`
5. Save just the token part (after `Bearer `) as `FIVE_IRON_AUTH_TOKEN` in `.env` and in your GitHub secret

When the token expires, repeat these steps and update both places.

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
# Validates targets.json, checks if any target opens tonight at midnight ET
# If yes: validates token, waits until midnight, retries booking for up to 5 min per session
# Emails you on success (with booking ID and times) or failure
```

## GitHub Actions (automated, no PC required)

Scheduling runs entirely in the cloud — your PC can be off.

### Setup

1. Push this repo to GitHub (private recommended)
2. Go to **Settings → Secrets and variables → Actions** and add all variables from `.env` as repository secrets
3. Enable Actions on the repo

### How it works

| Workflow | Schedule | What it does |
|---|---|---|
| `monday-prompt.yml` | Every Monday ~9am ET | Emails a summary of upcoming booking nights for the next 2 weeks with a link to edit `targets.json` |
| `morning-reminder.yml` | Daily ~9am ET | On booking days: emails token status and fix instructions if expired |
| `midnight-booker.yml` | Nightly ~11:25pm ET | Validates targets, books at midnight, emails confirmation with booking details |
| `cancellation-poller.yml` | Hourly | On polling targets: checks for cancellations and emails when your exact requested session opens |

After receiving the Monday email, click the link, edit `targets.json` in the GitHub UI, and commit. The nightly job picks it up automatically.
