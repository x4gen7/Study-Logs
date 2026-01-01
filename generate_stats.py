#!/usr/bin/env python3

from pathlib import Path
import yaml
from datetime import datetime, timedelta, date

# ---------------- CONFIG ----------------

BASE = Path.home() / "Documents/Study-Logs"
DAILY_DIR = BASE / "Daily"
WEEKLY_DIR = BASE / "weekly"
MONTHLY_DIR = BASE / "Monthly"
OUTPUT = BASE / "README.md"

DAILY_TARGET_MIN = 270
WEEKLY_TARGET_MIN = DAILY_TARGET_MIN * 7  # 31h 30m

# ---------------- HELPERS ----------------

def hm(m):
    return f"{m//60}h {m%60:02d}m"

def parse_date(d):
    if isinstance(d, date):
        return datetime.combine(d, datetime.min.time())
    return datetime.strptime(d, "%Y-%m-%d")

def week_start(dt):
    return dt - timedelta(days=(dt.weekday() - 4) % 7)  # Friday start

# ---------------- LOAD DAILY ----------------

daily_logs = []

for f in sorted(DAILY_DIR.glob("*.yaml")):
    d = yaml.safe_load(f.read_text())
    if "date" not in d or "day_total_minutes" not in d:
        continue

    categories = {}
    if "category_totals" in d:
        categories = d["category_totals"]
    elif "entries" in d:
        for e in d["entries"]:
            cat = e["category"]
            categories[cat] = categories.get(cat, 0) + e.get("duration_minutes", 0)

    daily_logs.append({
        "date": parse_date(d["date"]),
        "categories": categories,
        "total": d["day_total_minutes"],
    })

# ---------------- LOAD WEEKLY ----------------

weekly_logs = []

for f in sorted(WEEKLY_DIR.glob("*.yaml")):
    d = yaml.safe_load(f.read_text())
    if "week_start" not in d or "week_end" not in d:
        continue
    weekly_logs.append({
        "range": f"{d['week_start']} → {d['week_end']}",
        "total": d.get("overall_minutes", 0),
    })

# ---------------- LOAD MONTHLY ----------------

monthly_logs = []

for f in sorted(MONTHLY_DIR.glob("*.yaml")):
    d = yaml.safe_load(f.read_text())
    if "overall_minutes" not in d:
        continue
    label = d.get("month", f.stem)
    monthly_logs.append({
        "label": label,
        "total": d["overall_minutes"],
    })

# ---------------- BUILD README ----------------

lines = []

# ===== DAILY TIMELINE =====
lines.append("## 📅 Daily Progress")
lines.append("***")
lines.append("")
lines.append(f"**Weekly target:** {hm(WEEKLY_TARGET_MIN)}")
lines.append("")

weekly_done = 0
current_week = None

for d in daily_logs:
    ws = week_start(d["date"])
    if ws != current_week:
        current_week = ws
        weekly_done = 0

    weekly_done += d["total"]
    remaining = max(WEEKLY_TARGET_MIN - weekly_done, 0)

    lines.append(f"### {d['date'].strftime('%Y-%m-%d (%A)')}")
    lines.append("")

    for cat, mins in d["categories"].items():
        lines.append(f"- {cat}: {hm(mins)}")

    lines.append("")
    lines.append(f"**Today:** {hm(d['total'])}")
    lines.append(f"**Weekly progress:** {hm(weekly_done)} / {hm(WEEKLY_TARGET_MIN)}")
    lines.append(f"**Remaining this week:** {hm(remaining)}")
    lines.append("")

# ===== DAILY SUMMARY =====
lines.append("")
lines.append("## 📅 Daily Progress")
lines.append("--------------")
lines.append("")

for d in daily_logs:
    lines.append(f"- **{d['date'].strftime('%Y-%m-%d')}** → {hm(d['total'])}")

# ===== WEEKLY SUMMARY =====
lines.append("")
lines.append("")
lines.append("## 📆 Weekly Progress")
lines.append("---------------")
lines.append("")

for w in weekly_logs:
    lines.append(f"- **{w['range']}** → {hm(w['total'])}")

# ===== MONTHLY SUMMARY =====
lines.append("")
lines.append("")
lines.append("## 🗓 Monthly Progress")
lines.append("----------------")
lines.append("")

for m in monthly_logs:
    lines.append(f"- **{m['label']}** → {hm(m['total'])}")

# ---------------- WRITE ----------------

OUTPUT.write_text("\n".join(lines))
print("[+] README.md generated (daily timeline + summaries)")
