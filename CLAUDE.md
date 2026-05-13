# CLAUDE.md

## General Rules

- **Always update README.md** when making any change that affects features, configuration, environment variables, workflows, scheduling, or usage. Do not wait to be asked.
- **Always update this CLAUDE.md** when making changes that affect the scheduling architecture, booking flow, or key file inventory.

## Project Overview

Python automation for booking Five Iron Golf happy hour simulator slots. Runs entirely in the cloud — no local machine needed after setup. The booking job is triggered by a Cloudflare Worker cron (more reliable than GHA's native scheduler) which fires a GitHub `repository_dispatch` event; GitHub Actions does the actual Python work. A GHA `schedule:` cron at the same time remains as a backup.

## Key Files

| File | Purpose |
|---|---|
| `scheduler.py` | Main nightly runner — gets token, waits for midnight, books |
| `book.py` | Booking logic: pricing endpoint → book endpoint |
| `token_refresh.py` | Magic link flow + Gmail IMAP polling for session token |
| `availability.py` | Fetches available happy hour slots from Five Iron API |
| `cancellation_poller.py` | Hourly job that watches polling targets; auto-books via `book_target` when a matching slot opens (email fallback if token refresh fails) |
| `gcal.py` | Google Calendar event creation after successful booking |
| `setup_gcal.py` | One-time local script to obtain Google OAuth2 refresh token |
| `monday_prompt.py` | Weekly Monday email summarizing upcoming booking nights |
| `targets.json` | Dates to book — edited directly or via GitHub UI |
| `validate_targets.py` | Schema/business-rule linter for `targets.json` (run in CI on every push) |
| `config.py` | Env var loading + `is_happy_hour()` |
| `notifier.py` | Email notifications via Gmail SMTP |
| `cf-trigger/` | Cloudflare Worker that fires `repository_dispatch` on cron — primary trigger for `midnight-booker.yml` |

## Booking Flow

1. `POST /auth/login` → magic link email → Gmail IMAP poll → `GET /auth/verify` → session token
2. `POST /appointments/pricing` with `staffIds` → returns real `sessionTypeId: 252` + price
3. `POST /appointments/book/{locationId}` using pricing result → confirmed booking

**Never hardcode `sessionTypeId`** — always resolve it via the pricing endpoint.

## Happy Hour Schedule

- Sun–Thu: 9pm+ (`hour >= 21`)
- Fri–Sat: 10pm+ (`hour >= 22`)

## Scheduling

- **Cloudflare Worker** (primary): fires at `0 3 * * *` (03:00 UTC = 11pm EDT / 10pm EST) and POSTs `repository_dispatch` with `event_type: midnight-booker` to GitHub.
- **GHA `schedule:` cron** (backup): same `0 3 * * *` slot, kept in case the CF Worker fails. Remove once the CF path has proven reliable over several weeks.
- **Workflow `timeout-minutes: 150`** — accommodates EST winter case where the workflow fires at 10pm EST and sleeps ~2hr until midnight.
- **The 60-min buffer is deliberate.** GHA `schedule:` runs are routinely delayed 25–55min on small repos and occasionally dropped entirely; the CF Worker is reliable to within a minute. The workflow script grabs an auth token immediately on fire (~2min), then sleeps until exactly midnight ET before calling the book endpoint.
- **Booking semantics (`scheduler.py`)**:
  - Targets exactly 15 days out: wait until midnight, then book
  - Targets 1–14 days out (already open): book immediately, no midnight wait
  - Failed bookings: written back to `targets.json` with `"status": "polling"` for the hourly cancellation poller

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `midnight-booker.yml` | `repository_dispatch` (from CF Worker) + `schedule` (backup) + `workflow_dispatch` | Nightly booking attempt |
| `cancellation-poller.yml` | `schedule` hourly | Watches polling targets; auto-books matching slots (calls into `book_target` from scheduler) with manual-action email fallback if token refresh fails |
| `monday-prompt.yml` | `schedule` Monday 9am ET | Weekly email reminder to confirm targets |
| `validate-targets.yml` | Push/PR touching `targets.json` | Lints schema + happy-hour rules; blocks merge on failure |
