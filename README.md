# Five Iron Scraper

Polls the Five Iron Golf booking API and sends an email notification when simulator slots become available after 9pm.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your .env values (see below)
python main.py
```

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `SENDER_EMAIL` | Gmail address to send notifications from |
| `SENDER_PASSWORD` | Gmail [App Password](https://myaccount.google.com/apppasswords) (not your regular password) |
| `RECIPIENT_EMAIL` | Email address to receive notifications |
| `LOCATION_ID` | Your Five Iron location ID (see below) |
| `PARTY_SIZE` | Number of people (default: 2) |

### Finding your Location ID

1. Go to [fiveirongolf.com](https://fiveirongolf.com) and start the booking flow for your location
2. Open Chrome DevTools (F12) → **Network** tab
3. Filter by `api.booking.fiveirongolf.com`
4. The `locationId` query parameter in any availability request is your location ID

## Usage

```bash
python main.py
# Enter a date in YYYY-MM-DD format when prompted
# The script polls every 30 minutes and emails you when post-9pm slots open
```
