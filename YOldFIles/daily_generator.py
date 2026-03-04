#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

import yaml

ALIASES = {
    "ctf": "CTF",
    "thm": "TryHackMe",
    "tcm": "TCM-Security",
    "htb": "HackTheBox",
    "cs": "General CS",
    "infosec": "General InfoSec",
}


def hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def ask_minutes(category: str) -> int:
    while True:
        raw = input(f"How many minutes for '{category}'? ").strip()
        try:
            minutes = int(raw)
        except ValueError:
            print("Please enter a valid whole number.")
            continue
        if minutes < 0:
            print("Minutes cannot be negative.")
            continue
        return minutes


def print_session_breaks(total_minutes: int, sessions_already_logged: int) -> int:
    total_sessions = total_minutes // 45
    new_sessions = total_sessions - sessions_already_logged
    if new_sessions <= 0:
        print("No new full 45m session reached yet.")
        return sessions_already_logged
    for i in range(new_sessions):
        session_no = sessions_already_logged + i + 1
        print(f"[NOTIFY] Session {session_no} logged (45m). Take a short break.")
    return total_sessions


def ask_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    day_minutes_total = 0
    sessions_logged = 0
    while True:
        raw_category = input("Enter a category (or type 'end'): ").strip()
        if not raw_category:
            print("Category cannot be empty.")
            continue
        if raw_category.lower() == "end":
            break

        category = ALIASES.get(raw_category.lower(), raw_category)
        if category.lower() == "book":
            book_name = input("Write the name of the book: ").strip()
            if not book_name:
                print("Book name cannot be empty.")
                continue
            category = f"Book ({book_name})"

        minutes = ask_minutes(category)
        day_minutes_total += minutes
        sessions_logged = print_session_breaks(day_minutes_total, sessions_logged)
        entries.append(
            {
                "category": category,
                "duration_minutes": minutes,
                "duration_hours": hm(minutes),
            }
        )
    return entries


def ask_int(label: str, default_value: int, min_value: int, max_value: int) -> int:
    while True:
        raw = input(f"Enter {label} [{default_value}]: ").strip()
        if not raw:
            return default_value
        try:
            value = int(raw)
        except ValueError:
            print(f"Invalid {label}. Please enter a number.")
            continue
        if value < min_value or value > max_value:
            print(f"{label.capitalize()} must be between {min_value} and {max_value}.")
            continue
        return value


def ask_log_date(default_date: date) -> date:
    while True:
        year = ask_int("year", default_date.year, 1970, 2100)
        month = ask_int("month", default_date.month, 1, 12)
        day = ask_int("day", default_date.day, 1, 31)
        try:
            return date(year, month, day)
        except ValueError:
            print("Invalid calendar date. Please try again.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive daily log generator. Prompts for category/minutes until 'end'."
    )
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y-%m-%d"),
        help="Date for the daily log in YYYY-MM-DD format (default: today).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    default_date = date.today()
    log_date = ask_log_date(default_date)

    try:
        cli_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("Invalid --date format. Use YYYY-MM-DD.")
        return 1
    if args.date != default_date.strftime("%Y-%m-%d"):
        log_date = cli_date

    print(f"Creating daily log for {log_date.strftime('%Y-%m-%d')}")
    entries = ask_entries()
    if not entries:
        print("No entries were added. Nothing written.")
        return 0

    day_total_minutes = sum(int(item["duration_minutes"]) for item in entries)
    payload = {
        "date": log_date.strftime("%Y-%m-%d"),
        "entries": entries,
        "day_total_minutes": day_total_minutes,
        "day_total_hours": hm(day_total_minutes),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    base = Path(__file__).resolve().parent
    daily_dir = base / "Daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    out_file = daily_dir / f"{log_date.strftime('%Y-%m-%d')}.yaml"
    out_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"Daily log written: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
