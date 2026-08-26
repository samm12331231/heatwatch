"""
Heatwatch Historical Data Fetcher

Downloads real temperature data from FortyGuard for historical Phoenix heat
events. Saves to JSON files in data/fortyguard/ for use by the eval harness.

Usage:
    python fetch_historical.py
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import SITES, API_SETTINGS, EVAL_SETTINGS
from core_engine import fetch_temperature

DATA_DIR = Path("data/fortyguard")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DELAY_SECONDS = 2.5  # Time between API calls to avoid rate limits


def make_cache_key(site_id: str, date: str, time_str: str) -> str:
    return f"{site_id}_{date}_{time_str}"


def load_cache(cache_file: Path) -> dict:
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, cache_file: Path):
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_event_data(client, event: dict) -> dict:
    """Fetch 12:00 and 16:00 temperatures for every site across an event window."""
    cache_file = DATA_DIR / f"event_{event['start']}_to_{event['end']}.json"
    cache = load_cache(cache_file)

    start = datetime.strptime(event["start"], "%Y-%m-%d")
    end = datetime.strptime(event["end"], "%Y-%m-%d")
    time_slots = ["12:00", "16:00"]

    total_days = (end - start).days + 1
    total_calls = total_days * len(SITES) * len(time_slots)
    completed = 0

    print(f"\n📡 Fetching: {event['name']}")
    print(f"   Period: {event['start']} → {event['end']}")
    print(f"   Sites: {len(SITES)}, Days: {total_days}, Slots: {len(time_slots)}")
    print(f"   Total API calls needed: {total_calls}")
    print(f"   Estimated time: ~{int(total_calls * DELAY_SECONDS / 60)} minutes\n")

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")

        for site in SITES:
            for time_str in time_slots:
                completed += 1
                key = make_cache_key(site["id"], date_str, time_str)

                # Skip if already cached with valid data
                if key in cache and cache[key].get("temperature_c", 0) > 0:
                    temp = cache[key]["temperature_c"]
                    print(f"   [{completed}/{total_calls}] (cached) {site['id']} @ {time_str}: {temp:.1f}°C")
                    continue

                temp = fetch_temperature(client, site, date_str, time_str)
                cache[key] = {
                    "temperature_c": round(temp, 2),
                    "site_id": site["id"],
                    "date": date_str,
                    "time": time_str,
                }

                status = "✓" if temp > 0 else "✗ 0.0°C"
                print(f"   [{completed}/{total_calls}] {status} {site['id']} @ {date_str} {time_str}")

                # Save every 5 calls so progress isn't lost
                if completed % 5 == 0:
                    save_cache(cache, cache_file)

                time.sleep(DELAY_SECONDS)

        current += timedelta(days=1)

    save_cache(cache, cache_file)
    print(f"\n   ✅ Saved {len(cache)} records to {cache_file}")

    # Report success rate
    valid = sum(1 for v in cache.values() if v.get("temperature_c", 0) > 0)
    print(f"   📊 {valid}/{len(cache)} records have valid temperature data")

    return cache


def fetch_null_day_data(client, dates: list) -> dict:
    """Fetch temperatures for null (non-heat) days for false alarm testing."""
    cache_file = DATA_DIR / "null_days.json"
    cache = load_cache(cache_file)

    time_slots = ["12:00", "16:00"]
    total_calls = len(dates) * len(SITES) * len(time_slots)
    completed = 0

    print(f"\n📡 Fetching null days for false alarm testing...")
    print(f"   Days: {len(dates)}, Sites: {len(SITES)}")
    print(f"   Total API calls: {total_calls}")
    print(f"   Estimated time: ~{int(total_calls * DELAY_SECONDS / 60)} minutes\n")

    for date_str in dates:
        for site in SITES:
            for time_str in time_slots:
                completed += 1
                key = make_cache_key(site["id"], date_str, time_str)

                # Skip if already cached with valid data
                if key in cache and cache[key].get("temperature_c", 0) > 0:
                    temp = cache[key]["temperature_c"]
                    print(f"   [{completed}/{total_calls}] (cached) {site['id']} @ {date_str} {time_str}: {temp:.1f}°C")
                    continue

                temp = fetch_temperature(client, site, date_str, time_str)
                cache[key] = {
                    "temperature_c": round(temp, 2),
                    "site_id": site["id"],
                    "date": date_str,
                    "time": time_str,
                }

                status = "✓" if temp > 0 else "✗ 0.0°C"
                print(f"   [{completed}/{total_calls}] {status} {site['id']} on {date_str} {time_str}")

                if completed % 5 == 0:
                    save_cache(cache, cache_file)

                time.sleep(DELAY_SECONDS)

    save_cache(cache, cache_file)
    print(f"\n   ✅ Saved {len(cache)} null-day records to {cache_file}")

    valid = sum(1 for v in cache.values() if v.get("temperature_c", 0) > 0)
    print(f"   📊 {valid}/{len(cache)} records have valid temperature data")

    return cache


def main():
    from fortyguard import FortyGuardClient
    client = FortyGuardClient()

    print("=" * 60)
    print("HEATWATCH HISTORICAL DATA FETCHER")
    print("=" * 60)

    # Fetch heat event data
    for event in EVAL_SETTINGS["heat_wave_events"]:
        fetch_event_data(client, event)

    # Null days — spring dates that shouldn't trigger heat alerts
    null_dates = [
        "2023-04-10", "2023-04-11", "2023-04-12",
    ]
    fetch_null_day_data(client, null_dates)

    print("\n" + "=" * 60)
    print("DONE — Run eval_harness.py to compute metrics.")
    print("=" * 60)


if __name__ == "__main__":
    main()
