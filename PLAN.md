# Heatwatch — Project Progress

## What's Done ✅

- [x] **config.py** — 6 Phoenix high school football fields with unique ~2km polygons
- [x] **core_engine.py** — Full decision pipeline: fetch → heat index → policy → cost → reschedule → memo → audit trail (SQLite)
- [x] **fetch_historical.py** — Clean data fetcher with caching and rate limiting
- [x] **eval_harness.py** — Evaluation against real historical data (recall, false alarm rate, cost delta)
- [x] **app.py** — Streamlit UI (you're customizing this)
- [x] **FortyGuard API** — Verified working, returns real 42°C temps for Phoenix July 2023
- [x] **Polygon fix** — Each site has unique polygon (fixed the duplicate-polygon bug)
- [x] **Core engine test** — `python core_engine.py 2023-07-15 14:00` returns real temps and decisions
- [x] **Cleaned up** — Removed stale test/debug scripts

## What Needs Doing 🔧

### Priority 1: Get real eval data
```bash
cd "/Users/sampk/Downloads/fortyguard hackathon"
source venv/bin/activate
cd heatwatch
python fetch_historical.py
```
This fetches 1 heat day + 3 null days = ~36 API calls (~6 min).
After it finishes:
```bash
python eval_harness.py
```

### Priority 2: Polish the UI
- You're building the Streamlit UI yourself (not AI-sloppy)
- It needs to show: 6 sites, temperatures, policy level, before/after schedule, cost analysis, audit log

### Priority 3: Record demo
- 3-minute screen recording showing the working app
- Use the 60-second pitch script

### Priority 4: Write 500-word description
- Ready to fill in on submission day

### Priority 5: Deploy + submit
- Push to GitHub
- Deploy on Streamlit Cloud
- Submit by Aug 29 (2 days early)

## Architecture

```
FortyGuard API (2m breathing-zone temp)
        ↓
  core_engine.py (fetch → heat index → policy → cost → reschedule)
        ↓
  SQLite audit trail (hash-chained, tamper-evident)
        ↓
  Streamlit UI (real-time dashboard)
        ↓
  eval_harness.py (recall, false alarms, cost savings vs naive)
```

## Key Files
| File | Purpose |
|------|---------|
| config.py | 6 sites, thresholds, API settings, eval config |
| core_engine.py | Decision pipeline + heat index + cost analysis |
| fetch_historical.py | One-time data fetch for eval |
| eval_harness.py | Compute detection metrics |
| app.py | Streamlit UI |
| fortyguard/ | API client (from quickstart repo) |
| data/fortyguard/ | Cached API responses |
| heatwatch_audit.db | SQLite audit trail |

## API Details
- `create_heatmap(polygon_aoi, start_date, start_time, filter_type=1, granularity=100)`
- Coordinates: `[longitude, latitude]`
- Filter types: 1=single hour, 2=range, 3=single day, 4=range of days
- Date range: 2021-01-01 to present
- Credits: 2,000,000 (hackathon free tier, all endpoints Premium)
