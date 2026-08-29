#!/bin/bash
cd "/Users/sampk/Downloads/fortyguard hackathon/heatwatch"
exec "/Users/sampk/Downloads/fortyguard hackathon/venv/bin/python" -m streamlit run app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 127.0.0.1 \
    --browser.gatherUsageStats false
