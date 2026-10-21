#!/usr/bin/env bash
# Script to run CrimeGuard locally with built frontend and FastAPI backend
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Checking Python virtual environment..."
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "Building frontend if dist is not present..."
if [ ! -d "frontend/dist" ]; then
    cd frontend
    npm install
    npm run build
    cd ..
fi

echo "Starting CrimeGuard at http://127.0.0.1:8000 ..."
"$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
