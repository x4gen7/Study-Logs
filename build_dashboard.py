#!/usr/bin/env python3
"""Aggregate Daily/Weekly/Monthly YAML logs into dashboard/data.json."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

WEEKLY_TARGET_MIN = 1500
FOUR_WEEK_TARGET_MIN = WEEKLY_TARGET_MIN * 4


def hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else default


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def week_start(d: date) -> date:
    # Friday start
    return d - timedelta(days=(d.weekday() - 4) % 7)


def load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_daily(daily_dir: Path) -> list[dict[str, Any]]:
    logs = []
    for path in sorted(daily_dir.glob("*.yaml")):
        data = load_yaml(path)
        if not data or "date" not in data:
            continue
        categories: dict[str, int] = defaultdict(int)
        for entry in data.get("entries") or []:
            if isinstance(entry, dict):
                try:
                    categories[str(entry.get("category", "Unknown"))] += int(
                        entry.get("duration_minutes", 0)
                    )
                except (TypeError, ValueError):
                    continue
        logs.append(
            {
                "date": parse_date(data["date"]).isoformat(),
                "total": int(data.get("day_total_minutes", 0)),
                "categories": dict(categories),
                "status": str(data.get("status", "study_day")),
                "off_day_reason": data.get("off_day_reason"),
            }
        )
    logs.sort(key=lambda log: log["date"])
    return logs


def load_weekly(weekly_dir: Path) -> list[dict[str, Any]]:
    logs = []
    for path in sorted(weekly_dir.glob("*.yaml")):
        data = load_yaml(path)
        if not data or "week_start" not in data:
            continue
        logs.append(
            {
                "start": parse_date(data["week_start"]).isoformat(),
                "end": parse_date(data["week_end"]).isoformat(),
                "total": to_int(data.get("overall_minutes", 0)),
                "off_days": to_int(data.get("off_days", 0)),
                "categories": {
                    str(k): to_int(v)
                    for k, v in (data.get("category_totals") or {}).items()
                },
            }
        )
    logs.sort(key=lambda log: log["start"])
    return logs


def load_monthly(monthly_dir: Path) -> list[dict[str, Any]]:
    logs = []
    for path in sorted(monthly_dir.glob("*.yaml")):
        data = load_yaml(path)
        if not data:
            continue
        if "period_start" in data:
            start = parse_date(data["period_start"])
            end = parse_date(data["period_end"])
        elif "month" in data:
            # Legacy formats: "YYYY-MM" or "YYYY-MM_to_YYYY-MM".
            months = re.findall(r"\d{4}-\d{2}", str(data["month"]))
            if not months:
                continue
            start = datetime.strptime(months[0], "%Y-%m").date()
            end_month = datetime.strptime(months[-1], "%Y-%m").date()
            next_month = (end_month.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = next_month - timedelta(days=1)
        else:
            continue
        logs.append(
            {
                "label": path.stem,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "total": to_int(data.get("overall_minutes", 0)),
                "off_days": to_int(data.get("off_days", 0)),
                "goal_percent": float(data.get("goal_completion_percent", 0)),
                "categories": {
                    str(k): to_int(v)
                    for k, v in (data.get("category_totals") or {}).items()
                },
            }
        )
    logs.sort(key=lambda log: log["start"])
    return logs


def main() -> int:
    base = Path(__file__).resolve().parent
    today = date.today()

    daily = load_daily(base / "Daily")
    weekly = load_weekly(base / "Weekly")
    monthly = load_monthly(base / "Monthly")

    # Current week (Friday -> Thursday) computed live from daily logs.
    ws = week_start(today)
    we = ws + timedelta(days=6)
    week_days = [d for d in daily if ws.isoformat() <= d["date"] <= we.isoformat()]
    week_total = sum(d["total"] for d in week_days)
    week_categories: dict[str, int] = defaultdict(int)
    for d in week_days:
        for cat, mins in d["categories"].items():
            week_categories[cat] += mins

    today_log = next((d for d in daily if d["date"] == today.isoformat()), None)

    # All-time category totals without double counting:
    # months cover their span, then weeks after the last month, then days after the last week.
    overall: dict[str, int] = defaultdict(int)
    overall_minutes = 0
    off_days = 0
    covered_until = ""
    for m in monthly:
        overall_minutes += m["total"]
        off_days += m["off_days"]
        for cat, mins in m["categories"].items():
            overall[cat] += mins
        covered_until = max(covered_until, m["end"])
    for w in weekly:
        if w["start"] > covered_until:
            overall_minutes += w["total"]
            off_days += w["off_days"]
            for cat, mins in w["categories"].items():
                overall[cat] += mins
            covered_until = max(covered_until, w["end"])
    for d in daily:
        if d["date"] > covered_until:
            overall_minutes += d["total"]
            if d["status"] == "off_day":
                off_days += 1
            for cat, mins in d["categories"].items():
                overall[cat] += mins

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "weekly_target_minutes": WEEKLY_TARGET_MIN,
        "four_week_target_minutes": FOUR_WEEK_TARGET_MIN,
        "today": today_log,
        "current_week": {
            "start": ws.isoformat(),
            "end": we.isoformat(),
            "total": week_total,
            "total_display": hm(week_total),
            "remaining": max(0, WEEKLY_TARGET_MIN - week_total),
            "categories": dict(
                sorted(week_categories.items(), key=lambda kv: kv[1], reverse=True)
            ),
            "days": week_days,
        },
        "daily_recent": daily[-28:],
        "weekly": weekly,
        "monthly": monthly,
        "overall": {
            "minutes": overall_minutes,
            "display": hm(overall_minutes),
            "off_days": off_days,
            "categories": dict(
                sorted(overall.items(), key=lambda kv: kv[1], reverse=True)
            ),
        },
    }

    out = base / "dashboard" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[+] wrote {out.relative_to(base)} ({overall_minutes} min all-time)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
