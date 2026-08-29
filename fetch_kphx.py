"""
Fetch real KPHX (Phoenix Sky Harbor) historical temperature data
from Open-Meteo's free API — no API key required.

Saves to data/kphx_history.json for use by the weather comparison tab.
"""

import json
import requests
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# KPHX coordinates
KPHX_LAT = 33.4373
KPHX_LON = -112.0078

# Dates we have FortyGuard data for
DATES = {
    "heat": {"start": "2023-07-15", "end": "2023-07-15", "label": "July 2023 Heat Wave"},
    "null": {"start": "2023-04-10", "end": "2023-04-10", "label": "April 2023 Null Day"},
}


def fetch_hourly_temperatures(date_str: str) -> dict:
    """Fetch hourly temperatures for a single date from Open-Meteo."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": KPHX_LAT,
        "longitude": KPHX_LON,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation",
        "timezone": "America/Phoenix",
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    result = {}
    for i, t in enumerate(times):
        hour = int(t.split("T")[1].split(":")[0])
        result[hour] = {
            "temp_c": hourly.get("temperature_2m", [None])[i],
            "humidity_pct": hourly.get("relative_humidity_2m", [None])[i],
            "wind_speed_kmh": hourly.get("wind_speed_10m", [None])[i],
            "solar_w_m2": hourly.get("shortwave_radiation", [None])[i],
        }

    return result


def main():
    print("=" * 60)
    print("KPHX HISTORICAL DATA FETCHER")
    print("=" * 60)

    all_data = {}
    for key, info in DATES.items():
        print(f"\nFetching: {info['label']} ({info['start']})...")
        try:
            hourly = fetch_hourly_temperatures(info["start"])
            all_data[key] = {
                "label": info["label"],
                "date": info["start"],
                "source": "Open-Meteo Archive API (ERA5 reanalysis)",
                "station": "KPHX (33.44°N, 112.01°W)",
                "hourly": hourly,
            }
            # Print summary
            for h in [7, 12, 16]:
                if h in hourly:
                    d = hourly[h]
                    print(f"  {h:02d}:00 — {d['temp_c']:.1f}°C ({d['temp_c']*9/5+32:.0f}°F), "
                          f"RH: {d['humidity_pct']:.0f}%, wind: {d['wind_speed_kmh']:.1f} km/h, "
                          f"solar: {d['solar_w_m2']:.0f} W/m²")
            print("  ✓ OK")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            all_data[key] = {"error": str(e)}

    out_path = DATA_DIR / "kphx_history.json"
    with open(out_path, "w") as f:
        json.dump(all_data, f, indent=2)

    print(f"\nSaved to {out_path}")
    return all_data


if __name__ == "__main__":
    main()
