# CLAUDE.md

## General Rules

- **Always update README.md** when making any change that affects features, configuration, environment variables, workflows, scheduling, or usage. Do not wait to be asked.

## Project Overview

Python automation for booking Five Iron Golf happy hour simulator slots. Runs entirely via GitHub Actions — no local machine needed after setup.

## Key Files

| File | Purpose |
|---|---|
| `scheduler.py` | Main nightly runner — gets token, waits for midnight, books |
| `book.py` | Booking logic: pricing endpoint → book endpoint |
| `token_refresh.py` | Magic link flow + Gmail IMAP polling for session token |
| `availability.py` | Fetches available happy hour slots from Five Iron API |
| `gcal.py` | Google Calendar event creation after successful booking |
| `setup_gcal.py` | One-time local script to obtain Google OAuth2 refresh token |
| `targets.json` | Dates to book — edited directly or via GitHub UI |
| `config.py` | Env var loading + `is_happy_hour()` |
| `notifier.py` | Email notifications via Gmail SMTP |

## Booking Flow

1. `POST /auth/login` → magic link email → Gmail IMAP poll → `GET /auth/verify` → session token
2. `POST /appointments/pricing` with `staffIds` → returns real `sessionTypeId: 252` + price
3. `POST /appointments/book/{locationId}` using pricing result → confirmed booking

**Never hardcode `sessionTypeId`** — always resolve it via the pricing endpoint.

## Happy Hour Schedule

- Sun–Thu: 9pm+ (`hour >= 21`)
- Fri–Sat: 10pm+ (`hour >= 22`)

## Scheduling

- Cron fires at **11:55pm ET** nightly
- Targets exactly 15 days out: wait until midnight, then book
- Targets 1–14 days out (already open): book immediately, no midnight wait
- Failed bookings: written back to `targets.json` with `"status": "polling"` for the hourly cancellation poller
