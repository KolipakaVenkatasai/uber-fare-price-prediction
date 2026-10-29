# FareSense - Uber Fare Predictor (Flask)

Place this `webapp/` folder inside your `uber_fare_price/` project (next to `models/` and `data/`).

## Run
    cd uber_fare_price/webapp
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000 (first start takes ~10 s while the 1.2 GB model loads).

Pages: / Predict, /dashboard Insights, /history, /about
API: POST /api/predict, POST /api/hourly, GET /api/stats, GET/DELETE /api/history, GET /health


## India edition
Locations: Hyderabad & Visakhapatnam. Fares shown in INR; fares are calibrated to Indian cab tariffs (base + per-km, see `RATES` in `app.py`) instead of a raw dollar conversion.
