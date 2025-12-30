#!/usr/bin/env python3
from pathlib import Path
import yaml

BASE = Path.home() / "Documents/Study-Logs"

DAILY = BASE / "Daily"
WEEKLY = BASE / "Weekly"
MONTHLY = BASE / "Monthly"

OUTPUT = BASE / "README.md"

def hm(m):
    m = int(m)
    return f"{m//60}h {m%60:02d}m"

def load_yaml(folder):
    for f in sorted(folder.glob("*.yaml")):
        with open(f) as fh:
            yield f.stem, yaml.safe_load(fh)

lines = []

# -------- DAILY --------
lines.append("## 📅 Daily Progress")
lines.append("--------------")
lines.append("")

for name, d in load_yaml(DAILY):
    minutes = d.get("day_total_minutes")
    if minutes is None:
        continue
    lines.append(f"- **{name}** → {hm(minutes)}")

lines.append("")
lines.append("")

# -------- WEEKLY --------
lines.append("## 📆 Weekly Progress")
lines.append("---------------")
lines.append("")

for _, d in load_yaml(WEEKLY):
    minutes = d.get("overall_minutes")
    if minutes is None:
        continue
    start = d.get("week_start", "unknown")
    end = d.get("week_end", "unknown")
    lines.append(f"- **{start} → {end}** → {hm(minutes)}")

lines.append("")
lines.append("")

# -------- MONTHLY --------
lines.append("## 🗓 Monthly Progress")
lines.append("----------------")
lines.append("")

for name, d in load_yaml(MONTHLY):
    minutes = d.get("overall_minutes")
    if minutes is None:
        continue
    month = d.get("month", name)
    lines.append(f"- **{month}** → {hm(minutes)}")

lines.append("")

# write output
OUTPUT.write_text("\n".join(lines))

print("[+] README.md generated in Markdown format")
