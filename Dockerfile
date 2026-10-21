# Multi-stage Dockerfile for CrimeGuard (React + FastAPI + CatBoost)
# Stage 1: Build React frontend with Vite
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python 3.11 runtime for FastAPI, CatBoost & SQLite OLAP
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for OpenMP (CatBoost runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code, models, and data
COPY backend/ ./backend/

# Copy built frontend assets to frontend/dist for FastAPI SPA serving
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Health check using FastAPI /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health')" || exit 1

# Start uvicorn server dynamically on $PORT provided by Render/Railway/Cloud
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
