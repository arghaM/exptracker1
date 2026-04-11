#!/bin/bash
set -e

echo "=== Expense Tracker ==="

# Load .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check for updates (non-blocking, git only)
if [ -d ".git" ]; then
    git fetch origin --quiet 2>/dev/null &
    FETCH_PID=$!
    # Wait briefly for fetch
    sleep 1
    if kill -0 $FETCH_PID 2>/dev/null; then
        # Fetch still running, skip check
        true
    else
        LOCAL=$(git rev-parse HEAD 2>/dev/null)
        REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null || echo "")
        if [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
            echo ""
            echo "** Update available! Run: ./update.sh **"
            echo ""
        fi
    fi
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 3
fi

# Pull model if not present
MODEL="${OLLAMA_MODEL:-llama3.2}"
if ! ollama list | grep -q "$MODEL"; then
    echo "Pulling model $MODEL..."
    ollama pull "$MODEL"
fi

# Set up virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

# Run the app
echo "Starting server..."
python main.py
