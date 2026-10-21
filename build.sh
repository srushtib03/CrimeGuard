#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "============================================="
echo " Building CrimeGuard Frontend (React + Vite)"
echo "============================================="
cd frontend
npm install
npm run build
cd ..

echo "============================================="
echo " Installing Backend Dependencies (Python)"
echo "============================================="
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo "============================================="
echo " CrimeGuard Build Completed Successfully!"
echo "============================================="
