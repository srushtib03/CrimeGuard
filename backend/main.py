from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
import json, pickle, sqlite3, math
import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
import auth
import olap_questions

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / "models"
DATA_DIR = BASE / "data"

with open(MODEL_DIR / "crimeguard_model_metadata.json", encoding="utf-8") as f:
    METADATA = json.load(f)
with open(MODEL_DIR / "crimeguard_features.json", encoding="utf-8") as f:
    FEATURES = json.load(f)
with open(MODEL_DIR / "crimeguard_categorical_features.json", encoding="utf-8") as f:
    CAT_FEATURES = json.load(f)
with open(MODEL_DIR / "crimeguard_rate_lookups.pkl", "rb") as f:
    RATE = pickle.load(f)

CATBOOST = CatBoostClassifier()
CATBOOST.load_model(str(MODEL_DIR / "crimeguard_final_catboost.cbm"))

RF_BUNDLE = None
RF_META = None
rf_path = MODEL_DIR / "random_forest_benchmark.joblib"
rf_meta_path = MODEL_DIR / "random_forest_metadata.json"
if rf_path.exists():
    RF_BUNDLE = joblib.load(rf_path)
if rf_meta_path.exists():
    with open(rf_meta_path, encoding="utf-8") as f:
        RF_META = json.load(f)

DB_PATH = DATA_DIR / "CrimeGuard_Warehouse.db"
olap_questions.init(DB_PATH)

app = FastAPI(title="CrimeGuard API", version="1.2.0")

async def auth_gate(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api") or path == "/api" or path in auth.PUBLIC:
        return await call_next(request)
    header = request.headers.get("authorization", "")
    user = auth.parse_token(header[7:]) if header.lower().startswith("bearer ") else None
    if not user:
        return JSONResponse({"detail": "Please sign in to continue."}, status_code=401)
    denied = auth.check_access(path, user["role"])
    if denied:
        return JSONResponse({"detail": denied}, status_code=403)
    request.state.user = user
    return await call_next(request)

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_gate)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PredictionInput(BaseModel):
    primary_type: str = Field(alias="Primary Type")
    iucr: str = Field(alias="IUCR")
    fbi_code: str = Field(alias="FBI Code")
    description: str = Field(alias="Description")
    location_description: str = Field(alias="Location Description")
    district: str = Field(alias="District")
    community_area: str = Field(alias="Community Area")
    latitude: float
    longitude: float
    hour: int = Field(ge=0, le=23)
    day: int = Field(ge=1, le=31)
    month: int = Field(ge=1, le=12)
    day_of_week: int = Field(ge=0, le=6)
    model: str = "catboost"

    class Config:
        populate_by_name = True


def build_base(row: PredictionInput):
    h, m, dow = row.hour, row.month, row.day_of_week
    return pd.DataFrame([{
        "Primary Type": str(row.primary_type), "IUCR": str(row.iucr), "FBI Code": str(row.fbi_code),
        "Description": str(row.description), "Location Description": str(row.location_description),
        "District": str(row.district), "Community Area": str(row.community_area),
        "Latitude": float(np.clip(row.latitude, -90, 90)), "Longitude": float(np.clip(row.longitude, -180, 180)),
        "Hour": h, "Day": row.day, "Month": m, "DayOfWeekNum": dow,
        "IsWeekend": int(dow >= 5), "IsNight": int(h < 6 or h >= 22),
        "Hour_sin": math.sin(2 * math.pi * h / 24), "Hour_cos": math.cos(2 * math.pi * h / 24),
        "Month_sin": math.sin(2 * math.pi * m / 12), "Month_cos": math.cos(2 * math.pi * m / 12),
        "DayOfWeek_sin": math.sin(2 * math.pi * dow / 7), "DayOfWeek_cos": math.cos(2 * math.pi * dow / 7),
    }])


def _norm_key(col, series):
    if col == "Hour":
        return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")
    if col == "Community Area":
        def fmt(v):
            try: return str(float(v))
            except (TypeError, ValueError): return str(v)
        return series.astype(object).map(fmt)
    if col == "District":
        def fmt(v):
            try: return str(int(float(v)))
            except (TypeError, ValueError): return str(v)
        return series.astype(object).map(fmt)
    return series.astype(object).map(str)


def enhance(base):
    out = base.copy()
    for name, lookup in RATE["groups"].items():
        keys = [c for c in lookup.columns if c not in ("ArrestRate", "LogCount")]
        left = pd.DataFrame({k: _norm_key(k, base[k]) for k in keys})
        right = lookup.copy()
        for k in keys:
            right[k] = _norm_key(k, right[k])
        merged = left.merge(right, on=keys, how="left")
        out[f"{name}_ArrestRate"] = merged["ArrestRate"].fillna(RATE["global_rate"]).to_numpy(dtype=float)
        out[f"{name}_LogCount"] = merged["LogCount"].fillna(0).to_numpy(dtype=float)
    for c in CAT_FEATURES:
        out[c] = _norm_key(c, out[c]) if c in ("District", "Community Area") else out[c].fillna("UNKNOWN").astype(str)
    return out[FEATURES]


def normalize_metrics(perf):
    # Metadata stores CatBoost test metrics with explicit test_* names,
    # while the frontend uses a common metric schema for every model.
    return {
        "accuracy": float(perf.get("accuracy", perf.get("test_accuracy", 0.0))),
        "precision": float(perf.get("precision", perf.get("test_precision", 0.0))),
        "recall": float(perf.get("recall", perf.get("test_recall", 0.0))),
        "f1": float(perf.get("f1", perf.get("test_f1", 0.0))),
        "roc_auc": float(perf.get("roc_auc", perf.get("test_roc_auc", 0.0))),
    }

def model_catalog():
    cat_perf = normalize_metrics(METADATA["performance"])
    result = [{
        "id": "catboost", "short_name": "CatBoost", "name": METADATA["model_name"],
        "description": "The deployed enhanced model. It handles categorical crime fields natively and is the recommended model.",
        "threshold": METADATA["decision_threshold"], "metrics": cat_perf, "deployed": True,
        "explanation": "SHAP local explanation"
    }]
    if RF_BUNDLE is not None and RF_META is not None:
        result.append({
            "id": "random_forest", "short_name": "Random Forest", "name": RF_META["model_name"],
            "description": "A benchmark ensemble using the same 47-feature pipeline. Its accuracy is intentionally shown as a baseline comparison.",
            "threshold": RF_META["decision_threshold"], "metrics": normalize_metrics(RF_META["performance"]), "deployed": False,
            "explanation": "Feature importance"
        })
    return result

@app.get("/")
def root():
    return {"message": "CrimeGuard API is running", "docs": "/docs", "health": "/api/health", "version": "1.1.0"}

@app.get("/api")
def api_root():
    return {"message": "CrimeGuard API is running", "health": "/api/health", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {"status": "online", "model": METADATA["model_name"], "threshold": METADATA["decision_threshold"], "features": METADATA["total_features"], "warehouse": DB_PATH.exists(), "models": len(model_catalog()), "auth": True}

@app.get("/api/model")
def model_info():
    return METADATA

@app.get("/api/models")
def models():
    return model_catalog()

@app.get("/api/options")
def options():
    with open(DATA_DIR / "options.json", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/predict")
def predict(payload: PredictionInput, request: Request):
    if payload.model.lower().strip() in ("random_forest", "random forest", "rf") and request.state.user["role"] != "crime_branch":
        raise HTTPException(status_code=403, detail="The Random Forest benchmark is available to Crime Branch accounts only.")
    try:
        base = build_base(payload)
        X = enhance(base)
        requested = payload.model.lower().strip()

        if requested in ("random_forest", "random forest", "rf") and RF_BUNDLE is not None:
            encoder = RF_BUNDLE["encoder"]
            rf = RF_BUNDLE["model"]
            cats = RF_BUNDLE["categorical_features"]
            nums = RF_BUNDLE["numeric_features"]
            for c in cats:
                X[c] = X[c].astype(str)
            matrix = np.hstack([encoder.transform(X[cats]), X[nums].to_numpy(dtype=float)])
            probability = float(rf.predict_proba(matrix)[0, 1])
            threshold = float(RF_BUNDLE.get("threshold", RF_META["decision_threshold"]))
            prediction = int(probability >= threshold)
            importance = rf.feature_importances_
            ordered = sorted(zip(cats + nums, importance), key=lambda z: abs(z[1]), reverse=True)[:10]
            explanation = [{"feature": f, "value": float(v)} for f, v in ordered]
            return {"prediction": prediction, "label": "Arrest" if prediction else "No Arrest", "probability": probability,
                    "threshold": threshold, "model": "random_forest", "model_name": "Random Forest",
                    "explanation_title": "Top feature importance", "explanation_type": "Random Forest feature importance",
                    "explanation": explanation}

        for c in CAT_FEATURES:
            X[c] = X[c].astype(object)
        cat_idx = [X.columns.get_loc(c) for c in CAT_FEATURES]
        pool = Pool(X, cat_features=cat_idx)
        probability = float(CATBOOST.predict_proba(pool)[0, 1])
        threshold = float(METADATA["decision_threshold"])
        prediction = int(probability >= threshold)
        shap = CATBOOST.get_feature_importance(pool, type="ShapValues")[0, :-1]
        explanation = sorted([{"feature": f, "value": float(v)} for f, v in zip(FEATURES, shap)], key=lambda x: abs(x["value"]), reverse=True)[:10]
        return {"prediction": prediction, "label": "Arrest" if prediction else "No Arrest", "probability": probability,
                "threshold": threshold, "model": "catboost", "model_name": "CatBoost",
                "explanation_title": "Top explanation signals", "explanation_type": "Local SHAP (log-odds)",
                "explanation": explanation}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def db_query(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params).to_dict(orient="records")

@app.get("/api/summary")
def summary():
    return {"crime": db_query("SELECT * FROM olap_crime ORDER BY crime_count DESC"), "district": db_query("SELECT * FROM olap_district ORDER BY crime_count DESC"), "hourly": db_query("SELECT * FROM olap_hourly ORDER BY hour"), "monthly": db_query("SELECT * FROM olap_monthly ORDER BY Year, Month")}

@app.get("/api/hotspots/kmeans")
def kmeans():
    return {"centers": pd.read_csv(DATA_DIR / "CrimeGuard_KMeans_Centers.csv").to_dict("records"), "silhouette": pd.read_csv(DATA_DIR / "CrimeGuard_KMeans_Silhouette.csv").to_dict("records")}

@app.get("/api/hotspots/dbscan")
def dbscan():
    return {"centers": pd.read_csv(DATA_DIR / "CrimeGuard_DBSCAN_Centers.csv").to_dict("records")}

@app.get("/api/shap")
def shap():
    return pd.read_csv(DATA_DIR / "CrimeGuard_SHAP_Feature_Importance.csv").head(20).to_dict("records")

@app.get("/api/apriori")
def apriori():
    return pd.read_csv(DATA_DIR / "CrimeGuard_Apriori_Rules.csv").head(100).to_dict("records")

@app.get("/api/olap/rollup")
def rollup():
    return {"year": db_query("SELECT Year, SUM(crime_count) crime_count, SUM(arrests) arrests FROM olap_monthly GROUP BY Year ORDER BY Year"), "quarter": db_query("SELECT Year, Quarter, SUM(crime_count) crime_count, SUM(arrests) arrests FROM olap_monthly GROUP BY Year, Quarter ORDER BY Year, Quarter"), "month": db_query("SELECT * FROM olap_monthly ORDER BY Year, Month")}

@app.get("/api/olap/drilldown")
def drilldown():
    return {"year": db_query("SELECT Year, SUM(crime_count) crime_count, SUM(arrests) arrests FROM olap_monthly GROUP BY Year"), "month": db_query("SELECT * FROM olap_monthly ORDER BY Year, Month"), "day": db_query("SELECT * FROM olap_daily ORDER BY Full_Date LIMIT 100")}

@app.get("/api/olap/slice")
def slice_olap(district: str):
    return db_query("SELECT District, crime_type, crime_count, arrests FROM olap_district_crime WHERE District = ? ORDER BY crime_count DESC", (district,))

@app.get("/api/olap/dice")
def dice(districts: str = "", crimes: str = "THEFT,BATTERY,ASSAULT"):
    ds = [x.strip() for x in districts.split(",") if x.strip()]; cs = [x.strip() for x in crimes.split(",") if x.strip()]
    if not ds: ds = [r["District"] for r in db_query("SELECT District FROM olap_district ORDER BY crime_count DESC LIMIT 3")]
    if not cs: cs = ["THEFT","BATTERY","ASSAULT"]
    dmarks = ",".join(["?"]*len(ds)); cmarks = ",".join(["?"]*len(cs))
    return db_query(f"SELECT District, crime_type, crime_count, arrests FROM olap_district_crime WHERE District IN ({dmarks}) AND crime_type IN ({cmarks}) ORDER BY crime_count DESC", tuple(ds+cs))

@app.get("/api/olap/pivot")
def pivot():
    return db_query("SELECT District, crime_type, crime_count FROM olap_district_crime")


# ---------------------------------------------------------------- authentication
class LoginInput(BaseModel):
    username: str
    password: str
    role: str

@app.post("/api/auth/login")
def login(body: LoginInput):
    if body.role not in auth.ROLES:
        raise HTTPException(status_code=400, detail="Choose Police or Crime Branch.")
    user, error = auth.authenticate(body.username, body.password, body.role)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return {"token": auth.make_token(user), "user": {"username": user["username"], "name": user["name"], "role": user["role"], "role_label": auth.ROLES[user["role"]]}}

@app.get("/api/auth/me")
def me(request: Request):
    u = request.state.user
    return {"username": u["u"], "name": u["name"], "role": u["role"], "role_label": auth.ROLES[u["role"]]}


# ---------------------------------------------------------------- question-driven OLAP (Crime Branch)
@app.get("/api/olap/catalog")
def olap_catalog():
    return olap_questions.catalog()

@app.get("/api/olap/ask")
def olap_ask(request: Request, id: str):
    if id not in olap_questions.REG:
        raise HTTPException(status_code=404, detail="Unknown OLAP question")
    return olap_questions.ask(id, dict(request.query_params))


# ---------------------------------------------------------------- mining charts (Crime Branch)
def _sample(df, n, seed=7):
    return df if len(df) <= n else df.sample(n, random_state=seed)

@app.get("/api/mining/kmeans")
def mining_kmeans():
    pts = pd.read_csv(DATA_DIR / "CrimeGuard_KMeans_Hotspots.csv")
    centers = pd.read_csv(DATA_DIR / "CrimeGuard_KMeans_Centers.csv")
    sil = pd.read_csv(DATA_DIR / "CrimeGuard_KMeans_Silhouette.csv")
    sizes = pts["cluster"].value_counts().sort_index()
    return {"points": _sample(pts, 3000).round(5).to_dict("records"), "centers": centers.to_dict("records"),
            "silhouette": sil.to_dict("records"), "best_k": int(sil.loc[sil["silhouette"].idxmax(), "k"]),
            "sizes": [{"cluster": int(k), "size": int(v), "share": round(v / len(pts) * 100, 1)} for k, v in sizes.items()], "total": int(len(pts))}

@app.get("/api/mining/dbscan")
def mining_dbscan():
    pts = pd.read_csv(DATA_DIR / "CrimeGuard_DBSCAN_Hotspots.csv")
    centers = pd.read_csv(DATA_DIR / "CrimeGuard_DBSCAN_Centers.csv").set_index("cluster")
    noise = int((pts["cluster"] == -1).sum())
    core = pts[pts["cluster"] != -1]
    sizes = core["cluster"].value_counts()
    top = [{"cluster": int(k), "size": int(v), "Latitude": float(centers.loc[k, "Latitude"]), "Longitude": float(centers.loc[k, "Longitude"])} for k, v in sizes.head(15).items() if k in centers.index]
    keep = [int(k) for k in sizes.head(15).index]
    parts = [_sample(pts[pts["cluster"] == -1], 1200)]
    parts += [_sample(core[core["cluster"] == k], 120) for k in keep]
    parts.append(_sample(core[~core["cluster"].isin(keep)], 600))
    shown = pd.concat(parts, ignore_index=True)
    shown["cluster"] = shown["cluster"].astype(int)
    return {"points": shown.round(5).to_dict("records"), "top_clusters": top, "n_clusters": int(core["cluster"].nunique()), "noise": noise,
            "noise_share": round(noise / len(pts) * 100, 1), "total": int(len(pts)), "top_ids": [int(k) for k in sizes.head(15).index]}

@app.get("/api/mining/apriori")
def mining_apriori():
    rules = pd.read_csv(DATA_DIR / "CrimeGuard_Apriori_Rules.csv")
    items = pd.read_csv(DATA_DIR / "CrimeGuard_Frequent_Itemsets.csv").sort_values("support", ascending=False)
    return {"rules": rules.round(4).to_dict("records"), "itemsets": items.head(20).round(4).to_dict("records")}
