#!/usr/bin/env bash
# AttentionX – Quick Start Script
set -e

echo ""
echo "⚡  AttentionX – AI Content Repurposing Engine"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3 not found. Please install Python 3.9+"
  exit 1
fi

PYTHON=$(command -v python3)
echo "✅  Python: $($PYTHON --version)"

# Check .env
if [ ! -f backend/.env ]; then
  echo ""
  echo "⚠️   No .env file found in backend/."
  echo "    Copy backend/.env.example → backend/.env and fill in your GEMINI_API_KEY"
  echo ""
  read -p "Press Enter to continue anyway (pipeline will fall back to peak-based clip selection)..."
fi

# Install deps
echo ""
echo "📦  Installing Python dependencies (this takes a minute on first run)…"
$PYTHON -m pip install -r backend/requirements.txt -q
echo "✅  Dependencies installed."

# Start server
echo ""
echo "🚀  Starting AttentionX server at http://localhost:8000"
echo "    Open your browser and go to: http://localhost:8000"
echo ""
cd backend
$PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
