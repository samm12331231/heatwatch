"""
Quick fetcher — grabs one heat event day + one null day.
Saves every record immediately so no data is lost.
"""
import json, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from config import SITES, API_SETTINGS
from core_engine import fetch_temperature
from wbgt import estimate_wbgt
from config import get_policy_level

DATA_DIR = Path("data/fortyguard")
DATA_DIR.mkdir(parents=True, exist_ok=True)

from fortyguard import FortyGuardClient
client = FortyGuardClient()

# --- Heat event: July 15, 2023 12:00 + 16:00 ---
print("=" * 60)
print("QUICK FETCH — 1 heat day + 1 null day")
print("=" * 60)

heat_cache = {}
null_cache = {}

# Heat day
date = "2023-07-15"
for time_slot in ["12:00", "16:00"]:
    for site in SITES:
        key = f"{site['id']}_{date}_{time_slot}"
        print(f"  Fetching {site['id']} @ {date} {time_slot}...", end=" ", flush=True)
        temp = fetch_temperature(client, site, date, time_slot)
        heat_cache[key] = {"temperature_c": round(temp, 2), "site_id": site["id"], "date": date, "time": time_slot}
        rh = 15 if time_slot == "16:00" else 20
        wbgt = estimate_wbgt(temp, rh, 900.0, 1.5)
        level = get_policy_level(wbgt["wbgt_f"])
        print(f"{temp:.1f}°C → WBGT {wbgt['wbgt_f']:.0f}F → {level.upper()}")
        time.sleep(2)

with open(DATA_DIR / "event_2023-07-15_to_2023-07-15.json", "w") as f:
    json.dump(heat_cache, f, indent=2)

# Null day (spring — shouldn't trigger)
date = "2023-04-10"
for time_slot in ["12:00", "16:00"]:
    for site in SITES:
        key = f"{site['id']}_{date}_{time_slot}"
        print(f"  Fetching {site['id']} @ {date} {time_slot}...", end=" ", flush=True)
        temp = fetch_temperature(client, site, date, time_slot)
        null_cache[key] = {"temperature_c": round(temp, 2), "site_id": site["id"], "date": date, "time": time_slot}
        rh = 15 if time_slot == "16:00" else 20
        wbgt = estimate_wbgt(temp, rh, 900.0, 1.5)
        level = get_policy_level(wbgt["wbgt_f"])
        print(f"{temp:.1f}°C → WBGT {wbgt['wbgt_f']:.0f}F → {level.upper()}")
        time.sleep(2)

with open(DATA_DIR / "null_days.json", "w") as f:
    json.dump(null_cache, f, indent=2)

print(f"\n✅ Heat: {len(heat_cache)} records saved")
print(f"✅ Null: {len(null_cache)} records saved")
print("\nRun: python eval_harness.py")
