"""
Heatwatch Configuration
6 Phoenix-area high school football fields

Each site has a unique polygon_aoi centered on the school's coordinates.
Polygons are ~2km × 2km bounding boxes (large enough for the API to return
tiles at 100m granularity, small enough to capture site-specific microclimate).
"""

# --- Sites (football fields / practice facilities) ---
SITES = [
    {
        "id": "mountain_pointe",
        "name": "Mountain Pointe High School",
        "address": "4200 E Questa Rd, Phoenix, AZ 85044",
        "lat": 33.3890,
        "lon": -111.9870,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.9970, 33.3790],
                        [-111.9770, 33.3790],
                        [-111.9770, 33.3990],
                        [-111.9970, 33.3990],
                        [-111.9970, 33.3790],
                    ]]
                }
            }]
        }
    },
    {
        "id": "desert_vista",
        "name": "Desert Vista High School",
        "address": "16440 S 32nd St, Phoenix, AZ 85048",
        "lat": 33.3050,
        "lon": -111.9830,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.9930, 33.2950],
                        [-111.9730, 33.2950],
                        [-111.9730, 33.3150],
                        [-111.9930, 33.3150],
                        [-111.9930, 33.2950],
                    ]]
                }
            }]
        }
    },
    {
        "id": "chandler",
        "name": "Chandler High School",
        "address": "350 N Arizona Ave, Chandler, AZ 85224",
        "lat": 33.3070,
        "lon": -111.8410,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.8510, 33.2970],
                        [-111.8310, 33.2970],
                        [-111.8310, 33.3170],
                        [-111.8510, 33.3170],
                        [-111.8510, 33.2970],
                    ]]
                }
            }]
        }
    },
    {
        "id": "hamilton",
        "name": "Hamilton High School",
        "address": "3700 S Arizona Ave, Chandler, AZ 85249",
        "lat": 33.2620,
        "lon": -111.8450,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.8550, 33.2520],
                        [-111.8350, 33.2520],
                        [-111.8350, 33.2720],
                        [-111.8550, 33.2720],
                        [-111.8550, 33.2520],
                    ]]
                }
            }]
        }
    },
    {
        "id": "saguaro",
        "name": "Saguaro High School",
        "address": "6250 N 82nd St, Scottsdale, AZ 85250",
        "lat": 33.5020,
        "lon": -111.9230,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.9330, 33.4920],
                        [-111.9130, 33.4920],
                        [-111.9130, 33.5120],
                        [-111.9330, 33.5120],
                        [-111.9330, 33.4920],
                    ]]
                }
            }]
        }
    },
    {
        "id": "corona_del_sol",
        "name": "Corona del Sol High School",
        "address": "1001 E Galveston St, Tempe, AZ 85282",
        "lat": 33.3930,
        "lon": -111.9170,
        "type": "football_field",
        "polygon_aoi": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-111.9270, 33.3830],
                        [-111.9070, 33.3830],
                        [-111.9070, 33.4030],
                        [-111.9270, 33.4030],
                        [-111.9270, 33.3830],
                    ]]
                }
            }]
        }
    },
]

# --- Heat policy thresholds (based on AIA state guidelines) ---
HEAT_POLICY = {
    "name": "Arizona Interscholastic Association Heat Acclimatization Guidelines",
    "source": "AIA Sports Medicine Advisory Committee",
    "thresholds": {
        "green": {
            "max_heat_index_c": 27.0,   # 80.6°F - Normal activity
            "action": "standard_practice",
        },
        "yellow": {
            "max_heat_index_c": 30.0,   # 86°F - Increased rest breaks
            "action": "increase_rest_breaks",
        },
        "orange": {
            "max_heat_index_c": 32.0,   # 89.6°F - Limit outdoor intensity
            "action": "limit_intensity",
        },
        "red": {
            "max_heat_index_c": 35.0,   # 95°F - Move indoors or reschedule
            "action": "reschedule_or_suspend",
        },
        "black": {
            "max_heat_index_c": 38.0,   # 100.4°F - Cancel outdoor activity
            "action": "cancel_outdoor",
        },
    },
}

# --- Time buckets for scheduling ---
TIME_BUCKETS = {
    "morning":   {"start": "07:00", "end": "11:00", "label": "Morning (7-11 AM)"},
    "midday":    {"start": "11:00", "end": "15:00", "label": "Midday (11 AM-3 PM)"},
    "afternoon": {"start": "15:00", "end": "19:00", "label": "Afternoon (3-7 PM)"},
}

# --- Cost parameters for decision rule ---
COST_PARAMS = {
    "C_dispatch": 500,              # Cost of unnecessary reschedule (lost productivity)
    "C_liability": 50000,           # Cost of missed heat event (medical + legal)
    "P_false_alarm_default": 0.1,
    "P_miss_default": 0.05,
}

# --- FortyGuard API settings ---
API_SETTINGS = {
    "base_url": "https://api.fortyguard.com",
    "granularity": 100,             # meters: 60, 80, or 100
    "filter_type": 1,               # 1 = single hour
    "forecast_hours_ahead": 12,
}

# --- NWS Station for ground truth ---
NWS_STATIONS = {
    "KPHX": {
        "name": "Phoenix Sky Harbor International Airport",
        "lat": 33.4373,
        "lon": -112.0078,
        "distance_km": "varies by site",
    }
}

# --- Evaluation settings ---
EVAL_SETTINGS = {
    "replay_years": [2023],
    "null_day_count": 3,
    "heat_wave_events": [
        {"name": "July 2023 Phoenix Heat Wave", "start": "2023-07-15", "end": "2023-07-15"},
    ],
}

# --- Sample practice schedule (for demo) ---
SAMPLE_SCHEDULE = [
    {"site_id": "mountain_pointe", "activity": "Varsity Practice", "day": "Monday", "time": "15:00", "duration_hours": 2.5},
    {"site_id": "mountain_pointe", "activity": "JV Practice", "day": "Monday", "time": "17:30", "duration_hours": 2.0},
    {"site_id": "desert_vista",    "activity": "Varsity Practice", "day": "Monday", "time": "15:00", "duration_hours": 2.5},
    {"site_id": "chandler",        "activity": "Freshman Practice", "day": "Monday", "time": "07:00", "duration_hours": 2.0},
    {"site_id": "hamilton",        "activity": "Varsity Practice", "day": "Monday", "time": "16:00", "duration_hours": 2.5},
    {"site_id": "saguaro",         "activity": "Varsity Practice", "day": "Monday", "time": "15:30", "duration_hours": 2.5},
    {"site_id": "corona_del_sol",  "activity": "JV Practice", "day": "Monday", "time": "17:00", "duration_hours": 2.0},
]

# --- Phoenix August humidity data (monthly averages from NOAA) ---
# Used as humidity placeholder when env_params is unavailable
PHOENIX_HUMIDITY = {
    "month": 8,
    "avg_relative_humidity_pct": 20.0,   # Phoenix in August is very dry
    "morning_humidity_pct": 35.0,         # Higher at dawn
    "midday_humidity_pct": 15.0,
    "afternoon_humidity_pct": 12.0,
}
