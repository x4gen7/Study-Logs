#!/usr/bin/env python3

from __future__ import annotations

import argparse
import curses
from datetime import date, datetime
from pathlib import Path

import yaml

DEFAULT_CATEGORIES = [
    "TryHackMe",
    "HackTheBox",
    "CTF",
    "TCM-Security",
    "General CS",
    "General InfoSec",
]


def hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def put(stdscr: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    clipped = text[: max(0, w - x - 1)]
    if not clipped:
        return
    try:
        stdscr.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def draw_box(
    stdscr: curses.window,
    top: int,
    left: int,
    height: int,
    width: int,
    title: str = "",
    attr: int = 0,
) -> None:
    if height < 3 or width < 4:
        return
    try:
        win = stdscr.derwin(height, width, top, left)
        win.attrset(attr)
        win.box()
        if title:
            label = f" {title} "
            put(win, 0, 2, label, attr | curses.A_BOLD)
        win.noutrefresh()
    except curses.error:
        return


def init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)     # title
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # selected
    curses.init_pair(3, curses.COLOR_YELLOW, -1)   # footer/info
    curses.init_pair(4, curses.COLOR_GREEN, -1)    # positive/status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TUI daily log generator. Saves YAML logs in Daily/<date>.yaml."
    )
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y-%m-%d"),
        help="Initial date in YYYY-MM-DD format (default: today).",
    )
    return parser.parse_args()


def menu(stdscr: curses.window, title: str, options: list[str], footer: str = "") -> int:
    idx = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        title_attr = curses.color_pair(1) | curses.A_BOLD
        select_attr = curses.color_pair(2) | curses.A_BOLD
        footer_attr = curses.color_pair(3) | curses.A_BOLD

        box_top = 1
        box_left = 2
        box_h = max(7, h - 4)
        box_w = max(20, w - 4)
        draw_box(stdscr, box_top, box_left, box_h, box_w, title, curses.color_pair(1))

        if footer:
            put(stdscr, box_top + 2, box_left + 2, footer, footer_attr)

        start_y = box_top + 4
        for i, opt in enumerate(options):
            row = start_y + i
            if row >= box_top + box_h - 3:
                break
            attr = select_attr if i == idx else curses.A_NORMAL
            prefix = " > " if i == idx else "   "
            put(stdscr, row, box_left + 2, f"{prefix}{opt}", attr)

        hint = "Up/Down (or j/k): move  Enter: select  q: back"
        put(stdscr, box_top + box_h - 2, box_left + 2, hint, footer_attr)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(options)
        elif key in (10, 13, curses.KEY_ENTER):
            return idx
        elif key in (ord("q"), 27):
            return -1


def prompt_text(
    stdscr: curses.window,
    title: str,
    prompt: str,
    default: str = "",
) -> str | None:
    curses.echo()
    try:
        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            title_attr = curses.color_pair(1) | curses.A_BOLD
            footer_attr = curses.color_pair(3) | curses.A_BOLD
            draw_box(stdscr, 1, 2, max(9, h - 4), max(20, w - 4), title, curses.color_pair(1))
            put(stdscr, 4, 4, prompt, curses.A_BOLD)
            if default:
                put(stdscr, 5, 4, f"Default: {default}", footer_attr)
            put(stdscr, h - 3, 4, "Enter value (empty = default, q = cancel)", footer_attr)
            put(stdscr, 7, 4, "> ", title_attr)
            stdscr.move(7, 6)
            stdscr.clrtoeol()
            stdscr.refresh()

            raw = stdscr.getstr(7, 6, max(1, w - 8)).decode("utf-8", errors="ignore").strip()
            if raw.lower() == "q":
                return None
            if not raw:
                return default
            return raw
    finally:
        curses.noecho()


def show_message(stdscr: curses.window, title: str, lines: list[str]) -> None:
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    title_attr = curses.color_pair(1) | curses.A_BOLD
    footer_attr = curses.color_pair(3) | curses.A_BOLD
    draw_box(stdscr, 1, 2, max(8, h - 4), max(20, w - 4), title, curses.color_pair(1))
    for i, line in enumerate(lines):
        y = 4 + i
        if y >= h - 3:
            break
        put(stdscr, y, 4, line, title_attr if line.startswith("[NOTIFY]") else curses.A_NORMAL)
    put(stdscr, h - 3, 4, "Press any key to continue", footer_attr)
    stdscr.refresh()
    stdscr.getch()


def choose_date(stdscr: curses.window, current: date) -> date:
    while True:
        year_raw = prompt_text(stdscr, "Set Log Date", "Enter year:", str(current.year))
        if year_raw is None:
            return current
        month_raw = prompt_text(stdscr, "Set Log Date", "Enter month:", str(current.month))
        if month_raw is None:
            return current
        day_raw = prompt_text(stdscr, "Set Log Date", "Enter day:", str(current.day))
        if day_raw is None:
            return current

        try:
            year = int(year_raw)
            month = int(month_raw)
            day = int(day_raw)
        except ValueError:
            show_message(stdscr, "Invalid Date", ["Year, month, and day must be numbers."])
            continue

        try:
            return date(year, month, day)
        except ValueError:
            show_message(stdscr, "Invalid Date", ["Please enter a valid calendar date."])


def prompt_minutes(stdscr: curses.window, category: str) -> int | None:
    while True:
        raw = prompt_text(stdscr, "Duration", f"Minutes for '{category}':", "45")
        if raw is None:
            return None
        try:
            minutes = int(raw)
        except ValueError:
            show_message(stdscr, "Invalid Input", ["Please enter a whole number."])
            continue
        if minutes < 0:
            show_message(stdscr, "Invalid Input", ["Minutes cannot be negative."])
            continue
        return minutes


def choose_category(
    stdscr: curses.window,
    categories: list[str],
) -> str | None:
    while True:
        options = [*categories, "Custom category", "Back"]
        idx = menu(stdscr, "Choose Category", options, "Select category or create your own")
        if idx == -1 or idx == len(options) - 1:
            return None

        selected = options[idx]
        if idx < len(categories):
            return selected

        if selected == "Custom category":
            raw = prompt_text(stdscr, "Custom Category", "Category name:")
            if raw is None:
                continue
            category = raw.strip()
            if not category:
                show_message(stdscr, "Invalid Category", ["Category cannot be empty."])
                continue
            return category


def review_entries(stdscr: curses.window, entries: list[dict[str, object]]) -> None:
    if not entries:
        show_message(stdscr, "Entries", ["No entries yet."])
        return

    lines = [
        f"{i + 1}. {entry['category']} - {entry['duration_minutes']}m ({entry['duration_hours']})"
        for i, entry in enumerate(entries)
    ]
    total = sum(int(item["duration_minutes"]) for item in entries)
    sessions = total // 45
    remaining = 45 - (total % 45) if total % 45 != 0 else 0
    lines.append("")
    lines.append(f"Total: {total}m ({hm(total)})")
    lines.append(f"45m sessions reached: {sessions}")
    if remaining == 0:
        lines.append("Next 45m session: reached")
    else:
        lines.append(f"Minutes to next 45m session: {remaining}m")
    show_message(stdscr, "Current Entries", lines)


def run_tui(
    stdscr: curses.window,
    initial_date: date,
    categories: list[str],
) -> tuple[date, list[dict[str, object]], bool]:
    curses.curs_set(0)
    init_colors()
    entries: list[dict[str, object]] = []
    log_date = initial_date
    sessions_logged = 0

    while True:
        day_total = sum(int(item["duration_minutes"]) for item in entries)
        options = [
            f"Set log date ({log_date.strftime('%Y-%m-%d')})",
            "Add entry",
            f"Review entries ({len(entries)})",
            "Save log and exit",
            "Exit without saving",
        ]
        footer = f"Total today: {day_total}m ({hm(day_total)})"
        choice = menu(stdscr, "Daily Log TUI", options, footer)

        if choice in (-1, 4):
            return log_date, entries, False

        if choice == 0:
            log_date = choose_date(stdscr, log_date)
            continue

        if choice == 1:
            category = choose_category(stdscr, categories)
            if category is None:
                continue
            minutes = prompt_minutes(stdscr, category)
            if minutes is None:
                continue

            entries.append(
                {
                    "category": category,
                    "duration_minutes": minutes,
                    "duration_hours": hm(minutes),
                }
            )

            day_total = sum(int(item["duration_minutes"]) for item in entries)
            total_sessions = day_total // 45
            new_sessions = total_sessions - sessions_logged
            sessions_logged = total_sessions

            lines = [f"Added: {category} - {minutes}m"]
            if new_sessions > 0:
                for i in range(new_sessions):
                    lines.append(
                        f"[NOTIFY] Session {sessions_logged - new_sessions + i + 1} logged (45m)."
                    )
            else:
                lines.append("No new full 45m session reached yet.")
            show_message(stdscr, "Entry Added", lines)
            continue

        if choice == 2:
            review_entries(stdscr, entries)
            continue

        if choice == 3:
            if not entries:
                show_message(stdscr, "Nothing to Save", ["Add at least one entry first."])
                continue
            return log_date, entries, True


def main() -> int:
    args = parse_args()
    try:
        cli_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("Invalid --date format. Use YYYY-MM-DD.")
        return 1

    base = Path(__file__).resolve().parent
    log_date, entries, should_save = curses.wrapper(run_tui, cli_date, DEFAULT_CATEGORIES)
    if not should_save:
        print("Exited without saving.")
        return 0

    day_total_minutes = sum(int(item["duration_minutes"]) for item in entries)
    payload = {
        "date": log_date.strftime("%Y-%m-%d"),
        "entries": entries,
        "day_total_minutes": day_total_minutes,
        "day_total_hours": hm(day_total_minutes),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    daily_dir = base / "Daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    out_file = daily_dir / f"{log_date.strftime('%Y-%m-%d')}.yaml"
    out_file.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    print(f"Daily log written: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
