import json
import math
import os
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
MODEL_DIR = os.path.join(PROJECT_DIR, "models")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "history.db")
STATS_CACHE = os.path.join(BASE_DIR, "stats_cache.json")

FEATURES = [
    "pickup_longitude", "pickup_latitude", "dropoff_longitude", "dropoff_latitude",
    "passenger_count", "distance_km", "hour", "day", "month", "weekday",
]

# ---------------------------------------------------------------- India setup
# The model files are untouched (still the NYC-trained Random Forest + Linear Regression).
# Indian coordinates are shifted onto the NYC area the model knows (distance is preserved),
# and the predicted fare (USD) is converted to rupees.
# Fares are calibrated to typical Indian app-cab (Uber Go / Uber Auto-level) pricing instead of a
# raw dollar conversion: fare = base + rate per road-km, then nudged by the model's own signal
# (time of day, passengers, location pattern) within +/-, never changing the model files.
# Edit these numbers to match what you see in the real Uber app.
RATES = {                  # base fare (Rs), Rs per road-km, minimum fare (Rs)
    "Hyderabad":     {"base": 40, "per_km": 12.0, "min": 80},
    "Visakhapatnam": {"base": 35, "per_km": 10.5, "min": 65},
}
ROAD_FACTOR = 1.3          # road distance ~ 1.3 x straight-line distance
RATIO_CLAMP = (0.85, 1.35) # how far the model may raise/lower the baseline (e.g. peak hours)

CITIES = {                 # bounding boxes: (lat_min, lat_max, lon_min, lon_max)
    "Hyderabad":     (17.20, 17.60, 78.20, 78.70),
    "Visakhapatnam": (17.55, 17.92, 83.10, 83.50),
}
CITY_CENTERS = {"Hyderabad": (17.4126, 78.4071), "Visakhapatnam": (17.7231, 83.3013)}

# NYC area limits the model was trained on (used internally after the shift)
LAT_RANGE = (40.5, 41.0)
LON_RANGE = (-74.3, -73.6)
NYC_CENTER = (40.7396, -73.9800)

app = Flask(__name__)

# ----------------------------------------------------------------- models

print("Loading models (using the optimized Random Forest)...")
rf_model = joblib.load(
    os.path.join(MODEL_DIR, "final_model_candidate.pkl")
)
lr_model = joblib.load(
    os.path.join(MODEL_DIR, "linear_regression_model.pkl")
)
print("Models loaded.")


# ----------------------------------------------------------------- helpers
def haversine(lat1, lon1, lat2, lon2):
    """Same formula used in notebook 03_eda."""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nyc_baseline(dist_km):
    """Typical NYC fare (USD) for a trip of this length, fitted from the training data."""
    return 4.0 + 2.5 * dist_km


def inr_fare(usd, dist_km, city):
    """Realistic Indian fare: city tariff on road distance x model's relative adjustment."""
    r = RATES[city]
    base = r["base"] + r["per_km"] * dist_km * ROAD_FACTOR
    ratio = min(max(usd / nyc_baseline(dist_km), RATIO_CLAMP[0]), RATIO_CLAMP[1])
    return max(base * ratio, r["min"])


def city_of(lat, lon):
    for name, (a, b, c, d) in CITIES.items():
        if a <= lat <= b and c <= lon <= d:
            return name
    return None


def to_model_coords(lat, lon, city):
    """Shift an Indian point onto the NYC area, keeping its km offset from the city centre."""
    clat, clon = CITY_CENTERS[city]
    dlat = lat - clat
    dlon = (lon - clon) * math.cos(math.radians(clat)) / math.cos(math.radians(NYC_CENTER[0]))
    return NYC_CENTER[0] + dlat, NYC_CENTER[1] + dlon


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS predictions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created TEXT, pickup_lat REAL, pickup_lon REAL,
                drop_lat REAL, drop_lon REAL, passengers INTEGER,
                distance_km REAL, ride_time TEXT, rf_fare REAL, lr_fare REAL,
                pickup_name TEXT, drop_name TEXT)"""
        )


def validate(payload):
    try:
        p_lat = float(payload["pickup_latitude"])
        p_lon = float(payload["pickup_longitude"])
        d_lat = float(payload["dropoff_latitude"])
        d_lon = float(payload["dropoff_longitude"])
        pax = int(payload.get("passenger_count", 1))
    except (KeyError, TypeError, ValueError):
        return None, "Please select valid pickup and dropoff locations."

    c1, c2 = city_of(p_lat, p_lon), city_of(d_lat, d_lon)
    if not c1 or not c2:
        return None, "Locations must be inside Hyderabad or Visakhapatnam (Vizag)."
    if c1 != c2:
        return None, "Pickup and dropoff must be in the same city."
    if not 1 <= pax <= 6:
        return None, "Passenger count must be between 1 and 6."

    when = payload.get("datetime")
    try:
        dt = datetime.fromisoformat(when) if when else datetime.now()
    except ValueError:
        return None, "Invalid date/time."

    dist = haversine(p_lat, p_lon, d_lat, d_lon)
    if dist < 0.05:
        return None, "Pickup and dropoff are too close together."
    if dist >= 50:
        return None, "Distance must be under 50 km (the model's training range)."

    m_p_lat, m_p_lon = to_model_coords(p_lat, p_lon, c1)
    m_d_lat, m_d_lon = to_model_coords(d_lat, d_lon, c1)
    return dict(p_lat=p_lat, p_lon=p_lon, d_lat=d_lat, d_lon=d_lon, pax=pax, dt=dt, dist=dist,
                m_p_lat=m_p_lat, m_p_lon=m_p_lon, m_d_lat=m_d_lat, m_d_lon=m_d_lon, city=c1), None


def build_row(v):
    return pd.DataFrame(
        [[v["m_p_lon"], v["m_p_lat"], v["m_d_lon"], v["m_d_lat"], v["pax"], v["dist"],
          v["dt"].hour, v["dt"].day, v["dt"].month, v["dt"].weekday()]],
        columns=FEATURES,
    )


def compute_stats():
    if os.path.exists(STATS_CACHE):
        with open(STATS_CACHE) as f:
            return json.load(f)

    df = pd.read_csv(os.path.join(DATA_DIR, "final_uber_dataset.csv"))
    df = df[df["fare_amount"] > 0]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    hourly = df.groupby("hour")["fare_amount"].mean().round(2)
    weekly = df.groupby("weekday")["fare_amount"].mean().round(2)
    monthly = df.groupby("month")["fare_amount"].mean().round(2)
    pax = df.groupby("passenger_count").size()

    bins = [0, 1, 2, 3, 5, 8, 12, 20, 50]
    labels = ["0-1", "1-2", "2-3", "3-5", "5-8", "8-12", "12-20", "20+"]
    df["dbin"] = pd.cut(df["distance_km"], bins=bins, labels=labels)
    dist_fare = df.groupby("dbin", observed=True)["fare_amount"].mean().round(2)

    sample = df[df["fare_amount"] < 100].sample(1500, random_state=1)
    heat = df.sample(4000, random_state=2)

    try:
        pred = pd.read_csv(os.path.join(DATA_DIR, "predictions.csv"))
        from sklearn.metrics import mean_absolute_error, r2_score
        lr_r2 = float(r2_score(pred.iloc[:, 0], pred.iloc[:, 1]))
        lr_mae = float(mean_absolute_error(pred.iloc[:, 0], pred.iloc[:, 1]))
    except Exception:
        lr_r2, lr_mae = 0.728, None

    imp = sorted(zip(FEATURES, rf_model.feature_importances_), key=lambda x: -x[1])

    stats = {
        "total_rides": int(len(df)),
        "avg_fare": round(float(df["fare_amount"].mean()), 2),
        "median_fare": round(float(df["fare_amount"].median()), 2),
        "avg_distance": round(float(df["distance_km"].mean()), 2),
        "hourly": {"labels": [int(i) for i in hourly.index], "values": hourly.tolist()},
        "weekly": {"labels": [days[int(i)] for i in weekly.index], "values": weekly.tolist()},
        "monthly": {"labels": [int(i) for i in monthly.index], "values": monthly.tolist()},
        "passengers": {"labels": [int(i) for i in pax.index], "values": [int(x) for x in pax.values]},
        "dist_fare": {"labels": list(dist_fare.index.astype(str)), "values": dist_fare.tolist()},
        "scatter": [{"x": round(float(a), 2), "y": round(float(b), 2)}
                    for a, b in zip(sample["distance_km"], sample["fare_amount"])],
        "importance": {"labels": [k for k, _ in imp], "values": [round(float(v), 4) for _, v in imp]},
        "heat": [[round(float(a), 5), round(float(b), 5)]
                 for a, b in zip(heat["pickup_latitude"], heat["pickup_longitude"])
                 if LAT_RANGE[0] < a < LAT_RANGE[1] and LON_RANGE[0] < b < LON_RANGE[1]],
        "models": {
            "labels": ["Linear Regression", "Random Forest"],
            "r2": [round(lr_r2, 3), 0.795],
        },
        "lr_mae": round(lr_mae, 2) if lr_mae else None,
    }
    with open(STATS_CACHE, "w") as f:
        json.dump(stats, f)
    return stats


# ----------------------------------------------------------------- routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/api/predict", methods=["POST"])
def api_predict():
    v, err = validate(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400

    row = build_row(v)
    rf = float(rf_model.predict(row)[0])
    lr = float(lr_model.predict(row)[0])
    rf, lr = max(rf, 2.5), max(lr, 2.5)  # minimum fare floor (USD, model units)
    rf, lr = inr_fare(rf, v["dist"], v["city"]), inr_fare(lr, v["dist"], v["city"])  # -> rupees

    # confidence range from the spread of individual trees
    tree_preds = np.array([t.predict(row.values)[0] for t in rf_model.estimators_])
    low, high = np.percentile(tree_preds, [10, 90])
    low, high = inr_fare(low, v["dist"], v["city"]), inr_fare(high, v["dist"], v["city"])

    data = request.get_json()
    with db() as c:
        c.execute(
            "INSERT INTO predictions(created,pickup_lat,pickup_lon,drop_lat,drop_lon,passengers,"
            "distance_km,ride_time,rf_fare,lr_fare,pickup_name,drop_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), v["p_lat"], v["p_lon"], v["d_lat"],
             v["d_lon"], v["pax"], v["dist"], v["dt"].strftime("%Y-%m-%d %H:%M"), rf, lr,
             data.get("pickup_name", ""), data.get("dropoff_name", "")),
        )

    return jsonify(
        fare=round(rf, 2),
        low=round(float(low), 2),
        high=round(float(high), 2),
        linear_fare=round(lr, 2),
        city=v["city"],
        distance_km=round(v["dist"], 2),
        distance_mi=round(v["dist"] * 0.621371, 2),
        per_km=round(rf / v["dist"], 2),
        features={
            "hour": v["dt"].hour, "day": v["dt"].day, "month": v["dt"].month,
            "weekday": v["dt"].strftime("%A"),
        },
    )


@app.route("/api/hourly", methods=["POST"])
def api_hourly():
    """Predicted fare for the same trip at every hour of the day."""
    v, err = validate(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    rows = pd.concat([build_row({**v, "dt": v["dt"].replace(hour=h)}) for h in range(24)])
    preds = np.maximum(rf_model.predict(rows), 2.5)
    return jsonify(hours=list(range(24)),
                   fares=[round(float(inr_fare(p, v["dist"], v["city"])), 2) for p in preds])


@app.route("/api/stats")
def api_stats():
    """Cached stats are in USD / NYC coordinates; convert to rupees and show hotspots in Hyderabad."""
    st = json.loads(json.dumps(compute_stats()))  # deep copy
    city = "Hyderabad"
    avg_d = st["avg_distance"]
    avg_usd = st["avg_fare"]
    st["avg_fare"] = round(inr_fare(avg_usd, avg_d, city), 2)
    st["median_fare"] = round(inr_fare(st["median_fare"], avg_d * 0.8, city), 2)
    for key in ("hourly", "weekly", "monthly"):   # keep the model's relative pattern
        st[key]["values"] = [round(st["avg_fare"] * x / avg_usd, 2) for x in st[key]["values"]]
    mids = [0.5, 1.5, 2.5, 4, 6.5, 10, 16, 30]
    st["dist_fare"]["values"] = [round(inr_fare(nyc_baseline(m), m, city), 2) for m in mids][:len(st["dist_fare"]["values"])]
    for pt in st["scatter"]:
        pt["y"] = round(inr_fare(pt["y"], max(pt["x"], 0.1), city), 2)
    st["lr_mae"] = None
    clat, clon = CITY_CENTERS["Hyderabad"]
    cos_in = math.cos(math.radians(clat)) / math.cos(math.radians(NYC_CENTER[0]))
    st["heat"] = [[round(clat + (a - NYC_CENTER[0]), 5),
                   round(clon + (b - NYC_CENTER[1]) / cos_in, 5)] for a, b in st["heat"]]
    return jsonify(st)


@app.route("/api/history")
def api_history():
    with db() as c:
        rows = c.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/history/<int:pid>", methods=["DELETE"])
def api_history_delete(pid):
    with db() as c:
        c.execute("DELETE FROM predictions WHERE id=?", (pid,))
    return jsonify(ok=True)


@app.route("/api/history", methods=["DELETE"])
def api_history_clear():
    with db() as c:
        c.execute("DELETE FROM predictions")
    return jsonify(ok=True)


@app.route("/health")
def health():
    return jsonify(status="ok", model="RandomForestRegressor", trees=len(rf_model.estimators_))


init_db()

if __name__ == "__main__":
    compute_stats()
    app.run(debug=False, host="0.0.0.0", port=5000)
