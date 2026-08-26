"""
Day 1 Probes — Run these FIRST before building anything.
Tests: 1) Forecast anchoring, 2) Humidity availability, 3) Spatial variance
"""

import os
import sys
from dotenv import load_dotenv
from fortyguard import FortyGuardClient

load_dotenv()

# Probe 1: Can we get a forecast heatmap?
print("=" * 60)
print("PROBE 1: Forecast Anchoring (Create Heatmap with future date)")
print("=" * 60)

try:
    client = FortyGuardClient()
    response = client.create_heatmap(
        polygon_aoi={
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.9885, 33.3885],
                        [-111.9855, 33.3885],
                        [-111.9855, 33.3895],
                        [-111.9885, 33.3895],
                        [-111.9885, 33.3885],
                    ]]
                }
            }]
        },
        start_date="2026-08-21",
        start_time="14:00",
        filter_type=1,
        granularity=100,
    )
    print(f"✓ Forecast request succeeded")
    print(f"  Activity ID: {response.get('activity_id', 'N/A')}")
    print(f"  Result keys: {list(response.get('result', {}).keys())}")
    if 'stats_data' in response.get('result', {}):
        stats = response['result']['stats_data']
        print(f"  Temperature range: {stats.get('min', 'N/A')} - {stats.get('max', 'N/A')} °C")
except Exception as e:
    print(f"✗ FAILED: {e}")
    sys.exit(1)

# Probe 2: Does environmental_parameters return humidity?
print("\n" + "=" * 60)
print("PROBE 2: Humidity Availability (Environmental Parameters)")
print("=" * 60)

try:
    response = client.environmental_parameters(
        point={"lat": 33.3890, "lon": -111.9870},
        date_time={
            "start_date": "2026-08-21",
            "start_time": "14:00",
        }
    )
    result = response.get('result', {})
    print(f"✓ Environmental parameters request succeeded")
    print(f"  Result keys: {list(result.keys())}")
    
    # Check for humidity
    humidity_key = None
    for key in ['relative_humidity', 'humidity', 'relative_humidity_percent']:
        if key in result:
            humidity_key = key
            break
    
    if humidity_key:
        print(f"  Humidity found: {key} = {result[key]}")
    else:
        print(f"  ⚠ No humidity field found. Available: {list(result.keys())}")
        print(f"  → Will need to use regional NWS humidity approximation")
        
except Exception as e:
    print(f"✗ FAILED: {e}")

# Probe 3: Spatial variance (5 points within 1km)
print("\n" + "=" * 60)
print("PROBE 3: Spatial Variance (Microclimate Reality Test)")
print("=" * 60)

# 5 points within 1km of Mountain Pointe HS
test_points = [
    {"name": "Football Field", "lat": 33.3890, "lon": -111.9870},
    {"name": "Parking Lot (S)", "lat": 33.3880, "lon": -111.9870},
    {"name": "Grassy Area (E)", "lat": 33.3890, "lon": -111.9855},
    {"name": "Building Roof", "lat": 33.3895, "lon": -111.9865},
    {"name": "Tree Shade (W)", "lat": 33.3888, "lon": -111.9880},
]

temps = []
for point in test_points:
    try:
        response = client.environmental_parameters(
            point={"lat": point["lat"], "lon": point["lon"]},
            date_time={
                "start_date": "2026-08-21",
                "start_time": "14:00",
            }
        )
        temp = response.get('result', {}).get('temperature_celsius', None)
        if temp is not None:
            temps.append(temp)
            print(f"  {point['name']}: {temp} °C")
        else:
            print(f"  {point['name']}: No temperature in response")
    except Exception as e:
        print(f"  {point['name']}: FAILED - {e}")

if temps:
    variance = max(temps) - min(temps)
    print(f"\n  Temperature range: {min(temps)} - {max(temps)} °C")
    print(f"  Variance (ΔT): {variance:.2f} °C")
    
    if variance > 0.5:
        print(f"  ✓ PASSED: ΔT > 0.5°C — microclimate claim lives")
    else:
        print(f"  ⚠ WARNING: ΔT ≤ 0.5°C — microclimate claim may be weak")
        print(f"  → Story shifts to lead-time + documentation + re-planning")
else:
    print(f"  ✗ No temperature data collected")

print("\n" + "=" * 60)
print("DAY 1 PROBES COMPLETE")
print("=" * 60)
