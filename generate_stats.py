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
with open("README.md", "a", encoding="utf-8") as f:
    f.write("""
            




            
----------------- NEW STATS SECTION ----------------
## 📅 Two-Week Study Summary  
**Period:** 2026-01-02 → 2026-01-15 (Friday → Thursday)

### ⏱ Total Study Time
- **Total (2 weeks):** **37h 36m** (2,256 minutes)

---

### 🧠 Category Breakdown
- **TryHackMe:** 16h 45m  
- **HackTheBox:** 12h 29m  
- **CTF:** 7h 37m  
- **TCM-Security:** 0h 45m  

---

### 🎯 4-Week Target Progress
- **4-week target:** 126h  
- **Studied in these 2 weeks:** 37h 36m  
- **Remaining to hit 4-week target:** **88h 24m**



## 📈 3-Month Study Summary (Oct–Dec 2025)

### 📊 Monthly Breakdown
- **2025-10 → 2025-11:** 75h 22m
- **2025-11:** 115h 49m
- **2025-12:** 77h 21m

### ⏱ Overall Total
- **Total study time:** 268h 32m  
- **Total minutes:** 16,112

### 🧠 Category Totals
- **TryHackMe:** 89h 04m
- **HackTheBox:** 62h 35m
- **INE-eJPT:** 76h 41m
- **CTF:** 21h 55m
- **TCM-Security:** 10h 11m
- **Books / Reading:** 6h 30m
- **Labex:** 1h 31m
- **PortSwigger:** 0h 45m
- **General CS:** 1h 10m
- **Programming Language:** 0h 19m

### 📝 Notes
- Primary focus on **hands-on labs** (THM, HTB, CTF).
- Heavy investment in **INE-eJPT preparation**.
- **December consistency improved** despite partial weeks.
- Reading used as **supporting material**, not main workload.
""")