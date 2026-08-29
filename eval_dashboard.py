"""
Heatwatch Evaluation Dashboard
Plotly-based visualizations for eval results
"""
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

with open("eval_results.json") as f:
    results = json.load(f)


def create_cost_comparison_chart():
    """Bar chart: Naive cancellations vs Heatwatch reschedules."""
    cost = results["cost_delta"]
    fig = go.Figure(data=[
        go.Bar(
            name="Naive (Cancel All)",
            x=["Cost ($)"],
            y=[cost["cost_naive"]],
            marker_color="#EF4444",
            text=[f"${cost['cost_naive']:,}"],
            textposition="outside",
        ),
        go.Bar(
            name="Heatwatch (Reschedule)",
            x=["Cost ($)"],
            y=[cost["cost_heatwatch"]],
            marker_color="#10B981",
            text=[f"${cost['cost_heatwatch']:,}"],
            textposition="outside",
        ),
    ])
    fig.update_layout(
        title=dict(
            text="💰 Cost Comparison: Naive Cancellation vs Heatwatch Rescheduling",
            font=dict(size=16)
        ),
        yaxis_title="Cost ($)",
        barmode="group",
        template="plotly_dark",
        height=400,
        annotations=[
            dict(
                x="Cost ($)", y=max(cost["cost_naive"], cost["cost_heatwatch"]) * 1.2,
                text=f"Savings: ${cost['savings']:,}",
                showarrow=False, font=dict(size=18, color="#10B981", family="monospace")
            )
        ]
    )
    return fig


def create_site_temperature_chart():
    """Bar chart showing temperature by site during heat event."""
    sites = results["heat_events"]["July 2023 Phoenix Heat Wave"]
    site_names = []
    temps = []
    colors = []

    for site_id, data in sites.items():
        name = data["site_name"].replace(" High School", "")
        site_names.append(name)
        temp = data["daily_data"][0]["temp_c"]
        temps.append(temp)
        level = data["daily_data"][0].get("policy_level", "green")
        colors.append("#EF4444" if level == "black" else
                      "#F97316" if level == "orange" else
                      "#EAB308" if level == "yellow" else "#10B981")

    fig = go.Figure(data=[
        go.Bar(
            x=site_names,
            y=temps,
            marker_color=colors,
            text=[f"{t:.1f}°C" for t in temps],
            textposition="outside",
            textfont=dict(size=14, color="white"),
        )
    ])
    fig.add_hline(
        y=40, line_dash="dash", line_color="#F59E0B",
        annotation_text="NIOSH Danger Threshold (40°C / 104°F)",
        annotation_position="top"
    )
    fig.add_hline(
        y=38, line_dash="dot", line_color="#EF4444",
        annotation_text="BLACK Level (38°C / 100.4°F)",
        annotation_position="bottom"
    )
    fig.update_layout(
        title=dict(
            text="🌡️ Peak Temperatures by Site — July 15, 2023 (4:00 PM)",
            font=dict(size=16)
        ),
        yaxis_title="Temperature (°C)",
        template="plotly_dark",
        height=450,
        yaxis_range=[35, 45],
    )
    return fig


def create_policy_heatmap():
    """Heatmap of policy levels across sites and time slots."""
    # Fetch data from quick fetch results
    heat_data = [
        # 12:00 slot
        ["Mountain Pointe", "12:00 PM", 41.1, "BLACK"],
        ["Desert Vista", "12:00 PM", 41.2, "BLACK"],
        ["Chandler", "12:00 PM", 41.5, "BLACK"],
        ["Hamilton", "12:00 PM", 41.4, "BLACK"],
        ["Saguaro", "12:00 PM", 41.2, "BLACK"],
        ["Corona del Sol", "12:00 PM", 41.4, "BLACK"],
        # 4:00 PM slot
        ["Mountain Pointe", "4:00 PM", 42.3, "BLACK"],
        ["Desert Vista", "4:00 PM", 42.3, "BLACK"],
        ["Chandler", "4:00 PM", 42.4, "BLACK"],
        ["Hamilton", "4:00 PM", 42.2, "BLACK"],
        ["Saguaro", "4:00 PM", 42.2, "BLACK"],
        ["Corona del Sol", "4:00 PM", 42.4, "BLACK"],
    ]

    sites = list(dict.fromkeys([r[0] for r in heat_data]))
    times = ["12:00 PM", "4:00 PM"]

    z = []
    text = []
    for site in sites:
        row = [r[2] for r in heat_data if r[0] == site]
        txt = [f"{r}°C<br>{a}" for r, a in
               [(r[2], r[3]) for r in heat_data if r[0] == site]]
        z.append(row)
        text.append(txt)

    fig = go.Figure(data=go.Heatmap(
        z=z, x=times, y=sites,
        text=text, texttemplate="%{text}",
        colorscale=[[0, "#10B981"], [0.5, "#F59E0B"], [1, "#DC2626"]],
        zmin=30, zmax=45,
        textfont={"size": 14, "color": "white"},
    ))
    fig.update_layout(
        title=dict(
            text="🗺️ Temperature Heatmap: All Sites × Time Slots",
            font=dict(size=16)
        ),
        template="plotly_dark",
        height=400,
    )
    return fig


def create_detection_summary():
    """Gauge showing recall percentage from eval_results.json."""
    recall_pct = results["summary"]["recall"] * 100
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=recall_pct,
        number={"suffix": "%", "font": {"size": 72, "color": "#10B981"}},
        title={"text": "Detection Rate (Recall)", "font": {"size": 18}},
        delta={"reference": 80, "increasing": {"color": "#10B981"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#10B981"},
            "steps": [
                {"range": [0, 50], "color": "#FCA5A5"},
                {"range": [50, 80], "color": "#FDE68A"},
                {"range": [80, 100], "color": "#BBF7D0"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.75,
                "value": 100,
            },
        },
    ))
    fig.update_layout(
        template="plotly_dark",
        height=300,
    )
    return fig


def create_savings_gauge():
    """Gauge showing cost savings from eval_results.json."""
    savings = results["summary"]["cost_delta"]["savings"]
    fig = go.Figure(go.Indicator(
        mode="number+delta",
        value=savings,
        number={"prefix": "$", "font": {"size": 64, "color": "#10B981"}},
        title={"text": "Cost Savings per Event (6 sites)", "font": {"size": 16}},
    ))
    fig.update_layout(
        template="plotly_dark",
        height=250,
    )
    return fig


def create_microclimate_chart():
    """Show temperature variation between sites (microclimate story)."""
    sites = results["heat_events"]["July 2023 Phoenix Heat Wave"]
    site_names = []
    temps = []

    for site_id, data in sites.items():
        site_names.append(data["site_name"].replace(" High School", ""))
        temps.append(data["daily_data"][0]["temp_c"])

    temp_range = max(temps) - min(temps)
    hottest = site_names[temps.index(max(temps))]
    coolest = site_names[temps.index(min(temps))]

    fig = go.Figure(data=[
        go.Bar(
            x=site_names,
            y=temps,
            marker_color=temps,
            marker_colorscale="YlOrRd",
            marker_cmin=min(temps) - 0.5,
            marker_cmax=max(temps) + 0.5,
            text=[f"{t:.1f}°C" for t in temps],
            textposition="outside",
        )
    ])
    fig.add_annotation(
        x=0.5, y=1.15, xref="paper", yref="paper",
        text=f"Microclimate spread: {temp_range:.1f}°C "
             f"({hottest} vs {coolest})",
        showarrow=False, font=dict(size=14, color="#F59E0B"),
    )
    fig.update_layout(
        title=dict(
            text="🔬 Why a Single Weather Station Isn't Enough",
            font=dict(size=16)
        ),
        yaxis_title="Peak Temperature (°C)",
        template="plotly_dark",
        height=400,
        yaxis_range=[39, 44],
    )
    return fig
