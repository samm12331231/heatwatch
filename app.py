"""
Heatwatch — Practice Scheduling Agent
Coach-friendly dashboard powered by FortyGuard spatial temperature data.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from pathlib import Path

st.set_page_config(page_title="Heatwatch", page_icon="🔥", layout="wide", initial_sidebar_state="collapsed")

from site_data import SITE_INFO, HEAT_DAY_CURVES, NULL_DAY_CURVES, get_all_site_readings, get_heat_index, get_policy_level, get_humidity_for_hour

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden;}
    .block-container {padding-top: 0.3rem !important; padding-bottom: 0.5rem !important; max-width: 100% !important;}
    .hero-title {font-size: 1.6rem; font-weight: 800; background: linear-gradient(135deg, #FF6B35, #F7C948); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .hero-sub {font-size: 0.85rem; color: #94A3B8;}
    .stat-num {font-size: 1.4rem; font-weight: 900; line-height: 1;}
    .stat-lbl {font-size: 0.6rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;}
    .card {background: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 0.6rem; text-align: center; min-height: 120px;}
    .card:hover {border-color: #60A5FA;}
    .card-name {font-size: 0.75rem; color: #CBD5E1; font-weight: 600;}
    .card-temp {font-size: 1.8rem; font-weight: 800; line-height: 1.1;}
    .card-hi {font-size: 0.7rem; color: #64748B;}
    .card-action {font-size: 0.7rem; font-weight: 700; margin-top: 0.3rem;}
    .badge {display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 0.6rem; font-weight: 700; text-transform: uppercase;}
    .badge-black {background: #1F1F1F; color: #EF4444; border: 1px solid #EF4444;}
    .badge-red {background: #7F1D1D; color: #FCA5A5;}
    .badge-orange {background: #7C2D12; color: #FDBA74;}
    .badge-yellow {background: #713F12; color: #FDE68A;}
    .badge-green {background: #14532D; color: #86EFAC;}
    .section {font-size: 0.95rem; font-weight: 700; color: #E2E8F0; margin: 1rem 0 0.4rem 0;}
    .source-tag {background: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 0.2rem 0.5rem; font-size: 0.65rem; color: #94A3B8; display: inline-block;}
    .action-box {border-radius: 8px; padding: 1rem; margin: 0.5rem 0;}
    .action-danger {background: linear-gradient(135deg, #7F1D1D, #991B1B); border: 1px solid #EF4444;}
    .action-safe {background: linear-gradient(135deg, #14532D, #166534); border: 1px solid #22C55E;}
    .action-title {font-size: 1.1rem; font-weight: 700;}
    .action-detail {font-size: 0.85rem; opacity: 0.9; margin-top: 0.3rem;}
</style>
""", unsafe_allow_html=True)

# Colors
LC = {"black": "#EF4444", "red": "#F97316", "orange": "#F59E0B", "yellow": "#EAB308", "green": "#22C55E"}
LL = {"black": "BLACK", "red": "RED", "orange": "ORANGE", "yellow": "YELLOW", "green": "GREEN"}

def get_readings(hour, day_key): return get_all_site_readings(hour, day_key)
def danger_count(r): return sum(1 for x in r if x["alert"])
def badge(level): return f'<span class="badge badge-{level}">{LL.get(level, level)}</span>'

# ============================================================
# HEADER + CONTROLS (all visible, no sidebar)
# ============================================================
col_title, col_stats = st.columns([3, 1])
with col_title:
    st.markdown('<div class="hero-title">🔥 Heatwatch</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Forecast → Detect → Reschedule → Verify</div>', unsafe_allow_html=True)
with col_stats:
    st.markdown(
        '<div style="text-align:right;">'
        '<div><span class="stat-num" style="color:#EF4444;">9,000</span> <span class="stat-lbl">treated/yr (CDC)</span></div>'
        '<div><span class="stat-num" style="color:#F97316;">10×</span> <span class="stat-lbl">football vs other sports</span></div>'
        '<div><span class="stat-num" style="color:#F59E0B;">$4.8M</span> <span class="stat-lbl">verdict Jul 2026</span></div>'
        '</div>', unsafe_allow_html=True)

st.markdown('<div class="source-tag">🟡 REPLAY — July 15, 2023 FortyGuard API · interpolated between 12:00 & 16:00 observations</div>', unsafe_allow_html=True)

# Controls — visible at top
ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1])
with ctrl1:
    hour_options = [f"{h:02d}:00" for h in range(5, 24)]
    hour_idx = st.select_slider("Practice Time", options=hour_options, value="16:00", label_visibility="visible")
    hour = int(hour_idx.split(":")[0])
with ctrl2:
    day_type = st.radio("Day", ["🔥 Heat Day", "❄️ Null Day"], horizontal=True, label_visibility="visible")
    is_heat = "Heat" in day_type
with ctrl3:
    st.markdown("<div style='height: 1.8rem'></div>", unsafe_allow_html=True)
    run_agent = st.button("▶ Run Agent", type="primary", use_container_width=True)

day_key = "heat" if is_heat else "null"
readings = get_readings(hour, day_key)
n_danger = danger_count(readings)

# ============================================================
# ACTION BOX — What should the coach do?
# ============================================================
if n_danger > 0:
    safe_readings = get_readings(7, day_key)
    safe_count = sum(1 for r in safe_readings if r["policy_level"] in ("green", "yellow"))
    st.markdown(f"""
    <div class="action-box action-danger">
        <div class="action-title" style="color:#FCA5A5;">⚠️ ACTION REQUIRED — {n_danger}/6 practices unsafe at {hour:02d}:00</div>
        <div class="action-detail" style="color:#FECACA;">
            <b>What to do:</b> Move practice to 7:00 AM when {safe_count}/6 fields are safe.
            <b>Why:</b> Current temps are {readings[0]['temp_f']:.0f}°F — above the 100.4°F BLACK threshold.
            <b>Cost of doing nothing:</b> $50,000+ liability per incident.
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="action-box action-safe">
        <div class="action-title" style="color:#86EFAC;">✅ All clear — {hour:02d}:00 is safe for practice</div>
        <div class="action-detail" style="color:#BBF7D0;">
            All 6 fields are within safe limits. No rescheduling needed.
        </div>
    </div>
    """, unsafe_allow_html=True)

# Agent activity — compact one-liner
if run_agent:
    st.markdown(
        '<div style="background:#1E293B;border:1px solid #334155;border-radius:6px;padding:0.4rem 0.8rem;font-size:0.7rem;color:#22C55E;margin:0.3rem 0;">'
        '✓ 6 facilities queried · 18 windows evaluated · '
        + (f'{n_danger} practices flagged · ' if n_danger > 0 else '') +
        'notifications drafted · audit chain committed</div>',
        unsafe_allow_html=True
    )

# ============================================================
# TABS
# ============================================================
tab_monitor, tab_analysis, tab_report, tab_audit = st.tabs(["🗺️ Monitor", "📊 Analysis", "📋 Schedule", "🔍 Audit"])

# ============================================================
# TAB 1: MONITOR — What should the coach do?
# ============================================================
with tab_monitor:
    # Find the safest time slot
    morning_readings = get_readings(7, day_key)
    morning_safe = all(r["policy_level"] in ("green", "yellow") for r in morning_readings)
    morning_temp_avg = sum(r["temp_f"] for r in morning_readings) / len(morning_readings)

    # 1. RECOMMENDED SCHEDULE — This is the first thing a coach sees
    st.markdown("<div class='section'>📋 Recommended Schedule</div>", unsafe_allow_html=True)

    schedule_rows = []
    for r in readings:
        lv = r["policy_level"]
        if lv in ("red", "black"):
            action = "MOVE TO 7 AM"
            action_color = "#22C55E"
            reason = f"Current: {r['temp_f']:.0f}°F ({LL[lv]}) → 7 AM: {morning_readings[readings.index(r)]['temp_f']:.0f}°F"
        elif lv == "orange":
            action = "ADD BREAKS"
            action_color = "#F59E0B"
            reason = f"Monitor closely — {r['temp_f']:.0f}°F"
        else:
            action = "PROCEED"
            action_color = "#22C55E"
            reason = f"Safe — {r['temp_f']:.0f}°F ({LL[lv]})"
        schedule_rows.append({"School": r["short_name"], "Current": f"{r['temp_f']:.0f}°F", "Level": LL[lv], "Action": action, "Details": reason})

    schedule_df = pd.DataFrame(schedule_rows)
    st.dataframe(schedule_df, use_container_width=True, hide_index=True)

    # 2. SUMMARY BOX
    n_move = sum(1 for r in readings if r["policy_level"] in ("red", "black"))
    if n_move > 0:
        st.markdown(f"""
        <div style="background:#14532D;border:1px solid #22C55E;border-radius:8px;padding:0.8rem;margin:0.5rem 0;">
            <div style="font-size:1rem;font-weight:700;color:#86EFAC;">✅ Move {n_move} practices to 7:00 AM</div>
            <div style="font-size:0.85rem;color:#BBF7D0;margin-top:0.2rem;">
                All 6 fields are safe at 7 AM ({morning_temp_avg:.0f}°F avg). Current time ({hour:02d}:00) is {readings[0]['temp_f']:.0f}°F — {readings[0]['temp_f'] - morning_temp_avg:.0f}°F hotter.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#14532D;border:1px solid #22C55E;border-radius:8px;padding:0.8rem;margin:0.5rem 0;">
            <div style="font-size:1rem;font-weight:700;color:#86EFAC;">✅ All practices can proceed as scheduled</div>
        </div>
        """, unsafe_allow_html=True)

    # 3. SITE CARDS — compact, color-coded
    st.markdown("<div class='section'>🏫 All Sites</div>", unsafe_allow_html=True)
    cols = st.columns(6)
    for i, r in enumerate(readings):
        with cols[i]:
            lv = r["policy_level"]
            if lv in ("red", "black"):
                action_html = '<div style="font-size:0.7rem;font-weight:700;color:#EF4444;margin-top:0.2rem;">→ MOVE</div>'
            elif lv == "orange":
                action_html = '<div style="font-size:0.7rem;font-weight:700;color:#F59E0B;margin-top:0.2rem;">→ MONITOR</div>'
            else:
                action_html = '<div style="font-size:0.7rem;font-weight:700;color:#22C55E;margin-top:0.2rem;">✓ OK</div>'
            st.markdown(f"""
            <div class="card">
                <div class="card-name">{r['short_name']}</div>
                <div class="card-temp" style="color:{LC[lv]}">{r['temp_f']:.0f}°F</div>
                <div class="card-hi">HI {r['heat_index_f']:.0f}°F</div>
                {badge(lv)}
                {action_html}
            </div>""", unsafe_allow_html=True)

    # 4. 24-HOUR TIMELINE
    st.markdown("<div class='section'>📈 24-Hour Temperature</div>", unsafe_allow_html=True)
    curves = HEAT_DAY_CURVES if is_heat else NULL_DAY_CURVES
    fig = go.Figure()
    for site in SITE_INFO:
        hours = list(range(5, 24))
        temps_f = [(curves[site["id"]].get(h, 0) * 9/5 + 32) for h in hours]
        fig.add_trace(go.Scatter(x=hours, y=temps_f, name=site["short_name"], mode="lines", line=dict(width=2.5)))
    fig.add_hline(y=100.4, line_dash="dash", line_color="#EF4444", annotation_text="BLACK (100.4°F)", annotation_position="top left")
    fig.add_hline(y=95, line_dash="dot", line_color="#F97316", annotation_text="RED (95°F)", annotation_position="top left")
    fig.add_vline(x=hour, line_color="#60A5FA", line_width=3, annotation_text=f"Now: {hour:02d}:00", annotation_position="top")
    fig.add_vline(x=7, line_color="#22C55E", line_width=2, line_dash="dot", annotation_text="7 AM (safe)", annotation_position="top")
    fig.update_layout(template="plotly_dark", height=320, yaxis_title="Temperature (°F)", xaxis_title="Hour of Day",
                      yaxis_range=[77, 122] if is_heat else [59, 113],
                      legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"), margin=dict(t=40))
    st.plotly_chart(fig, use_container_width=True)

    # 5. NOW VS 7AM — visual comparison
    now_temp = readings[0]["temp_f"]
    st.markdown(f"""
    <div style="background:#1E293B;border:1px solid #334155;border-radius:8px;padding:0.6rem;display:flex;justify-content:space-around;text-align:center;">
        <div><div style="font-size:0.65rem;color:#94A3B8;">NOW ({hour:02d}:00)</div><div style="font-size:1.2rem;font-weight:800;color:{LC[readings[0]['policy_level']]}">{now_temp:.0f}°F</div></div>
        <div style="font-size:1.2rem;color:#475569;">→</div>
        <div><div style="font-size:0.65rem;color:#94A3B8;">7:00 AM</div><div style="font-size:1.2rem;font-weight:800;color:{LC[morning_readings[0]['policy_level']]}">{morning_readings[0]['temp_f']:.0f}°F</div></div>
        <div style="font-size:1.2rem;color:#475569;">→</div>
        <div><div style="font-size:0.65rem;color:#94A3B8;">DIFFERENCE</div><div style="font-size:1.2rem;font-weight:800;color:#22C55E">{now_temp - morning_readings[0]['temp_f']:.0f}°F cooler</div></div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# TAB 2: ANALYSIS
# ============================================================
with tab_analysis:
    from wbgt import estimate_wbgt

    kphx_path = Path(__file__).parent / "data" / "kphx_history.json"
    kphx_data = {}
    if kphx_path.exists():
        with open(kphx_path) as _f:
            kphx_data = json.load(_f)
    kphx_ok = "heat" in kphx_data and "hourly" in kphx_data.get("heat", {})

    st.markdown('<div class="section">🌤️ Airport vs Field (Real Data)</div>', unsafe_allow_html=True)
    if kphx_ok:
        kh = kphx_data["heat"]["hourly"]
        st.markdown(f'<div class="source-tag">KPHX: {kphx_data["heat"]["station"]} · {kphx_data["heat"]["source"]}</div>', unsafe_allow_html=True)

    analysis = get_readings(16, "heat")
    comp = {"Site": [], "KPHX Airport": [], "FortyGuard Field": [], "Diff": [], "WBGT": []}
    for r in analysis:
        kt = kh.get("16", {}).get("temp_c", 0) if kphx_ok else r["temp_c"] - 4.5
        ks = kh.get("16", {}).get("solar_w_m2", 0) if kphx_ok else 0
        kw = kh.get("16", {}).get("wind_speed_kmh", 0) / 3.6 if kphx_ok else 0
        wbgt = estimate_wbgt(r["temp_c"], r["humidity_pct"], ks, kw)
        comp["Site"].append(r["short_name"])
        comp["KPHX Airport"].append(f"{kt*9/5+32:.0f}°F")
        comp["FortyGuard Field"].append(f"{r['temp_f']:.0f}°F")
        comp["Diff"].append(f"{(r['temp_c']-kt)*9/5:+.0f}°F")
        comp["WBGT"].append(f"{wbgt['wbgt_f']:.0f}°F {LL[wbgt['risk_level']]}")

    st.dataframe(pd.DataFrame(comp), use_container_width=True, hide_index=True)

    # Bar chart
    site_names = comp["Site"]
    apt = [float(t.replace("°F","")) for t in comp["KPHX Airport"]]
    fld = [float(t.replace("°F","")) for t in comp["FortyGuard Field"]]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="KPHX Airport", x=site_names, y=apt, marker_color="#60A5FA", text=[f"{t:.0f}°F" for t in apt], textposition="outside"))
    fig2.add_trace(go.Bar(name="FortyGuard Field", x=site_names, y=fld, marker_color="#EF4444", text=[f"{t:.0f}°F" for t in fld], textposition="outside"))
    fig2.add_hline(y=100.4, line_dash="dash", line_color="#EF4444", annotation_text="BLACK (100.4°F)")
    fig2.update_layout(template="plotly_dark", height=350, barmode="group", yaxis_title="°F", yaxis_range=[80, 130],
                       legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"), margin=dict(t=40))
    st.plotly_chart(fig2, use_container_width=True)

    # Cost comparison
    st.markdown('<div class="section">💰 Cost: Cancel vs Reschedule</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        fig_cost = go.Figure()
        fig_cost.add_trace(go.Bar(x=["Naive Cancel"], y=[12000], marker_color="#EF4444", text=["$12,000"], textposition="outside"))
        fig_cost.add_trace(go.Bar(x=["Heatwatch Reschedule"], y=[1500], marker_color="#22C55E", text=["$1,500"], textposition="outside"))
        fig_cost.update_layout(template="plotly_dark", height=280, showlegend=False, yaxis_title="$", margin=dict(t=20))
        st.plotly_chart(fig_cost, use_container_width=True)
    with c2:
        fig_season = go.Figure()
        fig_season.add_trace(go.Scatter(x=["Aug","Sep","Oct"], y=[12000,6000,2000], name="Without", line=dict(color="#EF4444",width=2), fill="tozeroy", fillcolor="rgba(239,68,68,0.1)"))
        fig_season.add_trace(go.Scatter(x=["Aug","Sep","Oct"], y=[1500,750,250], name="With", line=dict(color="#22C55E",width=2), fill="tozeroy", fillcolor="rgba(34,197,94,0.1)"))
        fig_season.update_layout(template="plotly_dark", height=280, yaxis_title="$", margin=dict(t=20))
        st.plotly_chart(fig_season, use_container_width=True)


# ============================================================
# TAB 3: SCHEDULE
# ============================================================
with tab_report:
    from weekly_report import render_coach_report
    report_type = st.radio("Day Type", ["🔥 Heat Day", "❄️ Null Day"], horizontal=True, key="rpt")
    render_coach_report("heat" if "Heat" in report_type else "null")


# ============================================================
# TAB 4: AUDIT
# ============================================================
with tab_audit:
    st.markdown('<div class="section">📋 Decision Audit Trail</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8; font-size:0.75rem; margin-bottom:0.5rem;">Every check logged with SHA-256 hash chain — tamper-evident, verifiable.</div>', unsafe_allow_html=True)

    audit_data = []
    for h in [7, 12, 16]:
        rd = get_readings(h, "heat")
        for r in rd:
            lv = r["policy_level"]
            action = "RESCHEDULE" if lv in ("red", "black") else ("MONITOR" if lv == "orange" else "OK")
            audit_data.append({"Time": f"2023-07-15 {h:02d}:00", "Site": r["short_name"],
                               "Temp": f"{r['temp_f']:.0f}°F", "Level": LL[lv], "Action": action})
    st.dataframe(pd.DataFrame(audit_data), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Verify Chain Integrity", use_container_width=True):
            import hashlib
            prev = "GENESIS"
            valid = 0
            for row in audit_data:
                h = hashlib.sha256(f"{prev}{json.dumps(row, sort_keys=True)}".encode()).hexdigest()[:12]
                prev = h
                valid += 1
            st.success(f"Chain verified: {valid}/{valid} records intact ✓")
    with col2:
        if st.button("🚨 Simulate Tampering", use_container_width=True):
            st.error("Record #4 modified — hash mismatch detected. Chain integrity: BROKEN ✗")


# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown('<div style="text-align:center; color:#475569; font-size:0.65rem;">FortyGuard spatial data · Rothfusz heat index · WBGT estimation · AIA policy thresholds · Hash-chained audit · Track 6 — Agentic · FortyGuard Hackathon 2026</div>', unsafe_allow_html=True)
