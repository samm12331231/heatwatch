# Heatwatch

**Autonomous heat-safety agent for youth athletics. FortyGuard Hackathon 2026 — Track 6 (Agentic).**

## What it does

Heatwatch takes FortyGuard's 2m spatial temperature data and makes a decision: can athletes practice right now, and if not, when?

1. **Detect** — fetches temperature across 6 Phoenix-area football fields at 100m resolution
2. **Estimate** — computes WBGT (Wet Bulb Globe Temperature) from spatial temperature + humidity + solar + wind
3. **Classify** — maps WBGT to AIA 2026-2027 policy tiers (82/87/90/92°F thresholds)
4. **Verify** — skeptic check validates data credibility across nearby sites (spatial corroboration)
5. **Decide** — asymmetric cost model weighs false alarm vs missed incident
6. **Reschedule** — recommends safest practice window when danger is predicted
7. **Document** — hashes every decision into a tamper-evident SQLite audit trail

## Quick Start

```bash
git clone https://github.com/samm12331231/heatwatch.git
cd heatwatch
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py

# Run validation (reproduces key metrics)
python validate.py

# Run the agent (writes audit trail)
python core_engine.py
```

No API key required for demo — uses historical replay data with mock client.

## Architecture

```
heatwatch/
├── app.py              # Streamlit dashboard (4 tabs: Monitor, Analysis, Schedule, Audit)
├── core_engine.py      # Autonomous pipeline: detect → WBGT → policy → skeptic → cost → reschedule → log
├── config.py           # Sites, AIA thresholds (82/87/90/92°F), cost params, get_policy_level()
├── site_data.py        # Pre-computed temperature curves, WBGT readings per site
├── wbgt.py             # WBGT estimation (Liljegren-style: temp + humidity + solar + wind)
├── weekly_report.py    # Coach weekly heat report with risk heatmaps
├── mock_client.py      # Deterministic mock API for demo/development
├── eval_harness.py     # Historical replay evaluation (recall, false alarm rate)
├── validate.py         # One-click validation script
└── data/               # KPHX station data, cached FortyGuard responses
```

## Key Numbers

| Metric | Value |
|--------|-------|
| Recall | 100% — every dangerous hour detected |
| False alarm rate | 0% — no unnecessary cancellations |
| Sites monitored | 6 Phoenix-area high school fields |
| Lookahead | 12 hours |
| Policy standard | AIA 2026-2027 (UIL/TAPPS/GHSA/NCAA aligned) |
| Primary metric | WBGT (Wet Bulb Globe Temperature) |
| Audit trail | SHA-256 hash-chained SQLite |

## WBGT vs Heat Index

Heat index is defined for a person walking in the shade. WBGT incorporates solar radiation and wind — the actual conditions athletes face. AIA, NCAA, NATA, and OSHA all use WBGT for athletic heat safety. Heatwatch estimates WBGT from FortyGuard spatial data using a Liljegren-style model.

When solar/wind data is unavailable, Heatwatch uses conservative daytime estimates (900 W/m² solar, 1.5 m/s wind) and flags output as estimated. This is intentionally conservative — better to overestimate risk than underestimate it for athlete safety.

## FortyGuard Integration

- **Data source**: FortyGuard 2m-elevation spatial temperature at 100m resolution
- **Sites**: 6 Phoenix-area high school football fields with 2km bounding polygons
- **API**: Asynchronous polling via activity_id (create_heatmap → poll status → fetch results)
- **Value**: Airport sensors miss 3-7°F urban heat island effects on actual turf

## AI Tools Used

- **Gemini** — VC/judge perspective review
- **Claude** — Systems architecture review (found the two-brain bug, WBGT formula issues)
- **ChatGPT** — UX/UI review (CSS polish, layout hierarchy)
- **Perplexity** — Climate science verification (WBGT thresholds, humidity estimates)
- **Kimi** — Synthesis tie-breaker (prioritized all feedback into actionable checklist)

## License

Hackathon submission — FortyGuard Hackathon 2026
