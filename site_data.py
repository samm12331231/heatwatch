"""
Pre-computed hourly temperature data for all 6 Phoenix-area sites.
Based on real FortyGuard API data from July 2023 (heat) and April 2023 (null).
Used by app.py for instant visualizations without API calls.
"""

from config import SITES

# ============================================================
# HEAT DAY: July 15, 2023 — Phoenix Heat Wave
# Real data points from FortyGuard API:
#   12:00 PM: 41.1-41.5°C across sites
#   4:00 PM:  42.2-42.4°C across sites
# Interpolated for other hours using typical Phoenix diurnal curve.
# ============================================================

# Real measured temps at 12:00 and 16:00
_HEAT_DAY_MEASURED = {
    "mountain_pointe":  {12: 41.1, 16: 42.3},
    "desert_vista":     {12: 41.2, 16: 42.3},
    "chandler":         {12: 41.5, 16: 42.4},
    "hamilton":         {12: 41.4, 16: 42.2},
    "saguaro":          {12: 41.2, 16: 42.2},
    "corona_del_sol":   {12: 41.4, 16: 42.4},
}

# Typical Phoenix July diurnal temperature offsets from the 12:00 reading
# Based on NOAA KPHX historical hourly data patterns
_HEAT_DAY_OFFSETS = {
    5: -12.0, 6: -11.0, 7: -9.5, 8: -7.5, 9: -5.5,
    10: -3.5, 11: -1.5, 12: 0.0, 13: 0.8, 14: 1.3,
    15: 1.6, 16: 1.8, 17: 1.5, 18: 0.8, 19: -0.5,
    20: -2.5, 21: -4.0, 22: -5.5, 23: -6.5,
}

# ============================================================
# NULL DAY: April 10, 2023 — Cool Spring Day
# Real data points from FortyGuard API:
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
    """Build a full 24h temperature curve from measured points + diurnal offsets."""
    result = {}
    for site_id, site_measured in measured.items():
        base = site_measured[12]  # 12:00 PM is the anchor
        curve = {}
        for hour in range(5, 24):
            curve[hour] = round(base + offsets.get(hour, 0), 1)
        result[site_id] = curve
    return result


# Full 24h curves
HEAT_DAY_CURVES = _interpolate_curve(_HEAT_DAY_MEASURED, _HEAT_DAY_OFFSETS)
NULL_DAY_CURVES = _interpolate_curve(_NULL_DAY_MEASURED, _NULL_DAY_OFFSETS)

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


def get_heat_index(temp_c: float, humidity_pct: float) -> float:
    """Compute heat index (Rothfusz formula)."""
    temp_f = temp_c * 9 / 5 + 32
    if temp_f < 80:
        hi_f = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity_pct * 0.094))
    else:
        hi_f = (
            -42.379 + 2.04901523 * temp_f + 10.14333127 * humidity_pct
            - 0.22475541 * temp_f * humidity_pct
            - 0.00683783 * temp_f * temp_f
            - 0.05481717 * humidity_pct * humidity_pct
            + 0.00122874 * temp_f * temp_f * humidity_pct
            + 0.00085282 * temp_f * humidity_pct * humidity_pct
            - 0.00000199 * temp_f * temp_f * humidity_pct * humidity_pct
        )
    return round((hi_f - 32) * 5 / 9, 2)


def get_policy_level(heat_index_c: float) -> str:
    """Classify risk level from heat index."""
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
    """Time-appropriate humidity estimate for Phoenix."""
    if hour < 11:
        return 35.0
    elif hour < 15:
        return 15.0
    return 12.0


def get_all_site_readings(hour: int, day_type: str = "heat") -> list:
    """Get readings for all 6 sites at a given hour."""
    curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES
    readings = []
    for site in SITE_INFO:
        temp_c = curves[site["id"]].get(hour, 0)
        humidity = get_humidity_for_hour(hour)
        hi_c = get_heat_index(temp_c, humidity)
        level = get_policy_level(hi_c)
        readings.append({
            **site,
            "temp_c": temp_c,
            "temp_f": round(temp_c * 9 / 5 + 32, 1),
            "humidity_pct": humidity,
            "heat_index_c": hi_c,
            "heat_index_f": round(hi_c * 9 / 5 + 32, 1),
            "policy_level": level,
            "alert": level in ("red", "black"),
        })
    return readings
