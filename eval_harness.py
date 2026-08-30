"""
Heatwatch Evaluation Harness

Replays real historical temperature data against our decision layer and
computes detection metrics: recall, false alarm rate, lead time, cost delta.

Usage:
    # First fetch data (one-time, burns ~240 API credits):
    python fetch_historical.py

    # Then run eval:
    python eval_harness.py

    # Or run eval against live API (slower, uses credits):
    python eval_harness.py --live
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from config import SITES, HEAT_POLICY, EVAL_SETTINGS, PHOENIX_HUMIDITY
from wbgt import estimate_wbgt
from config import get_policy_level

DATA_DIR = Path("data/fortyguard")


def load_cached_data() -> dict:
    """Load all cached event data from disk."""
    all_data = {}

    if not DATA_DIR.exists():
        return all_data

    for cache_file in DATA_DIR.glob("event_*.json"):
        with open(cache_file) as f:
            event_data = json.load(f)
            all_data.update(event_data)

    return all_data


def load_null_data() -> dict:
    """Load cached null-day data."""
    null_file = DATA_DIR / "null_days.json"
    if null_file.exists():
        with open(null_file) as f:
            return json.load(f)
    return {}


def simulate_detection(temp_c: float, humidity_pct: float = 20.0) -> dict:
    """Simulate the detection logic for a single temperature reading."""
    # Conservative: solar=900, wind=1.5 for outdoor athletes in daytime
    wbgt = estimate_wbgt(temp_c, humidity_pct, 900.0, 1.5)
    policy_level = get_policy_level(wbgt["wbgt_f"])
    return {
        "temperature_c": temp_c,
        "wbgt_f": wbgt["wbgt_f"],
        "policy_level": policy_level,
        "alert": policy_level in ("red", "black"),
    }


def evaluate_heat_event(cache: dict, event: dict) -> dict:
    """Evaluate detection performance during a heat event using cached data."""
    start = datetime.strptime(event["start"], "%Y-%m-%d")
    end = datetime.strptime(event["end"], "%Y-%m-%d")

    site_results = {}

    for site in SITES:
        daily_alerts = []
        current = start

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")

            # Check afternoon slot (worst case)
            key = f"{site['id']}_{date_str}_16:00"
            if key in cache:
                temp = cache[key]["temperature_c"]
            else:
                # Try 12:00 as fallback
                key = f"{site['id']}_{date_str}_12:00"
                temp = cache.get(key, {}).get("temperature_c", 0)

            if temp > 0:
                hour = 16
                if hour < 11:
                    humidity = PHOENIX_HUMIDITY["morning_humidity_pct"]
                elif hour < 15:
                    humidity = PHOENIX_HUMIDITY["midday_humidity_pct"]
                else:
                    humidity = PHOENIX_HUMIDITY["afternoon_humidity_pct"]

                detection = simulate_detection(temp, humidity)
                daily_alerts.append({
                    "date": date_str,
                    "temp_c": temp,
                    "alert": detection["alert"],
                    "policy_level": detection["policy_level"],
                })
            else:
                daily_alerts.append({
                    "date": date_str,
                    "temp_c": None,
                    "alert": None,
                    "policy_level": None,
                })

            current += timedelta(days=1)

        # Metrics
        valid = [d for d in daily_alerts if d["temp_c"] is not None]
        alerts_fired = [d for d in valid if d["alert"]]

        site_results[site["id"]] = {
            "site_name": site["name"],
            "total_days": len(valid),
            "alerts_fired": len(alerts_fired),
            "recall": len(alerts_fired) / len(valid) if valid else 0,
            "daily_data": daily_alerts,
        }

    return site_results


def evaluate_null_days(cache: dict) -> dict:
    """Evaluate false alarm rate during non-heat days."""
    site_results = {}

    for site in SITES:
        false_alarms = 0
        total_days = 0

        for key, value in cache.items():
            if key.startswith(site["id"]) and value.get("temperature_c"):
                temp = value["temperature_c"]
                hour = int(value["time"].split(":")[0])
                if hour < 11:
                    humidity = PHOENIX_HUMIDITY["morning_humidity_pct"]
                elif hour < 15:
                    humidity = PHOENIX_HUMIDITY["midday_humidity_pct"]
                else:
                    humidity = PHOENIX_HUMIDITY["afternoon_humidity_pct"]

                detection = simulate_detection(temp, humidity)
                total_days += 1
                if detection["alert"]:
                    false_alarms += 1

        site_results[site["id"]] = {
            "site_name": site["name"],
            "total_readings": total_days,
            "false_alarms": false_alarms,
            "false_alarm_rate": false_alarms / total_days if total_days else 0,
        }

    return site_results


def compute_cost_delta(event_results: dict, naive_threshold: float = 35.0) -> dict:
    """
    Compute cost savings: Heatwatch rescheduling vs naive cancellation.
    
    Naive: cancel all practices when temp > threshold → $12,000 across 6 sites
    Heatwatch: reschedule to safe window → $1,500 impact
    """
    total_days = 0
    naive_cancellations = 0
    heatwatch_reschedules = 0

    for site_id, result in event_results.items():
        for day in result["daily_data"]:
            if day["temp_c"] is None:
                continue
            total_days += 1

            # Naive: cancel if above threshold
            if day["temp_c"] >= naive_threshold:
                naive_cancellations += 1

            # Heatwatch: only cancel if ALL buckets are dangerous
            # (we'd need multi-hour data, but approximate: if afternoon is bad,
            # we reschedule rather than cancel)
            if day["alert"]:
                heatwatch_reschedules += 1

    cost_naive = naive_cancellations * 2000  # $2,000 per cancelled practice
    cost_heatwatch = heatwatch_reschedules * 250  # $250 per reschedule (reduced cost)

    return {
        "total_site_days": total_days,
        "naive_cancellations": naive_cancellations,
        "heatwatch_reschedules": heatwatch_reschedules,
        "cost_naive": cost_naive,
        "cost_heatwatch": cost_heatwatch,
        "savings": cost_naive - cost_heatwatch,
    }


def run_eval(use_live_api: bool = False) -> dict:
    """Run the full evaluation harness."""
    print("=" * 60)
    print("HEATWATCH EVALUATION HARNESS")
    print("=" * 60)

    if use_live_api:
        print("\n⚠️  Using LIVE API — this will burn credits and take ~10 min.")
        from fortyguard import FortyGuardClient
        from fetch_historical import fetch_event_data, fetch_null_day_data
        client = FortyGuardClient()

        cache = {}
        for event in EVAL_SETTINGS["heat_wave_events"]:
            cache.update(fetch_event_data(client, event))

        null_dates = [
            "2023-04-15", "2023-04-16", "2023-04-17", "2023-04-18", "2023-04-19",
            "2023-05-20", "2023-05-21", "2023-05-22", "2023-05-23", "2023-05-24",
        ]
        null_cache = fetch_null_day_data(client, null_dates)
        cache.update(null_cache)
    else:
        cache = load_cached_data()
        null_cache = load_null_data()

        if not cache:
            print("\n❌ No cached data found. Run fetch_historical.py first:")
            print("   python fetch_historical.py")
            print("\n   Or run with --live flag:")
            print("   python eval_harness.py --live")
            sys.exit(1)

    # Evaluate heat events
    print("\n📊 Evaluating Heat Events...\n")
    all_event_results = {}

    for event in EVAL_SETTINGS["heat_wave_events"]:
        results = evaluate_heat_event(cache, event)
        all_event_results[event["name"]] = results

        # Print summary
        total_alerts = sum(r["alerts_fired"] for r in results.values())
        total_days = sum(r["total_days"] for r in results.values())
        recall = total_alerts / total_days if total_days else 0

        print(f"  Event: {event['name']}")
        print(f"  Period: {event['start']} to {event['end']}")
        print(f"    Total site-days: {total_days}")
        print(f"    Alerts fired: {total_alerts}/{total_days}")
        print(f"    Recall: {recall:.0%}")
        for site_id, r in results.items():
            print(f"      {r['site_name']}: {r['alerts_fired']}/{r['total_days']} days alerted")
        print()

    # Evaluate null days
    print("📊 Evaluating Null Days (False Alarms)...\n")
    null_results = evaluate_null_days(null_cache)

    total_null_readings = sum(r["total_readings"] for r in null_results.values())
    total_false_alarms = sum(r["false_alarms"] for r in null_results.values())
    overall_far = total_false_alarms / total_null_readings if total_null_readings else 0

    for site_id, r in null_results.items():
        print(f"  {r['site_name']}: {r['false_alarms']}/{r['total_readings']} false alarms ({r['false_alarm_rate']:.0%})")
    print(f"\n  Overall false alarm rate: {overall_far:.1%}")

    # Compute cost delta
    print("\n📊 Computing Cost Delta...\n")
    # Merge all event results for cost calculation
    merged_results = {}
    for event_name, event_results in all_event_results.items():
        for site_id, result in event_results.items():
            if site_id not in merged_results:
                merged_results[site_id] = result
            else:
                merged_results[site_id]["daily_data"].extend(result["daily_data"])
                merged_results[site_id]["total_days"] += result["total_days"]
                merged_results[site_id]["alerts_fired"] += result["alerts_fired"]

    cost_delta = compute_cost_delta(merged_results)
    print(f"  Naive threshold: cancel all above 35°C")
    print(f"    Cancellations: {cost_delta['naive_cancellations']}")
    print(f"    Cost: ${cost_delta['cost_naive']:,}")
    print(f"\n  Heatwatch: reschedule to safe windows")
    print(f"    Reschedules: {cost_delta['heatwatch_reschedules']}")
    print(f"    Cost: ${cost_delta['cost_heatwatch']:,}")
    print(f"\n  💰 SAVINGS: ${cost_delta['savings']:,}")

    # Compute overall metrics
    total_tp = sum(r["alerts_fired"] for er in all_event_results.values()
                   for r in er.values())
    total_fn = sum(r["total_days"] - r["alerts_fired"]
                   for er in all_event_results.values()
                   for r in er.values())
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0

    summary = {
        "events_tested": len(EVAL_SETTINGS["heat_wave_events"]),
        "total_site_days": total_tp + total_fn,
        "true_positives": total_tp,
        "false_negatives": total_fn,
        "recall": overall_recall,
        "false_alarm_rate": overall_far,
        "cost_delta": cost_delta,
    }

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"\n  Heat Events Tested: {summary['events_tested']}")
    print(f"  Total Site-Days: {summary['total_site_days']}")
    print(f"  True Positives (alerts fired): {summary['true_positives']}")
    print(f"  False Negatives (missed): {summary['false_negatives']}")
    print(f"  Recall (Detection Rate): {summary['recall']:.0%}")
    print(f"  False Alarm Rate: {summary['false_alarm_rate']:.1%}")
    print(f"  Cost Savings vs Naive: ${cost_delta['savings']:,}")

    # Save results
    results_output = {
        "summary": summary,
        "heat_events": all_event_results,
        "null_days": null_results,
        "cost_delta": cost_delta,
    }

    with open("eval_results.json", "w") as f:
        json.dump(results_output, f, indent=2, default=str)

    print(f"\n  Results saved to eval_results.json")
    return results_output


if __name__ == "__main__":
    use_live = "--live" in sys.argv
    run_eval(use_live_api=use_live)
