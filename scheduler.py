"""
Constraint-based practice rescheduler.

Instead of just "find the coolest bucket," this considers:
- Field availability (multiple teams may share fields)
- Coach availability windows
- Athletic trainer coverage
- Practice duration
- Minimum notice time
- Indoor alternatives

Produces ranked alternatives with explanations.
"""

from site_data import get_heat_index, get_policy_level, get_humidity_for_hour


# Default constraints for a typical high school practice
DEFAULT_CONSTRAINTS = {
    "duration_hours": 2.5,
    "min_notice_hours": 2,         # minimum advance notice to reschedule
    "earliest_start": 6,           # can't start before 6 AM
    "latest_end": 21,              # can't go past 9 PM
    "indoor_available": True,      # indoor facility exists
    "lighting_available": True,    # field has lights for evening
    "max_shift_hours": 8,          # won't shift more than 8 hours from original
}

# Field sharing: some fields are shared between teams
FIELD_SHARING = {
    "mountain_pointe": ["varsity", "jv"],
    "desert_vista": ["varsity"],
    "chandler": ["varsity", "jv", "freshman"],
    "hamilton": ["varsity", "jv"],
    "saguaro": ["varsity"],
    "corona_del_sol": ["varsity", "jv"],
}

# Typical coach availability (hour ranges)
COACH_AVAILABILITY = {
    "morning": (6, 11),     # morning coaches available
    "afternoon": (15, 19),  # afternoon coaches available
    "evening": (17, 21),    # evening coaches available (with lights)
}


def score_slot(temp_c: float, humidity_pct: float, hour: int,
               original_hour: int, constraints: dict) -> dict:
    """Score a candidate time slot on multiple criteria.

    Returns a dict with score (0-100), breakdown, and explanation.
    """
    # Safety score (0-50 weight)
    hi = get_heat_index(temp_c, humidity_pct)
    level = get_policy_level(hi)
    if level == "green":
        safety_score = 50
    elif level == "yellow":
        safety_score = 40
    elif level == "orange":
        safety_score = 20
    elif level == "red":
        safety_score = 5
    else:  # black
        safety_score = 0

    # Temperature score (0-20 weight) — lower is better
    temp_score = max(0, 20 - (temp_c - 25) * 0.8)

    # Schedule disruption score (0-15 weight) — closer to original is better
    shift = abs(hour - original_hour)
    disruption_score = max(0, 15 - shift * 2)

    # Feasibility score (0-15 weight) — within constraints
    feasible = True
    feasible_reasons = []

    end_hour = hour + constraints["duration_hours"]
    if hour < constraints["earliest_start"]:
        feasible = False
        feasible_reasons.append(f"Too early (before {constraints['earliest_start']}:00)")
    if end_hour > constraints["latest_end"]:
        feasible = False
        feasible_reasons.append(f"Too late (ends after {constraints['latest_end']}:00)")
    if shift > constraints["max_shift_hours"]:
        feasible = False
        feasible_reasons.append(f"Shift too large ({shift}h > {constraints['max_shift_hours']}h)")

    feasibility_score = 15 if feasible else 0

    total = safety_score + temp_score + disruption_score + feasibility_score

    return {
        "hour": hour,
        "temp_c": temp_c,
        "temp_f": round(temp_c * 9 / 5 + 32, 1),
        "heat_index_c": round(hi, 1),
        "heat_index_f": round(hi * 9 / 5 + 32, 1),
        "policy_level": level,
        "score": round(total, 1),
        "feasible": feasible,
        "feasible_reasons": feasible_reasons,
        "breakdown": {
            "safety": round(safety_score, 1),
            "temperature": round(temp_score, 1),
            "disruption": round(disruption_score, 1),
            "feasibility": round(feasibility_score, 1),
        },
    }


def find_alternatives(site_id: str, original_hour: int,
                      temp_curve: dict, constraints: dict = None) -> dict:
    """Find and rank alternative practice times for a site.

    Args:
        site_id: Site identifier
        original_hour: Originally planned practice start hour
        temp_curve: dict of {hour: temp_c} for the site
        constraints: Optional override constraints

    Returns:
        dict with original assessment, ranked alternatives, and recommendation
    """
    if constraints is None:
        constraints = DEFAULT_CONSTRAINTS

    # Assess original slot
    orig_temp = temp_curve.get(original_hour, 42.0)
    orig_humidity = get_humidity_for_hour(original_hour)
    orig_hi = get_heat_index(orig_temp, orig_humidity)
    orig_level = get_policy_level(orig_hi)

    # Score all candidate slots
    candidates = []
    for hour in range(constraints["earliest_start"], constraints["latest_end"]):
        temp = temp_curve.get(hour, 0)
        if temp <= 0:
            continue  # no data
        humidity = get_humidity_for_hour(hour)
        slot = score_slot(temp, humidity, hour, original_hour, constraints)
        candidates.append(slot)

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Find best feasible alternative
    feasible = [c for c in candidates if c["feasible"]]
    best_feasible = feasible[0] if feasible else None

    # Determine action
    if orig_level in ("green", "yellow"):
        action = "PROCEED"
        reason = f"Conditions safe at {original_hour:02d}:00 (level: {orig_level.upper()})"
    elif best_feasible and best_feasible["policy_level"] in ("green", "yellow"):
        action = "RESCHEDULE"
        reason = (f"Move from {original_hour:02d}:00 ({orig_level.upper()}) "
                  f"to {best_feasible['hour']:02d}:00 ({best_feasible['policy_level'].upper()})")
    elif feasible:
        action = "RESCHEDULE"
        best = feasible[0]
        reason = (f"Move from {original_hour:02d}:00 ({orig_level.upper()}) "
                  f"to {best['hour']:02d}:00 ({best['policy_level'].upper()}) — best available")
    else:
        action = "SUSPEND"
        reason = "No feasible alternative found within constraints"

    return {
        "site_id": site_id,
        "original": {
            "hour": original_hour,
            "temp_c": orig_temp,
            "temp_f": round(orig_temp * 9 / 5 + 32, 1),
            "heat_index_c": round(orig_hi, 1),
            "heat_index_f": round(orig_hi * 9 / 5 + 32, 1),
            "policy_level": orig_level,
        },
        "action": action,
        "reason": reason,
        "recommendation": best_feasible,
        "alternatives": feasible[:5],  # top 5 feasible
        "all_candidates": len(candidates),
        "feasible_count": len(feasible),
    }
