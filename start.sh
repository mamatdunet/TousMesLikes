#!/bin/bash
# TousMesLikes — start both backend and frontend

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting TousMesLikes..."

# Backend
cd "$DIR/backend"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACK_PID=$!

# Frontend
cd "$DIR/frontend"
npm run dev -- --port 5173 &
FRONT_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACK_PID $FRONT_PID 2>/dev/null; exit" INT TERM
wait
