#!/bin/bash
# Restart script for Poetry-based deployment with Docker databases

echo "Stopping services..."
pkill -f "streamlit|uvicorn" || true
sleep 3

echo "Starting FastAPI..."
pwd

# Source environment variables from .env first
source .env 2>/dev/null || echo "No .env file found"

# Make sure Poetry environment is installed
echo "Ensuring Poetry environment is ready..."
poetry install --only=main

# Start FastAPI from the fastapi directory with proper working directory
cd src/fastapi
# Copy .env file to fastapi directory so Poetry can find it
cp ../../.env .env 2>/dev/null || echo "No .env file to copy"
nohup poetry run uvicorn main:app --host 0.0.0.0 --port 9020 > /tmp/fastapi.log 2>&1 &
cd /Users/martinlopez/litigation_genai

echo "Starting Streamlit..."
nohup poetry run streamlit run src/streamlit/Home.py --server.port=8501 --server.address=0.0.0.0 > /tmp/streamlit.log 2>&1 &

echo "Services started"
echo "Check with: ps aux | grep -E '(streamlit|uvicorn)'"
echo "Logs: tail -f /tmp/fastapi.log or tail -f /tmp/streamlit.log"