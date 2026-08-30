"""
Simplified Wet Bulb Globe Temperature (WBGT) estimation.

WBGT is the standard metric for athletic heat stress (NCAA, NATA, AIA).
It combines: temperature, humidity, solar radiation, and wind.

Full WBGT requires: wet bulb temp (Tw), black globe temp (Tg), and air temp (Ta).
This module estimates WBGT from available data when direct sensors aren't available.

Reference: NWS, NCAA Heat acclimatization guidelines, AIA 2026-2027 policies.
"""

import math


def estimate_wbgt(temp_c: float, humidity_pct: float,
                  solar_w_m2: float = 0, wind_speed_ms: float = 0) -> dict:
    """Estimate WBGT from available environmental data.

    Uses the simplified Liljegren model for outdoor WBGT estimation.
    When solar/wind data is unavailable, falls back to a temperature-humidity
    approximation that is conservative (overestimates risk).

    Args:
        temp_c: Air temperature in °C
        humidity_pct: Relative humidity in %
        solar_w_m2: Solar radiation in W/m² (0 if unknown)
        wind_speed_ms: Wind speed in m/s (0 if unknown)

    Returns:
        dict with wbgt_c, wbgt_f, risk_level, confidence
    """
    # Step 1: Estimate wet bulb temperature (Tw)
    # Stull formula: Tw ≈ T * atan(0.151977 * sqrt(RH + 8.313659))
    #              + atan(T + RH) - atan(RH - 1.676331)
    #              + 0.00391838 * sqrt(RH^3) * atan(0.023101 * RH) - 4.686035
    rh = humidity_pct
    tw_c = (temp_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + math.atan(temp_c + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * (rh ** 1.5) * math.atan(0.023101 * rh)
            - 4.686035)

    # Step 2: Estimate black globe temperature (Tg)
    # Bernard et al. approximation: Tg = Ta + 0.0084*Q - 0.6*V
    # where Q = solar radiation (W/m²), V = wind speed (m/s)
    # At 900 W/m², 2 m/s: Tg = Ta + 7.6 - 1.2 = Ta + 6.4°C (realistic)
    # No solar: conservative estimate of Ta + 5°C (moderate sun)
    if solar_w_m2 > 0:
        tg_c = temp_c + 0.0084 * solar_w_m2 - 0.6 * wind_speed_ms
        # Cap globe temp boost at 15°C above air temp (physical limit)
        tg_c = min(tg_c, temp_c + 15.0)
    else:
        tg_c = temp_c + 5.0

    # Step 3: WBGT = 0.7 * Tw + 0.2 * Tg + 0.1 * Ta
    wbgt_c = 0.7 * tw_c + 0.2 * tg_c + 0.1 * temp_c
    wbgt_f = wbgt_c * 9 / 5 + 32

    # Confidence based on data availability
    has_solar = solar_w_m2 > 0
    has_wind = wind_speed_ms > 0
    if has_solar and has_wind:
        confidence = "high"
    elif has_solar or has_wind:
        confidence = "moderate"
    else:
        confidence = "low (estimated — solar/wind data unavailable)"

    # Risk level based on AIA/WBGT thresholds (°F)
    # AIA 2026-2027: WBGT > 92°F = no outdoor workout
    if wbgt_f >= 92.0:
        risk_level = "black"
        action = "NO OUTDOOR WORKOUT"
    elif wbgt_f >= 90.0:
        risk_level = "red"
        action = "Limit to 30 min, mandatory breaks, no equipment"
    elif wbgt_f >= 87.0:
        risk_level = "orange"
        action = "Limit to 60 min, additional water breaks"
    elif wbgt_f >= 82.0:
        risk_level = "yellow"
        action = "Increase rest breaks, monitor athletes"
    else:
        risk_level = "green"
        action = "Standard practice"

    return {
        "wbgt_c": round(wbgt_c, 1),
        "wbgt_f": round(wbgt_f, 1),
        "tw_c": round(tw_c, 1),
        "tg_c": round(tg_c, 1),
        "temp_c": temp_c,
        "humidity_pct": humidity_pct,
        "solar_w_m2": solar_w_m2,
        "wind_speed_ms": wind_speed_ms,
        "risk_level": risk_level,
        "action": action,
        "confidence": confidence,
        "note": ("WBGT estimated from temperature + humidity" if not has_solar
                 else "WBGT estimated with solar data"),
    }


def wbgt_from_kphx(temp_c: float, humidity_pct: float,
                   solar_w_m2: float = 0, wind_speed_ms: float = 0) -> dict:
    """Convenience wrapper that returns WBGT for KPHX-style inputs."""
    wind_ms = wind_speed_ms / 3.6 if wind_speed_ms > 20 else wind_speed_ms
    return estimate_wbgt(temp_c, humidity_pct, solar_w_m2, wind_ms)
