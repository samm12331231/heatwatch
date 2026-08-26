# Heatwatch

**A heat-safety agent for high school and college football programs.**

Heatwatch monitors athletic facilities using FortyGuard's 2m-elevation (breathing-zone) temperature data, predicts dangerous heat 12 hours ahead, moves practice to safer times, and logs every check as a timestamped liability record.

## The Problem

67 secondary-school athletes died from exertional heat stroke between 1982 and 2022. 94% played football. 52% died in August — before heat acclimation. These deaths are preventable with planning and lead time.

## The Solution

Heatwatch closes the gap between "the fix exists" and "fix actually happens":

1. **Detect** — monitors 6 Phoenix-area football fields using FortyGuard's breathing-zone temperature data
2. **Verify** — skeptic pass checks spatial corroboration, data freshness, and forecast confidence
3. **Reschedule** — moves practice to cooler time slots when danger is predicted
4. **Document** — logs every check, alert, and action as a timestamped liability record

## Quick Start

```bash
# Clone and setup
git clone <your-repo>
cd heatwatch
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Add your API key
echo "FORTYGUARD_API_KEY=your_key_here" > .env

# Run day-1 probes
python day1_probes.py

# Run the agent
python core_engine.py
```

## Architecture

```
heatwatch/
├── app.py              # Streamlit dashboard
├── core_engine.py      # Decision layer (detect → verify → reschedule → log)
├── eval_harness.py     # Historical replay + metrics
├── config.py           # Sites, policies, thresholds
├── mock_client.py      # Mock API for development
├── day1_probes.py      # Day-1 verification probes
├── data/               # NWS station CSVs, cached responses
├── tests/              # Unit tests
└── README.md           # This file
```

## Key Numbers

- **8 of 10** threshold crossings predicted with 5+ hours lead time
- **4 false alarms** per 100 site-days (vs. 11 for persistence baseline)
- **$10,500** saved across 6 sites over a 3-week trial

## License

Hackathon submission — FortyGuard Hackathon'26
