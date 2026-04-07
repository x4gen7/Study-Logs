#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


DEFAULT_FULL_DAY_TARGET_MIN = 270
DEFAULT_LIGHT_DAY_TARGET_MIN = 135
DEFAULT_FULL_DAYS_PER_WEEK = 4
WEEKS_PER_MONTH_TARGET = 4
DEFAULT_WEEKLY_WINDOW = 7


def hm(minutes: int) -> str:
    mins = int(minutes)
    return f"{mins // 60}h {mins % 60:02d}m"


def parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    raise ValueError(f"Unsupported date value: {value!r}")


def week_start(dt: datetime) -> datetime:
    # Friday week start
    return dt - timedelta(days=(dt.weekday() - 4) % 7)


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        match = re.search(r"-?\d+", value)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return default
    return default


def normalize_category(name: Any) -> str:
    if not isinstance(name, str):
        return "Unknown"
    normalized = " ".join(name.strip().split())
    aliases = {
        "Books / Reading": "Book Penetration Testing - A Hands-On Introduction to Hacking",
        "Book": "Book Penetration Testing - A Hands-On Introduction to Hacking",
        "Book (Penetration Testing - A Hands-On Introduction to Hacking)": "Book Penetration Testing - A Hands-On Introduction to Hacking",
        "Programming Language": "General CS",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized or "Unknown"


def load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception as exc:
        print(f"[WARN] Failed to read {path}: {exc}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"[WARN] Skipping {path}: expected YAML mapping", file=sys.stderr)
        return None
    return data


def load_daily_logs(daily_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []

    for file_path in sorted(daily_dir.glob("*.yaml")):
        data = load_yaml(file_path)
        if not data:
            continue

        if "date" not in data or "day_total_minutes" not in data:
            print(f"[WARN] Skipping {file_path}: missing required fields", file=sys.stderr)
            continue

        try:
            d = parse_date(data["date"])
        except ValueError as exc:
            print(f"[WARN] Skipping {file_path}: {exc}", file=sys.stderr)
            continue

        categories: dict[str, int] = defaultdict(int)

        if isinstance(data.get("category_totals"), dict):
            for cat, mins in data["category_totals"].items():
                categories[normalize_category(cat)] += to_int(mins)
        elif isinstance(data.get("entries"), list):
            for entry in data["entries"]:
                if not isinstance(entry, dict):
                    continue
                cat = normalize_category(entry.get("category"))
                categories[cat] += to_int(entry.get("duration_minutes"), default=0)

        total = to_int(data.get("day_total_minutes"), default=-1)
        if total < 0:
            print(f"[WARN] Skipping {file_path}: invalid day_total_minutes", file=sys.stderr)
            continue

        status = str(data.get("status") or "study_day").strip() or "study_day"
        reason = data.get("off_day_reason")
        if not isinstance(reason, str):
            reason = None

        logs.append({
            "date": d,
            "categories": dict(sorted(categories.items())),
            "total": total,
            "status": status,
            "off_day_reason": reason,
        })

    logs.sort(key=lambda item: item["date"])
    return logs


def load_weekly_logs(base: Path, max_logs: int = 7) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    weekly_dir = base / "Weekly"
    if not weekly_dir.exists():
        return logs

    for file_path in sorted(weekly_dir.glob("*.yaml")):
        data = load_yaml(file_path)
        if not data:
            continue

        if "week_start" not in data or "week_end" not in data:
            continue

        try:
            start = parse_date(data["week_start"])
            end = parse_date(data["week_end"])
        except ValueError as exc:
            print(f"[WARN] Skipping {file_path}: {exc}", file=sys.stderr)
            continue

        category_totals: dict[str, int] = {}
        if isinstance(data.get("category_totals"), dict):
            for cat, mins in data["category_totals"].items():
                category_totals[normalize_category(cat)] = to_int(mins)

        logs.append({
            "start": start,
            "end": end,
            "range": f"{start.strftime('%Y-%m-%d')} -> {end.strftime('%Y-%m-%d')}",
            "total": to_int(data.get("overall_minutes"), default=0),
            "categories": category_totals,
            "off_days": to_int(data.get("off_days"), default=0),
        })

    logs.sort(key=lambda item: (item["start"], item["end"]))
    if max_logs > 0:
        logs = logs[-max_logs:]
    return logs


def month_sort_key(data: dict[str, Any], file_path: Path) -> datetime:
    if data.get("period_start"):
        try:
            return parse_date(data["period_start"])
        except ValueError:
            pass
    if data.get("month"):
        month_label = str(data["month"])
        token = month_label.split("_to_")[0]
        try:
            return datetime.strptime(token, "%Y-%m")
        except ValueError:
            pass
    try:
        return datetime.strptime(file_path.stem, "%Y-%m")
    except ValueError:
        return datetime.min


def month_label(data: dict[str, Any], file_path: Path) -> str:
    # Prefer file stem when it already matches YYYY-MM (e.g. 2026-02.yaml).
    try:
        datetime.strptime(file_path.stem, "%Y-%m")
        return file_path.stem
    except ValueError:
        pass

    if data.get("month"):
        token = str(data["month"]).split("_to_")[0]
        try:
            datetime.strptime(token, "%Y-%m")
            return token
        except ValueError:
            pass

    if data.get("period_start"):
        try:
            return parse_date(data["period_start"]).strftime("%Y-%m")
        except ValueError:
            pass

    return file_path.stem


def load_monthly_logs(monthly_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for file_path in sorted(monthly_dir.glob("*.yaml")):
        data = load_yaml(file_path)
        if not data:
            continue
        if "overall_minutes" not in data:
            continue

        label = month_label(data, file_path)

        category_totals: dict[str, int] = defaultdict(int)
        if isinstance(data.get("category_totals"), dict):
            for cat, mins in data["category_totals"].items():
                category_totals[normalize_category(cat)] += to_int(mins)

        sort_key = month_sort_key(data, file_path)
        period_end = sort_key
        if data.get("period_end"):
            try:
                period_end = parse_date(data["period_end"])
            except ValueError:
                period_end = sort_key

        logs.append({
            "label": str(label),
            "total": to_int(data.get("overall_minutes"), default=0),
            "categories": dict(category_totals),
            "sort_key": sort_key,
            "period_end": period_end,
            "off_days": to_int(data.get("off_days"), default=0),
        })

    return logs


def build_readme(
    daily_logs: list[dict[str, Any]],
    weekly_logs: list[dict[str, Any]],
    monthly_logs: list[dict[str, Any]],
    weekly_target_min: int,
    weekly_window: int,
) -> str:
    lines: list[str] = []
    four_week_target_min = weekly_target_min * WEEKS_PER_MONTH_TARGET

    # Daily timeline
    lines.append("## Daily Timeline")
    lines.append("***")
    lines.append("")
    lines.append(f"**Weekly target:** {hm(weekly_target_min)}")
    lines.append(f"**4-week target:** {hm(four_week_target_min)}")
    lines.append("")

    weekly_done = 0
    current_week: datetime | None = None

    for day in daily_logs:
        ws = week_start(day["date"])
        if ws != current_week:
            current_week = ws
            weekly_done = 0

        weekly_done += day["total"]
        remaining = max(weekly_target_min - weekly_done, 0)

        lines.append(f"### {day['date'].strftime('%Y-%m-%d (%A)')}")
        lines.append("")

        if day.get("status") == "off_day":
            lines.append("- Off day")
            if day.get("off_day_reason"):
                lines.append(f"- Reason: {day['off_day_reason']}")
        else:
            for cat, mins in day["categories"].items():
                lines.append(f"- {cat}: {hm(mins)}")

        lines.append("")
        lines.append(f"**Today:** {hm(day['total'])}")
        lines.append(f"**Weekly progress:** {hm(weekly_done)} / {hm(weekly_target_min)}")
        lines.append(f"**Remaining this week:** {hm(remaining)}")
        lines.append("")

    # Daily summary
    lines.append("")
    lines.append("## 📅 Daily Summary")
    lines.append("--------------")
    lines.append("")
    for day in daily_logs:
        if day.get("status") == "off_day":
            label = "Off day"
            if day.get("off_day_reason"):
                label += f" ({day['off_day_reason']})"
            lines.append(f"- **{day['date'].strftime('%Y-%m-%d')}** -> {label}")
        else:
            lines.append(f"- **{day['date'].strftime('%Y-%m-%d')}** -> {hm(day['total'])}")

    # Weekly summary
    lines.append("")
    lines.append("")
    lines.append("## 📅 Weekly Progress")
    lines.append("---------------")
    lines.append("")
    if weekly_window > 0:
        weekly_logs_to_show = weekly_logs[-weekly_window:]
    else:
        weekly_logs_to_show = weekly_logs

    for idx, week in enumerate(weekly_logs_to_show, start=1):
        week_line = f"- **{week['range']} (Week-{idx})** -> {hm(week['total'])}"
        off_days = int(week.get("off_days", 0))
        if off_days > 0:
            week_line += f" | Off days: {off_days}"
        lines.append(week_line)

    # Weekly detailed summary for latest week and 4-week span progress
    if weekly_logs_to_show:
        span_weeks = weekly_logs_to_show[-4:]
        studied_so_far = sum(item["total"] for item in span_weeks)
        off_days_in_span = sum(int(item.get("off_days", 0)) for item in span_weeks)
        remaining = max(four_week_target_min - studied_so_far, 0)
        span_start = span_weeks[0]["start"]
        span_end = span_weeks[-1]["end"]
        span_categories: dict[str, int] = defaultdict(int)
        for week in span_weeks:
            for cat, mins in week.get("categories", {}).items():
                span_categories[cat] += int(mins)

        lines.append("")
        lines.append("## 📅 Weekly Study Summary")
        lines.append(
            f"**Weeks:** {span_start.strftime('%Y-%m-%d')} -> {span_end.strftime('%Y-%m-%d')} "
            "(Friday -> Thursday)"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### ⏱ Total Study Time")
        lines.append(f"- **This span:** **{hm(studied_so_far)}** ({studied_so_far} minutes)")
        lines.append(f"- **Off days:** {off_days_in_span}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### 🧠 Category Breakdown")

        if span_categories:
            for cat, mins in sorted(span_categories.items(), key=lambda item: item[1], reverse=True):
                lines.append(f"- **{cat}:** {hm(mins)}")
        else:
            lines.append("- No category data for this span.")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### 🎯 4-Week Target Progress")
        lines.append(f"- **4-week target:** {hm(four_week_target_min)}")
        lines.append(
            f"- **Studied so far ({len(span_weeks)} / {WEEKS_PER_MONTH_TARGET} weeks):** **{hm(studied_so_far)}**"
        )
        lines.append(f"- **Off days in {len(span_weeks)}-week span:** {off_days_in_span}")
        lines.append(f"- **Remaining to hit 4-week target:** **{hm(remaining)}**")

    # Monthly summary
    lines.append("")
    lines.append("")
    lines.append("## 📅 Monthly Progress")
    lines.append("----------------")
    lines.append("")
    if monthly_logs:
        for month in monthly_logs:
            lines.append(f"- **{month['label']}** -> {hm(month['total'])}")
    else:
        lines.append("- No monthly logs found.")

    # Dynamic aggregate summary
    lines.append("")
    lines.append("")

    lines.append("## Study Summary")

    lines.append("")
    lines.append("### Overall Total")

    total_minutes = sum(month["total"] for month in monthly_logs)
    total_off_days = sum(int(month.get("off_days", 0)) for month in monthly_logs)
    lines.append(f"- **Total study time:** **{hm(total_minutes)}**")
    lines.append(f"- **Total minutes:** {total_minutes:,}")

    category_totals: dict[str, int] = defaultdict(int)
    for month in monthly_logs:
        for cat, mins in month["categories"].items():
            category_totals[cat] += mins

    lines.append("")
    lines.append("### Category Totals")
    if category_totals:
        for cat, mins in sorted(category_totals.items(), key=lambda item: item[1], reverse=True):
            if mins <= 0:
                continue
            lines.append(f"- **{cat}:** {hm(mins)}")
    else:
        lines.append("- No category totals available.")
    lines.append(f"- **Day Offs:** {total_off_days}")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    script_base = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description="Generate Study-Logs README summary from YAML files.")
    parser.add_argument("--base", type=Path, default=script_base, help="Base directory containing Daily/Weekly/Monthly")
    parser.add_argument("--output", type=Path, default=None, help="Output README path (default: <base>/README.md)")
    parser.add_argument(
        "--full-day-target",
        type=int,
        default=DEFAULT_FULL_DAY_TARGET_MIN,
        help="Target minutes for a standard study day.",
    )
    parser.add_argument(
        "--light-day-target",
        type=int,
        default=DEFAULT_LIGHT_DAY_TARGET_MIN,
        help="Target minutes for the lighter day in the week.",
    )
    parser.add_argument(
        "--full-days-per-week",
        type=int,
        default=DEFAULT_FULL_DAYS_PER_WEEK,
        help="Number of standard target days in each 7-day week.",
    )
    parser.add_argument("--weekly-window", type=int, default=DEFAULT_WEEKLY_WINDOW, help="Number of weekly logs to show from Weekly folder")
    parser.add_argument("--dry-run", action="store_true", help="Print generated markdown instead of writing file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    base = args.base.resolve()
    output = args.output.resolve() if args.output else base / "README.md"

    daily_dir = base / "Daily"
    monthly_dir = base / "Monthly"

    full_days_per_week = min(max(args.full_days_per_week, 0), 7)
    light_days_per_week = max(7 - full_days_per_week, 0)
    weekly_target_min = (args.full_day_target * full_days_per_week) + (args.light_day_target * light_days_per_week)

    daily_logs = load_daily_logs(daily_dir)
    weekly_logs = load_weekly_logs(base, max_logs=max(args.weekly_window, 0))
    monthly_logs = load_monthly_logs(monthly_dir)

    markdown = build_readme(
        daily_logs=daily_logs,
        weekly_logs=weekly_logs,
        monthly_logs=monthly_logs,
        weekly_target_min=weekly_target_min,
        weekly_window=max(args.weekly_window, 0),
    )

    if args.dry_run:
        print(markdown)
        return 0

    output.write_text(markdown, encoding="utf-8")
    print(f"[+] {output} generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
