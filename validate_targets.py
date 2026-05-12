"""
Standalone linter for targets.json — safe to run in CI with no secrets/env vars.
Exits 0 if valid, 1 if any errors are found.
"""

import json
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

TARGETS_FILE = "targets.json"
LOCAL_TZ = ZoneInfo("America/New_York")
VALID_DURATIONS = {0.5, 1.0, 1.5, 2.0}
KNOWN_FIELDS = {"date", "time", "duration_hours", "status"}
VALID_STATUSES = {"polling"}
# Five Iron typically opens bookings ~14 days in advance; warn if target is suspiciously far out.
MAX_DAYS_OUT = 60


def is_happy_hour(dt: date, hour: int) -> bool:
    # weekday(): 0=Mon … 4=Fri, 5=Sat, 6=Sun
    if dt.weekday() in (4, 5):  # Fri, Sat
        return hour >= 22
    return hour >= 21  # Sun–Thu


def validate(data: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). errors are blocking; warnings are advisory."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict) or "targets" not in data:
        errors.append("targets.json must be a JSON object with a top-level 'targets' array")
        return errors, warnings

    targets = data["targets"]
    if not isinstance(targets, list):
        errors.append("'targets' must be an array")
        return errors, warnings

    today_et = datetime.now(LOCAL_TZ).date()
    seen_dates: dict[str, int] = {}

    for i, t in enumerate(targets):
        prefix = f"Target {i + 1}"

        if not isinstance(t, dict):
            errors.append(f"{prefix}: must be a JSON object")
            continue

        unknown = set(t.keys()) - KNOWN_FIELDS
        if unknown:
            warnings.append(f"{prefix}: unknown field(s): {', '.join(sorted(unknown))}")

        # --- date ---
        date_str = t.get("date")
        parsed_date: date | None = None
        if not date_str:
            errors.append(f"{prefix}: missing required field 'date'")
        else:
            try:
                parsed_date = date.fromisoformat(date_str)
            except ValueError:
                errors.append(f"{prefix}: invalid date '{date_str}' — expected YYYY-MM-DD")
            else:
                if parsed_date <= today_et:
                    errors.append(f"{prefix}: date {date_str} is today or in the past")
                elif (parsed_date - today_et).days > MAX_DAYS_OUT:
                    warnings.append(
                        f"{prefix}: date {date_str} is {(parsed_date - today_et).days} days out "
                        f"(>{MAX_DAYS_OUT}) — Five Iron may not have slots open yet"
                    )
                if date_str in seen_dates:
                    errors.append(
                        f"{prefix}: duplicate date {date_str} (also appears at target {seen_dates[date_str]})"
                    )
                else:
                    seen_dates[date_str] = i + 1

        # --- duration_hours ---
        dur = t.get("duration_hours")
        if dur is None:
            errors.append(f"{prefix}: missing required field 'duration_hours'")
        elif dur not in VALID_DURATIONS:
            errors.append(
                f"{prefix}: duration_hours must be one of {sorted(VALID_DURATIONS)} (got {dur!r})"
            )

        # --- time ---
        time_str = t.get("time")
        parsed_hour: int | None = None
        if time_str is None:
            warnings.append(f"{prefix}: no 'time' set — will book first available post-9pm slot")
        else:
            try:
                parts = time_str.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and m in (0, 30)):
                    raise ValueError
                parsed_hour = h
            except (ValueError, AttributeError):
                errors.append(
                    f"{prefix}: time '{time_str}' must be HH:MM in 30-min increments "
                    "(e.g. '21:00', '21:30', '22:00')"
                )

        # --- happy hour check (requires both a valid date and a valid time) ---
        if parsed_date is not None and parsed_hour is not None:
            if not is_happy_hour(parsed_date, parsed_hour):
                day_name = parsed_date.strftime("%A")
                threshold = 22 if parsed_date.weekday() in (4, 5) else 21
                errors.append(
                    f"{prefix}: {time_str} on {day_name} {date_str} is not happy hour "
                    f"(must be {threshold:02d}:00 or later on {day_name})"
                )

        # --- status ---
        status = t.get("status")
        if status is not None and status not in VALID_STATUSES:
            errors.append(
                f"{prefix}: invalid status '{status}' — expected one of {sorted(VALID_STATUSES)}"
            )

    return errors, warnings


def main() -> int:
    try:
        with open(TARGETS_FILE) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {TARGETS_FILE} not found")
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: {TARGETS_FILE} is not valid JSON: {e}")
        return 1

    errors, warnings = validate(data)

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\n{len(errors)} error(s) found — fix before pushing.")
        return 1

    target_count = len(data.get("targets", []))
    print(f"OK: {target_count} target(s) valid" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
