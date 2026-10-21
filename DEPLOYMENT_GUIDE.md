# CrimeGuard Deployment Guide

This guide walks you through deploying **CrimeGuard** to **Render** (free cloud hosting) to get a live public URL, as well as running it locally with Docker or the local script.

---

## Architecture Overview

CrimeGuard is now configured as an **All-in-One Cloud Web Service**:
- **Frontend**: React + Vite + Leaflet + Recharts (compiled to static production bundle).
- **Backend**: FastAPI + CatBoost ML Predictor + SQLite OLAP Data Warehouse.
- **Unified Serving**: FastAPI serves both the API endpoints (`/api/...`) and the production React frontend SPA directly.
- **Zero-CORS**: Because the frontend and backend live on the same domain and port, cross-origin request issues are completely eliminated.

---

## Method 1: Deploy to Render (Recommended — Free & Automatic)

Render connects directly to your GitHub repository: [`srushtib03/CrimeGuard`](https://github.com/srushtib03/CrimeGuard).

### Step 1: Commit and Push Changes to GitHub
Open your terminal in the project directory and push the deployment files:
```bash
git add .
git commit -m "Configure production Docker and Render cloud deployment"
git push origin main
```

### Step 2: Create a Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/) and sign in (using GitHub).
2. Click **New +** and select **Web Service**.
3. Under **Connect a Git repository**, choose `srushtib03/CrimeGuard` (or paste your repo URL).
4. Render will automatically detect the settings from `render.yaml` or you can enter them:
   - **Name**: `crimeguard` (or your preferred name)
   - **Region**: Choose the closest region (e.g., *Singapore*, *Oregon*, or *Frankfurt*)
   - **Runtime**: **Docker** *(Recommended — builds both React frontend and Python ML backend seamlessly)*
   - **Instance Type**: **Free**
   - **Health Check Path**: `/api/health`
5. Click **Deploy Web Service**.

> **Note on Free Tier**: Render's free tier spins down after 15 minutes of inactivity. When visiting the URL for the first time, allow ~45 seconds for the server to spin up ("cold start").

### Alternative: Native Python Service on Render (Without Docker)
If you prefer Render's native Python runtime instead of Docker:
- **Runtime**: Python 3
- **Build Command**: `./build.sh`
- **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## Method 2: Universal Docker Deployment

If you want to run or test the production container locally or on any cloud VPS (DigitalOcean, AWS, GCP, Fly.io):

```bash
# Build and run with Docker Compose
docker compose up --build

# Open in browser:
http://localhost:8000
```

---

## Method 3: Run Locally (Without Docker)

You can run the full unified application locally anytime with a single command:

**On macOS / Linux:**
```bash
./run_local.sh
```

**On Windows:**
```cmd
run_backend.bat
```

Then visit [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Demo Accounts & Logins

| Unit | Username | Password | Accessible Features |
|---|---|---|---|
| **Police** | `police` | `Police@123` | Overview, Prediction (CatBoost), Crime Map, Trends |
| **Crime Branch** | `crimebranch` | `Crime@123` | Everything above + Explainability (SHAP), Pattern Mining, OLAP Explorer, Model Comparison |

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `PORT` | Port for the HTTP server (automatically supplied by Render/Railway) | `8000` |
| `CRIMEGUARD_SECRET` | Secret key used for signing session tokens | Auto-generated in `.auth_secret` |
