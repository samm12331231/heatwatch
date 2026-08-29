"""
Pre-computed hourly temperature data for all 6 Phoenix-area sites.
Based on real FortyGuard API data from July 2023 (heat) and April 2023 (null).

Data provenance per hour:
  - 12:00, 16:00: OBSERVED (FortyGuard API measurement)
  - 05:00-11:00, 17:00-23:00: INTERPOLATED (piecewise linear between anchors + diurnal profile)
"""

from config import SITES

# ============================================================
# HEAT DAY: July 15, 2023 — Phoenix Heat Wave
# OBSERVED data points from FortyGuard API:
#   12:00 PM: 41.1-41.5°C across sites
#   4:00 PM:  42.2-42.4°C across sites
# ============================================================

_HEAT_DAY_MEASURED = {
    "mountain_pointe":  {12: 41.1, 16: 42.3},
    "desert_vista":     {12: 41.2, 16: 42.3},
    "chandler":         {12: 41.5, 16: 42.4},
    "hamilton":         {12: 41.4, 16: 42.2},
    "saguaro":          {12: 41.2, 16: 42.2},
    "corona_del_sol":   {12: 41.4, 16: 42.4},
}

# Diurnal offsets from 12:00 anchor (based on NOAA KPHX hourly patterns)
# Used ONLY for hours outside the measured 12:00-16:00 range
_HEAT_DAY_OFFSETS = {
    5: -12.0, 6: -11.0, 7: -9.5, 8: -7.5, 9: -5.5,
    10: -3.5, 11: -1.5, 12: 0.0, 13: 0.8, 14: 1.3,
    15: 1.6, 16: 1.8, 17: 1.5, 18: 0.8, 19: -0.5,
    20: -2.5, 21: -4.0, 22: -5.5, 23: -6.5,
}

# ============================================================
# NULL DAY: April 10, 2023 — Cool Spring Day
# OBSERVED data points from FortyGuard API:
#   12:00 PM: 32.7-33.6°C across sites
#   4:00 PM:  36.1-36.7°C across sites
# ============================================================

_NULL_DAY_MEASURED = {
    "mountain_pointe":  {12: 33.3, 16: 36.5},
    "desert_vista":     {12: 32.7, 16: 36.3},
    "chandler":         {12: 33.4, 16: 36.7},
    "hamilton":         {12: 32.7, 16: 36.3},
    "saguaro":          {12: 33.2, 16: 36.1},
    "corona_del_sol":   {12: 33.6, 16: 36.7},
}

_NULL_DAY_OFFSETS = {
    5: -10.0, 6: -9.0, 7: -7.5, 8: -6.0, 9: -4.5,
    10: -3.0, 11: -1.5, 12: 0.0, 13: 0.6, 14: 1.0,
    15: 1.3, 16: 1.5, 17: 1.2, 18: 0.5, 19: -0.5,
    20: -2.0, 21: -3.5, 22: -5.0, 23: -6.0,
}


def _interpolate_curve(measured: dict, offsets: dict) -> dict:
    """Build a full 24h temperature curve preserving all measured anchors.

    Uses piecewise linear interpolation between measured points (12:00 and 16:00),
    and the diurnal profile for hours outside the measured range.
    """
    result = {}
    for site_id, site_measured in measured.items():
        curve = {}
        measured_hours = sorted(site_measured.keys())

        for hour in range(5, 24):
            if hour in site_measured:
                # OBSERVED — use actual measurement
                curve[hour] = site_measured[hour]
            elif hour < measured_hours[0]:
                # Before first measurement: use profile from 12:00 anchor
                base = site_measured[measured_hours[0]]
                curve[hour] = round(base + offsets.get(hour, 0), 1)
            elif hour > measured_hours[-1]:
                # After last measurement: use profile from 12:00 anchor
                base = site_measured[measured_hours[0]]
                curve[hour] = round(base + offsets.get(hour, 0), 1)
            else:
                # Between measurements: linear interpolation
                # Find the two bounding measured hours
                for i in range(len(measured_hours) - 1):
                    h1, h2 = measured_hours[i], measured_hours[i + 1]
                    if h1 < hour < h2:
                        t1, t2 = site_measured[h1], site_measured[h2]
                        frac = (hour - h1) / (h2 - h1)
                        curve[hour] = round(t1 + frac * (t2 - t1), 1)
                        break

        result[site_id] = curve
    return result


# Full 24h curves
HEAT_DAY_CURVES = _interpolate_curve(_HEAT_DAY_MEASURED, _HEAT_DAY_OFFSETS)
NULL_DAY_CURVES = _interpolate_curve(_NULL_DAY_MEASURED, _NULL_DAY_OFFSETS)

# Data provenance labels
DATA_PROVENANCE = {
    "heat": {
        "observed_hours": [12, 16],
        "label": "July 15, 2023 — FortyGuard API observed at 12:00 & 16:00, interpolated between",
        "source": "FortyGuard API",
    },
    "null": {
        "observed_hours": [12, 16],
        "label": "April 10, 2023 — FortyGuard API observed at 12:00 & 16:00, interpolated between",
        "source": "FortyGuard API",
    },
}

# Site metadata for map
SITE_INFO = []
for site in SITES:
    SITE_INFO.append({
        "id": site["id"],
        "name": site["name"],
        "short_name": site["name"].replace(" High School", ""),
        "lat": site["lat"],
        "lon": site["lon"],
        "address": site["address"],
    })


# Import the canonical heat index from core_engine (single source of truth)
from core_engine import compute_heat_index as get_heat_index


def get_policy_level(heat_index_c: float) -> str:
    """Classify risk level from heat index.

    NOTE: Current AIA policy (2026-2027) uses WBGT, not heat index.
    This uses heat index as a proxy because FortyGuard provides temperature data,
    not WBGT. In production, on-field WBGT sensors would be the primary gate.
    """
    if heat_index_c >= 38.0:
        return "black"
    elif heat_index_c >= 35.0:
        return "red"
    elif heat_index_c >= 32.0:
        return "orange"
    elif heat_index_c >= 30.0:
        return "yellow"
    return "green"


def get_humidity_for_hour(hour: int) -> float:
    """Time-appropriate humidity estimate for Phoenix.

    NOTE: Morning values raised to 40% per NWS climatology and
    conservative safety practice (Perplexity review recommendation).
    Higher humidity = higher WBGT = more conservative estimate.
    """
    if hour < 11:
        return 40.0  # Conservative morning estimate
    elif hour < 15:
        return 15.0
    return 12.0


def get_all_site_readings(hour: int, day_type: str = "heat") -> list:
    """Get readings for all 6 sites at a given hour."""
    curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES
    provenance = DATA_PROVENANCE[day_type]
    readings = []
    for site in SITE_INFO:
        temp_c = curves[site["id"]].get(hour, 0)
        humidity = get_humidity_for_hour(hour)
        hi_c = get_heat_index(temp_c, humidity)
        level = get_policy_level(hi_c)
        is_observed = hour in provenance["observed_hours"]
        readings.append({
            **site,
            "temp_c": temp_c,
            "temp_f": round(temp_c * 9 / 5 + 32, 1),
            "humidity_pct": humidity,
            "heat_index_c": hi_c,
            "heat_index_f": round(hi_c * 9 / 5 + 32, 1),
            "policy_level": level,
            "alert": level in ("red", "black"),
            "data_provenance": "observed" if is_observed else "interpolated",
        })
    return readings
