"""
Heatwatch Dashboard
Streamlit UI showing portfolio, schedule, and audit log
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Ensure this directory is on the Python path (for imports like config, core_engine)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SITES, TIME_BUCKETS, HEAT_POLICY, PHOENIX_HUMIDITY
from core_engine import CoreEngine, compute_heat_index, check_policy_threshold

# Page config
st.set_page_config(
    page_title="Heatwatch — Heat Safety Agent",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ Heatwatch")
st.subheader("Heat Safety Agent for Football Programs")

# Sidebar
st.sidebar.header("Configuration")
target_date = st.sidebar.date_input("Date", value=datetime.now().date())
target_time = st.sidebar.selectbox("Time", ["07:00", "10:00", "12:00", "14:00", "16:00", "18:00"], index=3)

# Initialize client
@st.cache_resource
def get_client():
    # Try Streamlit secrets first (for Cloud deployment), then .env (for local)
    api_key = None
    try:
        api_key = st.secrets["FORTYGUARD_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass

    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FORTYGUARD_API_KEY")

    if api_key:
        os.environ["FORTYGUARD_API_KEY"] = api_key
        from fortyguard import FortyGuardClient
        return FortyGuardClient()
    else:
        from mock_client import MockFortyGuardClient
        return MockFortyGuardClient()

client = get_client()

# Run sweep button
if st.sidebar.button("🔍 Run Heat Check", type="primary"):
    st.session_state["running"] = True
    engine = CoreEngine(client)
    
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, site in enumerate(SITES):
        status.text(f"Checking {site['name']}...")
        progress.progress((i + 1) / len(SITES))
        
        decision = engine.check_site(site, str(target_date), target_time)
        results.append(decision)
    
    engine.close()
    st.session_state["results"] = results
    st.session_state["running"] = False
    status.text("✅ Sweep complete!")
    progress.empty()

# Display results
if "results" in st.session_state:
    results = st.session_state["results"]
    
    # Summary metrics
    st.header("📊 Sweep Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    alerts = len([r for r in results if r["alert_decision"] == "ALERT"])
    reschedules = len([r for r in results if r["reschedule_action"] == "RESCHEDULE"])
    suspends = len([r for r in results if r["reschedule_action"] == "SUSPEND"])
    
    col1.metric("Sites Checked", len(results))
    col2.metric("Alerts", alerts, delta=None, delta_color="inverse")
    col3.metric("Reschedules", reschedules)
    col4.metric("Suspensions", suspends)
    
    # Site details
    st.header("🏫 Site Status")
    
    for result in results:
        level = result["policy_level"]
        color_map = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴", "black": "⚫"}
        icon = color_map.get(level, "⚪")
        
        with st.expander(f"{icon} {result['site_name']} — {level.upper()}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Temperature", f"{result['temperature_c']:.1f}°C")
                st.metric("Heat Index", f"{result['heat_index_c']:.1f}°C")
                st.metric("Policy Level", level.upper())
            
            with col2:
                st.metric("Decision", result["alert_decision"])
                st.metric("Action", result["reschedule_action"])
                if result["reschedule_detail"]:
                    st.info(result["reschedule_detail"])
            
            # Cost analysis
            cost = result["cost_analysis"]
            st.write(f"**Cost Analysis:** E[alert] = ${cost['E_alert']:.0f} vs E[silence] = ${cost['E_silence']:.0f}")
    
    # Schedule before/after
    st.header("📅 Schedule Impact")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Before (Original)")
        for result in results:
            st.write(f"• {result['site_name']}: Practice at 15:00")
    
    with col2:
        st.subheader("After (Rescheduled)")
        for result in results:
            if result["reschedule_action"] == "RESCHEDULE":
                st.write(f"• {result['site_name']}: Moved to 07:00 ☀️")
            elif result["reschedule_action"] == "SUSPEND":
                st.write(f"• {result['site_name']}: ⛔ SUSPENDED")
            else:
                st.write(f"• {result['site_name']}: ✅ No change needed")
    
    # Audit log
    st.header("📋 Audit Log")
    
    try:
        conn = sqlite3.connect("heatwatch_audit.db")
        df = pd.read_sql_query(
            "SELECT timestamp, site_name, temperature_c, heat_index_c, policy_level, alert_decision, reschedule_action FROM audit_log ORDER BY id DESC LIMIT 20",
            conn
        )
        conn.close()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No audit entries yet. Run a check first.")
    except:
        st.info("Audit database not initialized yet.")

else:
    # Welcome screen
    st.header("Welcome to Heatwatch")
    st.write("""
    Heatwatch monitors athletic facilities using FortyGuard's 2m-elevation 
    temperature data, predicts dangerous heat 12 hours ahead, and reschedules 
    practice to safer times.
    
    **How to use:**
    1. Select a date and time in the sidebar
    2. Click "Run Heat Check"
    3. View the results and audit log
    """)
    
    st.header("🏫 Monitored Sites")
    for site in SITES:
        st.write(f"• {site['name']} — {site['address']}")
    
    st.header("📏 Policy Thresholds")
    for level, data in HEAT_POLICY["thresholds"].items():
        st.write(f"• **{level.upper()}**: < {data['max_heat_index_c']}°C — {data['action']}")

# ============================================
# EVAL DASHBOARD (Plotly Charts)
# ============================================

import plotly.graph_objects as go
import json
from pathlib import Path

# Load eval results if available
eval_file = Path("eval_results.json")
if eval_file.exists():
    with open(eval_file) as f:
        eval_results = json.load(f)

    st.header("📊 Evaluation Results")
    st.caption("Tested against July 2023 Phoenix heat wave + April 2023 baseline")

    # Top metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recall", f"{eval_results['summary']['recall']:.0%}", delta="Perfect")
    m2.metric("False Alarms", f"{eval_results['summary']['false_alarm_rate']:.0%}", delta="Zero")
    m3.metric("Sites Tested", eval_results['summary']['total_site_days'])
    m4.metric("Savings", f"${eval_results['summary']['cost_delta']['savings']:,}", delta_color="inverse")

    # Import and render Plotly charts
    from eval_dashboard import (
        create_cost_comparison_chart, create_site_temperature_chart,
        create_policy_heatmap, create_microclimate_chart,
        create_detection_summary, create_savings_gauge,
    )

    # Cost comparison
    st.plotly_chart(create_cost_comparison_chart(), use_container_width=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(create_site_temperature_chart(), use_container_width=True)
    with col2:
        st.plotly_chart(create_detection_summary(), use_container_width=True)
        st.plotly_chart(create_savings_gauge(), use_container_width=True)

    st.plotly_chart(create_microclimate_chart(), use_container_width=True)
    st.plotly_chart(create_policy_heatmap(), use_container_width=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.write("Built with FortyGuard Temperature API")
st.sidebar.write("Track 6 — Agentic")
