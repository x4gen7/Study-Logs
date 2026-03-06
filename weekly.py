#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


def hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    raise ValueError(f"Unsupported date value: {value!r}")


def week_start(dt: datetime) -> datetime:
    # Friday start
    return dt - timedelta(days=(dt.weekday() - 4) % 7)


def normalize_category(name: Any) -> str:
    if not isinstance(name, str):
        return "Unknown"
    normalized = " ".join(name.strip().split())
    aliases = {
        "Programming Language": "General CS",
        "Books / Reading": "Book Penetration Testing - A Hands-On Introduction to Hacking",
        "Book": "Book Penetration Testing - A Hands-On Introduction to Hacking",
        "Book (Penetration Testing - A Hands-On Introduction to Hacking)": "Book Penetration Testing - A Hands-On Introduction to Hacking",
    }
    return aliases.get(normalized, normalized)


def load_daily_logs(daily_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for file_path in sorted(daily_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if "date" not in data or "day_total_minutes" not in data:
            continue

        try:
            dt = parse_date(data["date"])
        except ValueError:
            continue

        categories: dict[str, int] = defaultdict(int)
        if isinstance(data.get("category_totals"), dict):
            for cat, mins in data["category_totals"].items():
                try:
                    categories[normalize_category(cat)] += int(mins)
                except (TypeError, ValueError):
                    continue
        elif isinstance(data.get("entries"), list):
            for entry in data["entries"]:
                if not isinstance(entry, dict):
                    continue
                cat = normalize_category(entry.get("category"))
                try:
                    mins = int(entry.get("duration_minutes", 0))
                except (TypeError, ValueError):
                    mins = 0
                categories[cat] += mins

        try:
            total = int(data["day_total_minutes"])
        except (TypeError, ValueError):
            continue

        logs.append({"date": dt, "total": total, "categories": dict(categories)})
    return logs


def build_weekly_groups(daily_logs: list[dict[str, Any]]) -> dict[datetime, dict[str, Any]]:
    groups: dict[datetime, dict[str, Any]] = {}
    for log in daily_logs:
        start = week_start(log["date"])
        if start not in groups:
            groups[start] = {
                "start": start,
                "end": start + timedelta(days=6),
                "overall_minutes": 0,
                "category_totals": defaultdict(int),
                "days_present": 0,
            }
        g = groups[start]
        g["overall_minutes"] += log["total"]
        g["days_present"] += 1
        for cat, mins in log["categories"].items():
            g["category_totals"][cat] += mins
    return groups


def parse_args() -> argparse.Namespace:
    script_base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate Weekly/*.yaml files from Daily/*.yaml logs (Friday -> Thursday)."
    )
    parser.add_argument("--base", type=Path, default=script_base, help="Base folder containing Daily/ and Weekly/")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing weekly files")
    parser.add_argument(
        "--only-full-week",
        action="store_true",
        help="Generate only weeks that have all 7 daily logs (default: include partial weeks).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base.resolve()
    daily_dir = base / "Daily"
    weekly_dir = base / "Weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    daily_logs = load_daily_logs(daily_dir)
    weekly_groups = build_weekly_groups(daily_logs)

    written = 0
    skipped = 0

    for start in sorted(weekly_groups):
        group = weekly_groups[start]
        if args.only_full_week and group["days_present"] < 7:
            skipped += 1
            continue

        start_s = group["start"].strftime("%Y-%m-%d")
        end_s = group["end"].strftime("%Y-%m-%d")
        out_file = weekly_dir / f"week-{start_s}_to_{end_s}.yaml"
        if out_file.exists() and not args.overwrite:
            skipped += 1
            continue

        category_totals = dict(sorted(group["category_totals"].items(), key=lambda item: item[1], reverse=True))
        payload = {
            "week_start": start_s,
            "week_end": end_s,
            "category_totals": category_totals,
            "overall_minutes": int(group["overall_minutes"]),
            "overall_hours": hm(int(group["overall_minutes"])),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        out_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
        written += 1
        print(f"[+] wrote {out_file.name}")

    print(f"Done. written={written}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
