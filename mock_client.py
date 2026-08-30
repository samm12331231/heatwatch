"""
Mock FortyGuard Client
Returns cached data instantly for development without an API key.
Build everything against this first. Swap in real client on Day 5.
"""

import json
import os
from pathlib import Path


class MockFortyGuardClient:
    """
    Drop-in replacement for FortyGuardClient.
    Reads from static JSON fixtures and returns instantly.
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data" / "mock_responses"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_heatmap(self, polygon_aoi: dict, start_date: str, start_time: str,
                       filter_type: int = 1, granularity: int = 100, **kwargs) -> dict:
        """Return a mock heatmap response."""
        fixture = self._load_fixture("heatmap", start_date, start_time)
        if fixture:
            return fixture

        # Generate synthetic heatmap data if no fixture exists
        return self._generate_mock_heatmap(polygon_aoi, start_date, start_time)

    def environmental_parameters(self, point: dict, date_time: dict, **kwargs) -> dict:
        """Return mock environmental parameters."""
        fixture = self._load_fixture("env_params", 
                                     date_time.get("start_date", "2026-08-20"),
                                     date_time.get("start_time", "14:00"))
        if fixture:
            return fixture

        return self._generate_mock_env_params(point)

    def fetch_api_key_usage(self) -> dict:
        """Return mock credit usage."""
        return {
            "plan": "Hackathon Trial",
            "credits_remaining": 1000,
            "credits_used": 0,
            "status": "active",
        }

    def get_status(self, activity_id: str) -> dict:
        """Return mock status — always completed."""
        return {
            "activity_id": activity_id,
            "status": "Completed",
            "result": {"message": "Mock task completed"},
        }

    def wait_for(self, activity_id: str, timeout: int = 300, **kwargs) -> dict:
        """Return mock result — instant."""
        return self.get_status(activity_id)

    def _load_fixture(self, endpoint: str, date: str, time: str) -> dict | None:
        """Load a cached response from disk if it exists."""
        fixture_path = self.data_dir / f"{endpoint}_{date}_{time.replace(':', '')}.json"
        if fixture_path.exists():
            with open(fixture_path) as f:
                return json.load(f)
        return None

    def _generate_mock_heatmap(self, polygon_aoi: dict, start_date: str, start_time: str) -> dict:
        """Generate mock heatmap data aligned with site_data.py pre-computed curves."""
        import random
        import hashlib
        from site_data import HEAT_DAY_CURVES, NULL_DAY_CURVES
        from config import SITES

        # Determine which day type this is
        day_type = "heat" if "07-15" in start_date or "07-16" in start_date or "07-17" in start_date else "null"
        curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES
        hour = int(start_time.split(":")[0]) if ":" in start_time else 16

        # Find the matching site by polygon coordinates
        base_temp = 42.0  # fallback
        for site in SITES:
            site_poly = json.dumps(site["polygon_aoi"], sort_keys=True)
            input_poly = json.dumps(polygon_aoi, sort_keys=True)
            if site_poly == input_poly or site["id"] in str(polygon_aoi):
                base_temp = curves[site["id"]].get(hour, 42.0)
                break

        # Add small random variance for tile spread
        seed_str = json.dumps(polygon_aoi, sort_keys=True) + start_date + start_time
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        # Generate 16 tiles (4x4 grid)
        tiles = []
        for i in range(16):
            temp = base_temp + random.uniform(-1.5, 1.5)
            tiles.append({
                "tile_id": i,
                "average_temperature": round(temp, 2),
                "min_temperature": round(temp - 1.2, 2),
                "max_temperature": round(temp + 1.8, 2),
            })

        temps = [t["average_temperature"] for t in tiles]
        
        return {
            "activity_id": f"mock_heatmap_{start_date}_{start_time.replace(':', '')}",
            "result": {
                "map_data": {
                    "type": "FeatureCollection",
                    "features": tiles,
                },
                "stats_data": {
                    "activity_id": f"mock_heatmap_{start_date}_{start_time.replace(':', '')}",
                    "analytic_type": "tcm",
                    "units": "°C",
                    "n_cells": len(tiles),
                    "min": round(min(temps), 2),
                    "max": round(max(temps), 2),
                    "mean": round(sum(temps) / len(temps), 2),
                    "temperature_stats": {
                        "min": round(min(temps), 2),
                        "max": round(max(temps), 2),
                        "mean": round(sum(temps) / len(temps), 2),
                    },
                },
            },
        }

    def _generate_mock_env_params(self, point: dict) -> dict:
        """Generate realistic mock environmental parameters."""
        import random
        import hashlib
        seed = int(hashlib.md5(json.dumps(point, sort_keys=True).encode()).hexdigest()[:8], 16)
        random.seed(seed)

        # Phoenix August: hot and dry
        temp = 40.0 + random.uniform(-2, 3)
        humidity = 15 + random.uniform(-5, 10)  # Low humidity in Phoenix

        return {
            "activity_id": f"mock_env_{hash(str(point)) % 10000}",
            "result": {
                "temperature_celsius": round(temp, 2),
                "heat_index_celsius": round(temp + (humidity - 40) * 0.1, 2),
                "relative_humidity_percent": round(humidity, 2),
                "apparent_temperature_celsius": round(temp + 2, 2),
                "air_quality_index": 45,
                "solar_irradiance_wm2": 850,
            },
        }
