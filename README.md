# CrimeGuard — Crime Pattern & Hotspot Intelligence System

CrimeGuard combines Machine Learning, Explainable AI, Data Mining, Data Warehousing and OLAP analytics in one interactive React + FastAPI application.

## Features
- **Secure login** for Police and Crime Branch with role-based access (see below)
- **Guided workflow** stepper + Back/Next buttons on every page
- **Question-driven OLAP explorer**: 24 dropdown questions covering Roll-up, Drill-down, Slice, Dice and Pivot
- **Real charts** for K-Means (scatter + silhouette), DBSCAN (density scatter + cluster sizes) and Apriori (support/confidence/lift bubbles)
- Arrest prediction with deployed Enhanced CatBoost
- Random Forest benchmark model selector
- Model comparison with real test metrics
- Local SHAP explanation for CatBoost / feature importance for Random Forest
- K-Means and DBSCAN hotspot maps
- Crime trends and category analytics
- Apriori association rules
- Interactive OLAP: Roll-up, Drill-down, Slice, Dice and Pivot
- Simple/Analyst view for non-technical and technical audiences
- Animated 3D-style spatial intelligence hero visualization
- Command Center (Ctrl/Cmd + K)

## Run backend
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

## Run frontend
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

The Vite proxy forwards `/api` requests to FastAPI on port 8000.


### Pattern Mining UI
The Pattern Mining page includes animated 3D-style K-Means and DBSCAN spatial visualizations driven by the saved cluster centers.


## Login & roles

| Role | Demo username | Demo password | Can open |
|------|---------------|---------------|----------|
| Police | `police` | `Police@123` | Overview, Prediction (CatBoost), Crime Map, Trends |
| Crime Branch | `crimebranch` | `Crime@123` | Everything above + Explainability, Pattern Mining, OLAP Explorer, Model Comparison, Random Forest benchmark |

* Pick the unit on the login screen, then sign in (the role must match the account).
* Access is enforced **on the server**: a Police token calling a Crime-Branch endpoint receives `403`; no/invalid token receives `401` and the app returns to the login page.
* Passwords are stored as salted PBKDF2-SHA256 hashes in `backend/data/users.json`; sessions are signed, expiring (8 h) tokens. No extra Python packages are needed.
* After 5 wrong attempts an account is locked for 1 minute.
* Add your own accounts: `cd backend && python manage_users.py add inspector1 police "Inspector One"` (use role `police` or `crime_branch`; `python manage_users.py list` shows accounts).
* For a real deployment change the demo passwords and set the `CRIMEGUARD_SECRET` environment variable.

## Guided flow

The stepper at the top of every page shows where you are. Police: Overview → Predict → Hotspots → Trends.
Crime Branch: Overview → Predict → Explain → Hotspots → Trends → Mine patterns → Ask the warehouse → Compare models.
Use the **Next step** button at the bottom of each page to move through the story.

## OLAP Explorer (question-driven)

1. Choose an operation (Roll-up, Drill-down, Slice, Dice, Pivot).
2. Pick a question from the dropdown (and any parameter dropdowns, e.g. quarter, district, crime type).
3. Read the plain-English answer, the chart, or the pivot heat-map. The numbers are available behind "Show the numbers".

Examples: *How many crimes happened in each quarter?* · *Drill into a quarter: which months made it up?* · *Show only one district: what crimes happen there?* · *Compare two districts for one crime type across the quarters* · *Pivot: districts against the top crime types*.
All answers are computed from the existing warehouse (`fact_crime` + `dim_crime` + `dim_location`), opened read-only. Totals reconcile with the original `olap_*` summary tables.

## API additions

`POST /api/auth/login`, `GET /api/auth/me`, `GET /api/olap/catalog`, `GET /api/olap/ask?id=...`, `GET /api/mining/kmeans|dbscan|apriori`.
All previous endpoints are unchanged (they now require a valid login token, except `/api/health`).

## What changed in this version

Modified: `backend/main.py`, `frontend/src/App.jsx`, `frontend/src/services/api.js`.
Added: `backend/auth.py`, `backend/manage_users.py`, `backend/olap_questions.py`, `backend/data/users.json`, `frontend/src/components/*`, `frontend/src/newfeatures.css`.
Untouched: every data file, trained model, the notebook and `original_artifacts/`.
