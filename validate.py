#!/usr/bin/env python3
"""
Heatwatch Validation Script
Reproduces key metrics in <60 seconds. Run: python validate.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import get_policy_level, PHOENIX_HUMIDITY
from site_data import SITE_INFO, HEAT_DAY_CURVES, NULL_DAY_CURVES, get_humidity_for_hour
from wbgt import estimate_wbgt

def main():
    print("=" * 60)
    print("HEATWATCH VALIDATION — Key Metrics")
    print("=" * 60)
    errors = []

    # 1. Threshold consistency
    print("\n[1] Threshold consistency")
    thresholds = [
        (81.9, "green"), (82.0, "yellow"), (86.9, "yellow"),
        (87.0, "orange"), (89.9, "orange"), (90.0, "red"),
        (91.9, "red"), (92.0, "black"), (100.0, "black"),
    ]
    for wbgt_f, expected in thresholds:
        got = get_policy_level(wbgt_f)
        status = "OK" if got == expected else "FAIL"
        if status == "FAIL":
            errors.append(f"get_policy_level({wbgt_f}) = {got}, expected {expected}")
        print(f"  WBGT {wbgt_f:6.1f}F -> {got:8s} (expected {expected:8s}) [{status}]")

    # 2. WBGT sanity (Phoenix heat wave)
    print("\n[2] WBGT sanity (July 15, 2023 heat wave)")
    curves = HEAT_DAY_CURVES
    for site in SITE_INFO:
        site_id = site["id"]
        for hour in [7, 12, 16]:
            temp_c = curves[site_id].get(hour, 0)
            rh = get_humidity_for_hour(hour)
            solar = 900.0 if 6 <= hour <= 18 else 0.0
            wind = 1.5 if 6 <= hour <= 18 else 0.0
            wbgt = estimate_wbgt(temp_c, rh, solar, wind)
            level = get_policy_level(wbgt["wbgt_f"])
            temp_f = temp_c * 9/5 + 32
            print(f"  {site['short_name']:20s} {hour:02d}:00  Air {temp_f:5.1f}F  WBGT {wbgt['wbgt_f']:5.1f}F  {level.upper()}")
            if hour == 16 and level == "green":
                errors.append(f"{site['short_name']} at 16:00 is GREEN — should be YELLOW+")

    # 3. Null day check
    print("\n[3] Null day (safe conditions)")
    null_curves = NULL_DAY_CURVES
    all_safe = True
    for site in SITE_INFO:
        temp_c = null_curves[site["id"]].get(12, 0)
        rh = get_humidity_for_hour(12)
        wbgt = estimate_wbgt(temp_c, rh, 900.0, 1.5)
        level = get_policy_level(wbgt["wbgt_f"])
        if level in ("red", "black"):
            all_safe = False
            errors.append(f"Null day {site['short_name']} at 12:00 is {level.upper()}")
        print(f"  {site['short_name']:20s} 12:00  WBGT {wbgt['wbgt_f']:5.1f}F  {level.upper()}")
    if all_safe:
        print("  -> All null-day readings are below RED threshold")

    # 4. Cost model
    print("\n[4] Cost model")
    c_dispatch = 500
    c_liability = 50000
    for level in ["green", "yellow", "orange", "red", "black"]:
        from config import HEAT_POLICY
        p_miss_map = {"green": 0.001, "yellow": 0.01, "orange": 0.05, "red": 0.15, "black": 0.25}
        p_fa_map = {"green": 0.40, "yellow": 0.25, "orange": 0.15, "red": 0.10, "black": 0.05}
        e_alert = p_fa_map[level] * c_dispatch
        e_silence = p_miss_map[level] * c_liability
        should_alert = level in ("orange", "red", "black")
        decision = "ALERT" if should_alert else "MONITOR"
        print(f"  {level:8s}  E[alert]={e_alert:7.1f}  E[silence]={e_silence:7.1f}  -> {decision}")

    # 5. Audit trail integrity
    print("\n[5] Audit trail")
    db_path = os.path.join(os.path.dirname(__file__), "heatwatch_audit.db")
    if os.path.exists(db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()
        print(f"  DB exists with {rows} records")
    else:
        print("  No DB found (run Safety Check to create)")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} issues found")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
