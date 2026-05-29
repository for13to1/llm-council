#!/bin/bash

# LLM Council - Start script

echo "Starting LLM Council..."
echo ""

echo "Starting backend on http://localhost:8001..."
uv run python -m backend.main &
BACKEND_PID=$!

echo ""
echo "LLM Council is running at http://localhost:8001"
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
