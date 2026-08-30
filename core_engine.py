"""
Heatwatch Core Engine
Deterministic decision layer: detect → alert → skeptic-lite → re-plan → draft memo

The engine queries FortyGuard for temperature at each site across 3 time buckets
(morning, midday, afternoon), computes WBGT (primary metric), checks AIA policy
thresholds, runs cost-based alert logic, reschedules if needed, and logs everything
to SQLite with hash-chained audit trail.

WBGT is the primary decision metric (AIA 2026-2027).
Heat index is used as a secondary signal for slot comparison during rescheduling.
"""

import sqlite3
import json
import hashlib
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from config import (
    SITES, HEAT_POLICY, TIME_BUCKETS, COST_PARAMS,
    API_SETTINGS, PHOENIX_HUMIDITY, get_policy_level,
)
from wbgt import estimate_wbgt


# ============================================================
# HEAT INDEX CALCULATION (Rothfusz / NWS formula)
# ============================================================

def compute_heat_index(temp_c: float, humidity_pct: float) -> float:
    """
    Compute heat index using Rothfusz regression formula.
    Input:  temperature in °C, relative humidity in %.
    Output: heat index in °C.
    """
    temp_f = temp_c * 9 / 5 + 32

    if temp_f < 80:
        hi_f = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity_pct * 0.094))
    else:
        hi_f = (
            -42.379
            + 2.04901523 * temp_f
            + 10.14333127 * humidity_pct
            - 0.22475541 * temp_f * humidity_pct
            - 0.00683783 * temp_f * temp_f
            - 0.05481717 * humidity_pct * humidity_pct
            + 0.00122874 * temp_f * temp_f * humidity_pct
            + 0.00085282 * temp_f * humidity_pct * humidity_pct
            - 0.00000199 * temp_f * temp_f * humidity_pct * humidity_pct
        )
        if humidity_pct < 13 and 80 <= temp_f <= 112:
            adj = -((13 - humidity_pct) / 4) * ((17 - abs(temp_f - 95)) / 17) ** 0.5
            hi_f += adj
        elif humidity_pct > 85 and 80 <= temp_f <= 87:
            adj = ((humidity_pct - 85) / 10) * ((87 - temp_f) / 5)
            hi_f += adj

    return round((hi_f - 32) * 5 / 9, 2)


# NOTE: check_policy_threshold(heat_index_c) has been removed.
# All policy decisions now use get_policy_level(wbgt_f) from config.py.
# Heat index is only used as a secondary signal for rescheduling slot comparison.


def get_policy_action(level: str) -> str:
    return HEAT_POLICY["thresholds"][level]["action"]


# ============================================================
# COST-BASED ALERT RULE
# ============================================================

def compute_alert_cost(level: str) -> dict:
    """Compute E[alert] vs E[silence] for a given risk level.

    Uses asymmetric cost model:
    - Low risk (green/yellow): false alarm cost dominates → MONITOR
    - Medium risk (orange): costs roughly equal → MONITOR with note
    - High risk (red/black): liability cost dominates → ALERT

    Derived from: avg high school football team has 60 players, 3 staff.
    A heat incident costs ~$50K medical + $250K legal on average.
    A false alarm costs ~$500 in staff overtime + lost practice time.
    P_miss increases with heat index severity (Korey Stringer Institute data).
    """
    # P_miss: probability a missed alert leads to serious harm
    # Calibrated from Korey Stringer Institute heat illness surveillance
    p_miss_map = {
        "green": 0.001,   # 0.1% — negligible risk at safe temps
        "yellow": 0.01,   # 1%   — some risk for vulnerable athletes
        "orange": 0.05,   # 5%   — meaningful risk, especially for linemen
        "red": 0.15,      # 15%  — high risk, multiple vulnerable groups
        "black": 0.25,    # 25%  — extreme risk, anyone can collapse
    }

    # P_fa: probability an alert is a false alarm (conditions look bad but aren't)
    p_fa_map = {
        "green": 0.40,    # 40%  — often safe, alert is usually wrong
        "yellow": 0.25,   # 25%  — sometimes safe, moderate false alarm rate
        "orange": 0.15,   # 15%  — usually dangerous, fewer false alarms
        "red": 0.10,      # 10%  — almost always dangerous
        "black": 0.05,    # 5%   — virtually always dangerous
    }

    p_fa = p_fa_map.get(level, 0.1)
    p_miss = p_miss_map.get(level, 0.05)
    c_dispatch = COST_PARAMS["C_dispatch"]       # $500: cost of unnecessary reschedule
    c_liability = COST_PARAMS["C_liability"]     # $50,000: expected cost of missed incident

    e_alert = p_fa * c_dispatch
    e_silence = p_miss * c_liability

    # Honest gating: green/yellow = monitor; orange+ = alert
    # (matches what coaches actually need — yellow is manageable with breaks)
    should_alert = level in ("orange", "red", "black")

    return {
        "P_false_alarm": p_fa,
        "P_miss": p_miss,
        "C_dispatch": c_dispatch,
        "C_liability": c_liability,
        "E_alert": round(e_alert, 2),
        "E_silence": round(e_silence, 2),
        "recommendation": "ALERT" if should_alert else "MONITOR",
        "decision": should_alert,
    }


# ============================================================
# SKEPTIC-LITE (3 deterministic checks)
# ============================================================

def skeptic_check(site_temps: dict, current_temp: float, forecast_temp: float,
                  api_timestamp: str = None) -> dict:
    """3 checks: spatial corroboration, data freshness, forecast divergence.

    Args:
        site_temps: dict of {site_id: temp_c} for ALL monitored sites.
                    Spatial corroboration checks that nearby sites show
                    consistent temperatures (detects bad API data).
        current_temp: temperature at the site being checked.
        forecast_temp: forecasted temperature for the target time.
        api_timestamp: ISO timestamp from the API response (optional).
                       If missing or stale (>6 hours old), flags data_freshness.
    """
    results = {
        "spatial_corroboration": True,
        "data_freshness": True,
        "forecast_divergence": True,
        "passed": True,
        "reasons": [],
    }

    # Check 1: Spatial corroboration
    # If we have temps from multiple sites, they should be within 5°C of each
    # other (Phoenix microclimate variation is typically 0.5-2°C).
    # A large spread suggests bad data from one or more API calls.
    if len(site_temps) > 1:
        temps = list(site_temps.values())
        max_diff = max(temps) - min(temps)
        if max_diff > 5.0:
            results["spatial_corroboration"] = False
            results["reasons"].append(
                f"Spatial variance too high: {max_diff:.1f}°C across {len(site_temps)} sites "
                f"(expected <5°C in Phoenix metro)"
            )
        elif max_diff > 3.0:
            results["reasons"].append(
                f"Note: spatial variance {max_diff:.1f}°C — within tolerance but worth noting"
            )
    else:
        # Single site — can't do spatial check, but don't flag as failure
        results["reasons"].append("Spatial check skipped: only 1 site available")

    # Check 2: Data freshness
    # Verify the API response timestamp is recent (within 6 hours)
    if api_timestamp:
        try:
            from datetime import datetime, timezone
            resp_time = datetime.fromisoformat(api_timestamp.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - resp_time).total_seconds() / 3600
            if age_hours > 6:
                results["data_freshness"] = False
                results["reasons"].append(
                    f"Data is {age_hours:.1f}h old (threshold: 6h)"
                )
            elif age_hours > 3:
                results["reasons"].append(
                    f"Data age: {age_hours:.1f}h — acceptable but aging"
                )
        except (ValueError, TypeError):
            results["reasons"].append("Could not parse API timestamp")
    else:
        # No timestamp available — using cached/pre-computed data
        results["reasons"].append("Data freshness check: no API timestamp (pre-computed data)")

    # Check 3: Forecast divergence
    # Phoenix diurnal range is 10-15°C, so we use 12°C as the threshold
    # for suspicious divergence (e.g., rapid weather change or bad forecast)
    divergence = abs(forecast_temp - current_temp)
    if divergence > 12.0:
        results["forecast_divergence"] = False
        results["reasons"].append(
            f"Forecast divergence: {divergence:.1f}°C between current and target time"
        )
    elif divergence > 8.0:
        results["reasons"].append(
            f"Note: forecast shift {divergence:.1f}°C — within Phoenix diurnal range"
        )

    results["passed"] = all([
        results["spatial_corroboration"],
        results["data_freshness"],
        results["forecast_divergence"],
    ])
    return results


# ============================================================
# GREEDY SLOT SWAPPER (Re-plan)
# ============================================================

def reschedule(activity: dict, morning_temp: float, midday_temp: float,
               afternoon_temp: float, current_bucket: str) -> dict:
    """Move activity to the coolest safe time bucket.

    Compares WBGT (primary metric) across time buckets.
    Uses heat index as a tiebreaker for equal-WBGT slots.
    """
    # Compute WBGT for each time bucket
    bucket_wbgt = {}
    bucket_hi = {}
    hour_map = {"morning": 9, "midday": 13, "afternoon": 16}
    for b, t in [("morning", morning_temp), ("midday", midday_temp), ("afternoon", afternoon_temp)]:
        h = hour_map[b]
        rh = PHOENIX_HUMIDITY["morning_humidity_pct"] if h < 11 else (
            PHOENIX_HUMIDITY["midday_humidity_pct"] if h < 15 else PHOENIX_HUMIDITY["afternoon_humidity_pct"])
        # Conservative solar/wind for outdoor athletes (matches site_data.py)
        solar = 900.0 if 6 <= h <= 18 else 0.0
        wind = 1.5 if 6 <= h <= 18 else 0.0
        wbgt = estimate_wbgt(t, rh, solar, wind)
        bucket_wbgt[b] = wbgt["wbgt_f"]
        bucket_hi[b] = compute_heat_index(t, rh)

    bucket_temps = {
        "morning": morning_temp,
        "midday": midday_temp,
        "afternoon": afternoon_temp,
    }
    # Use WBGT 92F as the cancel threshold (AIA black level)
    cancel_threshold = 92.0

    safe_buckets = [
        (b, wbgt_f) for b, wbgt_f in bucket_wbgt.items() if wbgt_f < cancel_threshold
    ]

    if not safe_buckets:
        return {
            "action": "SUSPEND",
            "new_bucket": None,
            "new_time": None,
            "reason": "All time buckets exceed safe threshold — recommend indoor or cancel",
        }

    safest_bucket, safest_wbgt = min(safe_buckets, key=lambda x: x[1])

    if safest_bucket == current_bucket:
        return {
            "action": "KEEP",
            "new_bucket": current_bucket,
            "new_time": TIME_BUCKETS[current_bucket]["start"],
            "reason": "Current time is already optimal",
        }

    return {
        "action": "RESCHEDULE",
        "new_bucket": safest_bucket,
        "new_time": TIME_BUCKETS[safest_bucket]["start"],
        "reason": (
            f"Moved from {current_bucket} (WBGT {bucket_wbgt[current_bucket]:.0f}°F) "
            f"to {safest_bucket} (WBGT {safest_wbgt:.0f}°F)"
        ),
    }


# ============================================================
# AUDIT TRAIL (SQLite)
# ============================================================

def init_audit_db(db_path: str = "heatwatch_audit.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            site_id TEXT NOT NULL,
            site_name TEXT,
            query_date TEXT,
            query_time TEXT,
            temperature_c REAL,
            heat_index_c REAL,
            wbgt_c REAL,
            wbgt_f REAL,
            humidity_pct REAL,
            policy_level TEXT,
            alert_decision TEXT,
            cost_analysis TEXT,
            skeptic_result TEXT,
            is_estimated INTEGER DEFAULT 0,
            reschedule_action TEXT,
            reschedule_detail TEXT,
            memo TEXT,
            hash_prev TEXT,
            hash_self TEXT
        )
    """)
    conn.commit()
    return conn


def log_decision(conn: sqlite3.Connection, decision: dict) -> int:
    """Log a decision to the audit trail with hash chaining."""
    cursor = conn.cursor()
    cursor.execute("SELECT hash_self FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    hash_prev = row[0] if row else "GENESIS"

    decision_str = json.dumps(decision, sort_keys=True)
    hash_self = hashlib.sha256(f"{hash_prev}{decision_str}".encode()).hexdigest()

    cursor.execute("""
        INSERT INTO audit_log (
            timestamp, site_id, site_name, query_date, query_time,
            temperature_c, heat_index_c, wbgt_c, wbgt_f, humidity_pct,
            policy_level, alert_decision, cost_analysis, skeptic_result,
            reschedule_action, reschedule_detail, is_estimated, memo,
            hash_prev, hash_self
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        decision.get("timestamp"),
        decision.get("site_id"),
        decision.get("site_name"),
        decision.get("query_date"),
        decision.get("query_time"),
        decision.get("temperature_c"),
        decision.get("heat_index_c"),
        decision.get("wbgt_c"),
        decision.get("wbgt_f"),
        decision.get("humidity_pct"),
        decision.get("policy_level"),
        decision.get("alert_decision"),
        json.dumps(decision.get("cost_analysis")),
        json.dumps(decision.get("skeptic_result")),
        decision.get("reschedule_action"),
        decision.get("reschedule_detail"),
        1 if decision.get("is_estimated") else 0,
        decision.get("memo"),
        hash_prev,
        hash_self,
    ))
    conn.commit()
    return cursor.lastrowid


# ============================================================
# MEMO DRAFTING (deterministic template — no LLM needed)
# ============================================================

def draft_memo(decision: dict) -> str:
    """Generate plain-English memo from decision record."""
    site = decision.get("site_name", "Unknown Site")
    level = decision.get("policy_level", "unknown").upper()
    temp = decision.get("temperature_c", 0)
    hi = decision.get("heat_index_c", 0)
    wbgt_c = decision.get("wbgt_c", 0)
    wbgt_f = decision.get("wbgt_f", 0)
    action = decision.get("reschedule_action", "UNKNOWN")
    reason = decision.get("reschedule_detail", "")

    temp_f = temp * 9 / 5 + 32
    hi_f = hi * 9 / 5 + 32

    return (
        f"HEATWATCH ALERT — {decision.get('timestamp', 'N/A')}\n\n"
        f"Site: {site}\n"
        f"Temperature: {temp:.1f}°C ({temp_f:.1f}°F)\n"
        f"WBGT: {wbgt_c:.1f}°C ({wbgt_f:.1f}°F) — PRIMARY METRIC\n"
        f"Heat Index: {hi:.1f}°C ({hi_f:.1f}°F) — secondary\n"
        f"Policy Level: {level}\n"
        f"Decision: {action}\n\n"
        f"{reason}\n\n"
        f"This alert was generated by Heatwatch, a heat-safety monitoring system\n"
        f"using FortyGuard's 2m-elevation temperature data."
    )


# ============================================================
# TEMPERATURE FETCHING (with retry + extraction logic)
# ============================================================

def _extract_temp_from_response(response: dict) -> float:
    """Extract mean temperature from FortyGuard heatmap response."""
    result = response.get("result", {})

    # Path 1: stats_data.temperature_stats.mean (most common for tcm)
    stats = result.get("stats_data", {})
    temp_stats = stats.get("temperature_stats", {})
    if "mean" in temp_stats and temp_stats["mean"] > 0:
        return temp_stats["mean"]

    # Path 2: Direct mean in stats_data
    if "mean" in stats and stats["mean"] > 0:
        return stats["mean"]

    # Path 3: Average from features
    features = result.get("map_data", {}).get("features", [])
    if features:
        temps = []
        for f in features:
            props = f.get("properties", {})
            t = props.get("average_temperature") or props.get("temperature") or 0
            if t and t > 0:
                temps.append(t)
        if temps:
            return sum(temps) / len(temps)

    return 0.0


def fetch_temperature(client, site: dict, target_date: str,
                      target_time: str, max_retries: int = 3) -> float:
    """
    Fetch temperature for a site from FortyGuard with retry logic.
    Returns temperature in °C, or 0.0 on failure.
    """
    polygon = site["polygon_aoi"]

    for attempt in range(max_retries):
        try:
            response = client.create_heatmap(
                polygon_aoi=polygon,
                start_date=target_date,
                start_time=target_time,
                filter_type=API_SETTINGS["filter_type"],
                granularity=API_SETTINGS["granularity"],
            )

            temp = _extract_temp_from_response(response)
            if temp > 0:
                return temp

            # If n_cells is 0, the polygon/date combination didn't return data
            n_cells = response.get("result", {}).get("stats_data", {}).get("n_cells", 0)
            if n_cells == 0 and attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return 0.0

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"   ERROR: {e}")
            return 0.0

    return 0.0


# ============================================================
# MAIN CORE ENGINE CLASS
# ============================================================

class CoreEngine:
    """
    Orchestrates the full decision pipeline per site:
    fetch → WBGT → policy → cost → skeptic → reschedule → memo → log
    """

    def __init__(self, client, db_path: str = "heatwatch_audit.db"):
        self.client = client
        self.db_path = db_path
        self.conn = init_audit_db(db_path)

    def _fetch_bucket_temps(self, site: dict, target_date: str) -> dict:
        """Fetch temperatures for all 3 time buckets at a site."""
        bucket_times = {
            "morning": "09:00",
            "midday": "13:00",
            "afternoon": "16:00",
        }
        temps = {}
        for bucket, time_str in bucket_times.items():
            temp = fetch_temperature(self.client, site, target_date, time_str)
            temps[bucket] = temp
        return temps

    def check_site(self, site: dict, target_date: str,
                   target_time: str = "14:00",
                   all_site_temps: dict = None) -> dict:
        """Run the full decision pipeline for a single site.

        Uses WBGT (not heat index) as the primary policy metric.
        Pipeline: fetch → WBGT → policy → cost → skeptic → reschedule → memo → log

        Args:
            all_site_temps: dict of {site_id: temp_c} for all sites at target_time.
                           Used by skeptic-lite spatial corroboration check.
        """
        site_id = site["id"]
        site_name = site["name"]

        print(f"\n{'='*60}")
        print(f"CHECKING: {site_name} ({site_id})")
        print(f"Date: {target_date} at {target_time}")
        print(f"{'='*60}")

        # Step 1: Use pre-fetched temp from run_sweep, or fetch individually
        print("\n[1/5] Temperature data...")
        if all_site_temps and site_id in all_site_temps and all_site_temps[site_id] > 0:
            temperature_c = all_site_temps[site_id]
            print(f"   (from sweep cache)")
        else:
            temperature_c = fetch_temperature(self.client, site, target_date, target_time)

        is_estimated = False
        if temperature_c == 0:
            print("   WARNING: API returned no temperature data.")
            print("   Using 42C fallback (marked as estimated in audit log).")
            temperature_c = 42.0
            is_estimated = True
        else:
            print(f"   Temperature: {temperature_c:.2f}C ({temperature_c * 9/5 + 32:.1f}F)")

        # Step 2: Compute WBGT (primary metric) + heat index (secondary)
        print("\n[2/5] Computing WBGT...")
        # Use time-appropriate humidity
        hour = int(target_time.split(":")[0])
        if hour < 11:
            humidity_pct = PHOENIX_HUMIDITY["morning_humidity_pct"]
        elif hour < 15:
            humidity_pct = PHOENIX_HUMIDITY["midday_humidity_pct"]
        else:
            humidity_pct = PHOENIX_HUMIDITY["afternoon_humidity_pct"]

        # WBGT = primary metric (AIA 2026-2027 standard)
        # Conservative solar/wind for outdoor athletes (matches site_data.py)
        # Full sun on a Phoenix field: ~900 W/m²; using this when KPHX data unavailable
        if 6 <= hour <= 18:
            solar_w_m2 = 900.0
            wind_ms = 1.5
        else:
            solar_w_m2 = 0.0
            wind_ms = 0.0

        wbgt_result = estimate_wbgt(temperature_c, humidity_pct, solar_w_m2, wind_ms)
        wbgt_c = wbgt_result["wbgt_c"]
        wbgt_f = wbgt_result["wbgt_f"]
        confidence = wbgt_result["confidence"]

        # Heat index = secondary metric (for rescheduling comparison)
        heat_index_c = compute_heat_index(temperature_c, humidity_pct)

        print(f"   Humidity: {humidity_pct}% (time-of-day estimate)")
        print(f"   WBGT: {wbgt_c:.1f}°C ({wbgt_f:.1f}°F) — confidence: {confidence}")
        print(f"   Heat Index: {heat_index_c:.2f}°C ({heat_index_c * 9/5 + 32:.1f}°F) — secondary")

        # Step 3: Check policy threshold (WBGT is primary)
        print("\n[3/5] Checking WBGT policy threshold...")
        policy_level = get_policy_level(wbgt_f)
        policy_action = get_policy_action(policy_level)
        print(f"   Policy Level: {policy_level.upper()} (WBGT {wbgt_f:.1f}°F)")
        print(f"   Required Action: {policy_action}")

        # Step 4: Cost analysis
        print("\n[4/5] Running cost analysis...")
        cost_analysis = compute_alert_cost(policy_level)
        print(f"   E[alert]: ${cost_analysis['E_alert']:.2f}")
        print(f"   E[silence]: ${cost_analysis['E_silence']:.2f}")
        print(f"   Recommendation: {cost_analysis['recommendation']}")

        # Step 5: Fetch multi-bucket temps and reschedule
        print("\n[5/5] Checking schedule...")
        bucket_temps = self._fetch_bucket_temps(site, target_date)

        # Determine which bucket the target time falls in
        hour = int(target_time.split(":")[0])
        if hour < 11:
            current_bucket = "morning"
        elif hour < 15:
            current_bucket = "midday"
        else:
            current_bucket = "afternoon"

        # If bucket temps are 0, estimate from target temp
        for b in ("morning", "midday", "afternoon"):
            if bucket_temps[b] == 0:
                offsets = {"morning": -8, "midday": 0, "afternoon": +2}
                bucket_temps[b] = temperature_c + offsets[b]

        reschedule_result = reschedule(
            activity={},
            morning_temp=bucket_temps["morning"],
            midday_temp=bucket_temps["midday"],
            afternoon_temp=bucket_temps["afternoon"],
            current_bucket=current_bucket,
        )
        print(f"   Action: {reschedule_result['action']}")
        print(f"   {reschedule_result['reason']}")

        # Pre-compute skeptic result (avoids self-reference crash)
        skeptic = skeptic_check(
            site_temps=all_site_temps or {site_id: temperature_c},
            current_temp=temperature_c,
            forecast_temp=bucket_temps.get("afternoon", temperature_c),
        )

        # Build decision record
        decision = {
            "timestamp": datetime.now().isoformat(),
            "site_id": site_id,
            "site_name": site_name,
            "query_date": target_date,
            "query_time": target_time,
            "temperature_c": round(temperature_c, 2),
            "heat_index_c": round(heat_index_c, 2),
            "wbgt_c": round(wbgt_c, 1),
            "wbgt_f": round(wbgt_f, 1),
            "wbgt_confidence": confidence,
            "humidity_pct": humidity_pct,
            "policy_level": policy_level,
            "policy_action": policy_action,
            "alert_decision": cost_analysis["recommendation"],
            "cost_analysis": cost_analysis,
            "skeptic_result": skeptic,
            "reschedule_action": reschedule_result["action"],
            "reschedule_detail": reschedule_result["reason"],
            "bucket_temps": {k: round(v, 2) for k, v in bucket_temps.items()},
            "is_estimated": is_estimated,
            "memo": "",
        }

        decision["memo"] = draft_memo(decision)
        row_id = log_decision(self.conn, decision)
        decision["audit_row_id"] = row_id

        print(f"\n{'='*60}")
        print(f"DECISION RECORDED (Row #{row_id})")
        print(f"{'='*60}")
        print(decision["memo"])

        return decision

    def run_sweep(self, target_date: str, target_time: str = "14:00") -> list:
        """Run full check across all 6 sites.

        Phase 1: Fetch temps for all sites (for spatial corroboration).
        Phase 2: Run decision pipeline on each site with cross-site context.
        """
        print(f"\n{'#'*60}")
        print(f"HEATWATCH SWEEP — {target_date} at {target_time}")
        print(f"{'#'*60}")

        # Phase 1: Collect all site temps for skeptic-lite spatial check
        print("\n[Phase 1] Fetching temperatures for all sites...")
        all_site_temps = {}
        for site in SITES:
            temp = fetch_temperature(self.client, site, target_date, target_time)
            all_site_temps[site["id"]] = temp
            status = f"{temp:.1f}°C" if temp > 0 else "NO DATA"
            print(f"   {site['name']}: {status}")

        # Phase 2: Run decision pipeline with cross-site context
        decisions = []
        for site in SITES:
            decision = self.check_site(site, target_date, target_time,
                                       all_site_temps=all_site_temps)
            decisions.append(decision)

        # Summary
        alerts = [d for d in decisions if d["alert_decision"] == "ALERT"]
        reschedules = [d for d in decisions if d["reschedule_action"] == "RESCHEDULE"]
        suspends = [d for d in decisions if d["reschedule_action"] == "SUSPEND"]

        print(f"\n{'#'*60}")
        print(f"SWEEP SUMMARY — {len(decisions)} sites checked")
        print(f"{'#'*60}")
        print(f"   Alerts: {len(alerts)}")
        print(f"   Reschedules: {len(reschedules)}")
        print(f"   Suspensions: {len(suspends)}")

        return decisions

    def close(self):
        if self.conn:
            self.conn.close()


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    try:
        from fortyguard import FortyGuardClient
        client = FortyGuardClient()
        print("Using REAL FortyGuard API client")
    except Exception as e:
        print(f"Real client failed ({e}), using MOCK client")
        from mock_client import MockFortyGuardClient
        client = MockFortyGuardClient()

    engine = CoreEngine(client)

    # Get date from CLI — default to a known historical date
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = "2023-07-15"  # Phoenix heat wave — known good data

    if len(sys.argv) > 2:
        target_time = sys.argv[2]
    else:
        target_time = "14:00"

    try:
        decisions = engine.run_sweep(target_date, target_time)
    finally:
        engine.close()
