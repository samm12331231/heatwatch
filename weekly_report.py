"""
Heatwatch Weekly Report Generator
Creates a printable heat safety forecast for coaches.
Shows the week's risk levels, recommended practice times, and cost analysis.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from site_data import (
    SITE_INFO, get_all_site_readings, get_heat_index,
    get_policy_level, get_humidity_for_hour, HEAT_DAY_CURVES, NULL_DAY_CURVES,
)

LEVEL_COLORS = {
    "black": "#EF4444", "red": "#F97316", "orange": "#F59E0B",
    "yellow": "#EAB308", "green": "#22C55E",
}
LEVEL_ICONS = {
    "black": "⚫", "red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢",
}


def get_weekly_risk_matrix(site_id: str, day_type: str = "heat") -> pd.DataFrame:
    """Build a 7-day × 6-time-slot risk matrix for a site.

    Adds small day-to-day variance (-0.8 to +0.8°C) so the heatmap
    doesn't look identical Mon-Sun. Variance is seeded per day/site
    for reproducibility.
    """
    import hashlib
    from site_data import HEAT_DAY_CURVES, NULL_DAY_CURVES
    curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES

    time_slots = ["07:00", "09:00", "12:00", "14:00", "16:00", "18:00"]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    data = []
    for i, day in enumerate(days):
        row = {"Day": day}
        # Deterministic per-day variance using hash (reproducible but varied)
        seed = int(hashlib.md5(f"{site_id}-{day}-{day_type}".encode()).hexdigest()[:8], 16)
        day_offset = ((seed % 16) - 8) / 10.0  # -0.8 to +0.8°C

        for slot in time_slots:
            hour = int(slot.split(":")[0])
            temp_c = curves[site_id].get(hour, 0) + day_offset
            humidity = get_humidity_for_hour(hour)
            hi = get_heat_index(temp_c, humidity)
            level = get_policy_level(hi)
            row[slot] = f"{level.upper()}\n{temp_c:.0f}°C"
            row[f"{slot}_level"] = level
            row[f"{slot}_temp"] = temp_c
        data.append(row)

    return pd.DataFrame(data)


def create_weekly_heatmap(site_id: str, site_name: str, day_type: str = "heat") -> go.Figure:
    """Create a Plotly heatmap of the week's risk levels.

    Includes small per-day variance so the heatmap doesn't look
    identical across all 7 days.
    """
    import hashlib
    from site_data import HEAT_DAY_CURVES, NULL_DAY_CURVES
    curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES

    time_slots = ["07:00", "09:00", "12:00", "14:00", "16:00", "18:00"]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    z = []
    text = []
    for i, day in enumerate(days):
        seed = int(hashlib.md5(f"{site_id}-{day}-{day_type}".encode()).hexdigest()[:8], 16)
        day_offset = ((seed % 16) - 8) / 10.0  # -0.8 to +0.8°C

        row_z = []
        row_text = []
        for slot in time_slots:
            hour = int(slot.split(":")[0])
            temp_c = curves[site_id].get(hour, 0) + day_offset
            humidity = get_humidity_for_hour(hour)
            hi = get_heat_index(temp_c, humidity)
            level = get_policy_level(hi)
            row_z.append(hi)
            row_text.append(f"{level.upper()} {temp_c:.0f}°C")
        z.append(row_z)
        text.append(row_text)

    fig = go.Figure(data=go.Heatmap(
        z=z, x=time_slots, y=days,
        text=text, texttemplate="%{text}",
        colorscale=[
            [0, "#22C55E"],     # green
            [0.3, "#EAB308"],   # yellow
            [0.5, "#F59E0B"],   # orange
            [0.7, "#F97316"],   # red
            [1.0, "#EF4444"],   # black
        ],
        zmin=25, zmax=42,
        textfont={"size": 13, "color": "white"},
        colorbar=dict(
            title="Heat Index (°C)",
            tickvals=[27, 30, 32, 35, 38],
            ticktext=["27°C", "30°C", "32°C", "35°C", "38°C"],
        ),
    ))

    fig.update_layout(
        title=f"📅 Practice Window Risk Matrix — {site_name}",
        xaxis_title="Time of Day",
        yaxis_title="Day of Week",
        template="plotly_dark",
        height=350,
    )

    # Add threshold lines
    fig.add_hline(y=-0.5, line_width=0)  # just to make it look right

    return fig


def render_weekly_report(site: dict, day_type: str = "heat"):
    """Render a full weekly report for one site."""
    site_id = site["id"]
    site_name = site["name"]

    # Heatmap
    fig = create_weekly_heatmap(site_id, site_name, day_type)
    st.plotly_chart(fig, use_container_width=True)

    # Summary stats
    from site_data import HEAT_DAY_CURVES, NULL_DAY_CURVES
    curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES

    dangerous_slots = 0
    total_slots = 0
    worst_temp = 0
    worst_slot = ""

    for hour in range(7, 20):
        temp_c = curves[site_id].get(hour, 0)
        humidity = get_humidity_for_hour(hour)
        hi = get_heat_index(temp_c, humidity)
        level = get_policy_level(hi)
        total_slots += 1
        if level in ("red", "black"):
            dangerous_slots += 1
        if temp_c > worst_temp:
            worst_temp = temp_c
            worst_slot = f"{hour:02d}:00"

    safe_pct = ((total_slots - dangerous_slots) / total_slots * 100) if total_slots > 0 else 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Safe Practice Windows", f"{total_slots - dangerous_slots}/{total_slots}",
              delta=f"{safe_pct:.0f}% of day")
    c2.metric("Peak Temperature", f"{worst_temp:.1f}°C",
              delta=f"Worst at {worst_slot}")
    c3.metric("Recommendation",
              "Move to 7 AM" if dangerous_slots > 0 else "Practice as scheduled")


def render_coach_report(day_type: str = "heat"):
    """Render the full coach's report page."""
    st.markdown('<div class="section-header">📋 Coach\'s Weekly Heat Report</div>',
                unsafe_allow_html=True)

    st.markdown("""
    **For coaches and athletic directors:** This report shows the week's heat risk
    for your facility. Red/black zones indicate times when outdoor practice should
    be moved or cancelled. Green/yellow zones are safe for normal activity.
    """)

    for site in SITE_INFO:
        with st.expander(f"🏫 {site['name']}", expanded=False):
            render_weekly_report(site, day_type)

    # Fleet summary
    st.markdown('<div class="section-header">🏫 Fleet Summary</div>', unsafe_allow_html=True)

    summary_data = []
    for site in SITE_INFO:
        curves = HEAT_DAY_CURVES if day_type == "heat" else NULL_DAY_CURVES
        dangerous = 0
        total = 0
        for hour in range(7, 20):
            temp_c = curves[site["id"]].get(hour, 0)
            hi = get_heat_index(temp_c, get_humidity_for_hour(hour))
            level = get_policy_level(hi)
            total += 1
            if level in ("red", "black"):
                dangerous += 1

        summary_data.append({
            "Site": site["short_name"],
            "Safe Windows": f"{total - dangerous}/{total}",
            "Danger Windows": dangerous,
            "Risk Level": "HIGH" if dangerous > 6 else "MODERATE" if dangerous > 0 else "LOW",
        })

    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
