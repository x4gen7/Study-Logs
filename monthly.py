#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


DEFAULT_WEEKLY_GOAL_MINUTES = 1755
WEEKS_PER_MONTH_LOG = 4


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


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_category(name: Any) -> str:
    if not isinstance(name, str):
        return "Unknown"
    normalized = " ".join(name.strip().split())
    return normalized or "Unknown"


def load_weekly_logs(weekly_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for file_path in sorted(weekly_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue
        if "week_start" not in data or "week_end" not in data:
            continue

        try:
            start = parse_date(data["week_start"])
            end = parse_date(data["week_end"])
        except ValueError:
            continue

        category_totals: dict[str, int] = defaultdict(int)
        if isinstance(data.get("category_totals"), dict):
            for cat, mins in data["category_totals"].items():
                category_totals[normalize_category(cat)] += to_int(mins)

        logs.append({
            "start": start,
            "end": end,
            "categories": dict(category_totals),
            "total": to_int(data.get("overall_minutes"), default=0),
            "off_days": to_int(data.get("off_days"), default=0),
            "file": file_path.name,
        })

    logs.sort(key=lambda item: (item["start"], item["end"]))
    return logs


def build_runs(weekly_logs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not weekly_logs:
        return []

    runs: list[list[dict[str, Any]]] = []
    current_run: list[dict[str, Any]] = [weekly_logs[0]]

    for log in weekly_logs[1:]:
        prev = current_run[-1]
        if log["start"] == prev["start"] + timedelta(days=7):
            current_run.append(log)
        else:
            runs.append(current_run)
            current_run = [log]

    runs.append(current_run)
    return runs


def iter_month_groups(weekly_logs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for run in build_runs(weekly_logs):
        for idx in range(0, len(run), WEEKS_PER_MONTH_LOG):
            group = run[idx: idx + WEEKS_PER_MONTH_LOG]
            if len(group) == WEEKS_PER_MONTH_LOG:
                groups.append(group)
    return groups


def build_month_payload(group: list[dict[str, Any]], weekly_goal_minutes: int) -> tuple[str, dict[str, Any]]:
    period_start = group[0]["start"]
    period_end = group[-1]["end"]
    month_label = period_end.strftime("%Y-%m")

    category_totals: dict[str, int] = defaultdict(int)
    overall_minutes = 0
    off_days = 0
    for week in group:
        overall_minutes += int(week["total"])
        off_days += int(week.get("off_days", 0))
        for cat, mins in week["categories"].items():
            category_totals[cat] += int(mins)

    sorted_categories = dict(sorted(category_totals.items(), key=lambda item: item[1], reverse=True))
    four_week_goal_minutes = weekly_goal_minutes * WEEKS_PER_MONTH_LOG
    goal_completion_percent = round((overall_minutes / four_week_goal_minutes) * 100, 1) if four_week_goal_minutes else 0.0

    payload = {
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "weeks_count": WEEKS_PER_MONTH_LOG,
        "category_totals": sorted_categories,
        "overall_minutes": overall_minutes,
        "overall_hours": hm(overall_minutes),
        "weekly_goal_minutes": weekly_goal_minutes,
        "weekly_goal_display": hm(weekly_goal_minutes),
        "four_week_goal_minutes": four_week_goal_minutes,
        "four_week_goal_display": hm(four_week_goal_minutes),
        "goal_completion_percent": goal_completion_percent,
        "off_days": off_days,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return month_label, payload


def parse_args() -> argparse.Namespace:
    script_base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate Monthly/*.yaml files from groups of 4 Weekly/*.yaml logs."
    )
    parser.add_argument("--base", type=Path, default=script_base, help="Base folder containing Weekly/ and Monthly/")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing monthly files")
    parser.add_argument(
        "--weekly-goal-minutes",
        type=int,
        default=DEFAULT_WEEKLY_GOAL_MINUTES,
        help="Weekly target minutes used to compute 4-week goal completion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base.resolve()
    weekly_dir = base / "Weekly"
    monthly_dir = base / "Monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    weekly_logs = load_weekly_logs(weekly_dir)
    month_groups = iter_month_groups(weekly_logs)

    written = 0
    skipped = 0

    for group in month_groups:
        month_label, payload = build_month_payload(group, weekly_goal_minutes=args.weekly_goal_minutes)
        out_file = monthly_dir / f"{month_label}.yaml"
        if out_file.exists() and not args.overwrite:
            skipped += 1
            continue

        out_file.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        written += 1
        print(f"[+] wrote {out_file.name}")

    print(f"Done. written={written}, skipped={skipped}")
    if not month_groups:
        print("No complete 4-week groups found in Weekly/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
