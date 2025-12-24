#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Load environment variables from .env
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

echo "Starting BookerAI in development mode..."
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1

flask run --host=0.0.0.0 --port=8080
