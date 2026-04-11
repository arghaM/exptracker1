#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${BLUE}${BOLD}================================================${NC}"
echo -e "${BLUE}${BOLD}       ExpTracker - Setup Wizard${NC}"
echo -e "${BLUE}${BOLD}================================================${NC}"
echo ""

# ---------- Step 1: Check Python ----------
echo -e "${BOLD}[1/5] Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}Found: $PY_VERSION${NC}"
else
    echo -e "  ${RED}Python3 not found!${NC}"
    echo "  Install Python 3.12+ from https://python.org"
    exit 1
fi

# ---------- Step 2: Check/Install Ollama ----------
echo ""
echo -e "${BOLD}[2/5] Checking Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "  ${GREEN}Found: $(ollama --version 2>&1 || echo 'installed')${NC}"
else
    echo -e "  ${YELLOW}Ollama not found.${NC}"
    echo ""
    read -p "  Install Ollama now? (y/n): " INSTALL_OLLAMA
    if [[ "$INSTALL_OLLAMA" == "y" || "$INSTALL_OLLAMA" == "Y" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "  Opening Ollama download page..."
            open "https://ollama.com/download/mac"
            echo -e "  ${YELLOW}Install Ollama, then re-run this setup.${NC}"
            exit 0
        else
            echo "  Installing via curl..."
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    else
        echo -e "  ${RED}Ollama is required. Install from https://ollama.com${NC}"
        exit 1
    fi
fi

# ---------- Step 3: Configure .env ----------
echo ""
echo -e "${BOLD}[3/5] Configuring environment...${NC}"
if [ -f .env ]; then
    echo -e "  ${GREEN}.env already exists${NC}"
    read -p "  Reconfigure? (y/n): " RECONFIG
    if [[ "$RECONFIG" != "y" && "$RECONFIG" != "Y" ]]; then
        echo "  Keeping existing config."
        SKIP_ENV=true
    fi
fi

if [ "$SKIP_ENV" != "true" ]; then
    echo ""
    echo -e "  ${BLUE}Telegram Setup (optional - press Enter to skip)${NC}"
    echo "  Get a bot token from @BotFather on Telegram"
    read -p "  Bot Token: " BOT_TOKEN
    BOT_TOKEN=${BOT_TOKEN:-your_bot_token_here}

    read -p "  Chat ID: " CHAT_ID
    CHAT_ID=${CHAT_ID:-your_chat_id_here}

    echo ""
    echo -e "  ${BLUE}LLM Model${NC}"
    echo "  Options: llama3.2 (3B, fast), llama3.2:1b (tiny, fastest), qwen2.5:14b (large, best)"
    read -p "  Model [llama3.2]: " MODEL
    MODEL=${MODEL:-llama3.2}

    read -p "  Server Port [8000]: " PORT
    PORT=${PORT:-8000}

    cat > .env << EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
TELEGRAM_CHAT_ID=$CHAT_ID
OLLAMA_MODEL=$MODEL
OLLAMA_URL=http://localhost:11434
DB_PATH=expenses.db
PORT=$PORT
POLL_INTERVAL=30
EOF
    echo -e "  ${GREEN}.env created${NC}"
fi

# ---------- Step 4: Setup Python venv & deps ----------
echo ""
echo -e "${BOLD}[4/5] Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "  Installing dependencies..."
pip install -q -r requirements.txt
echo -e "  ${GREEN}Dependencies installed${NC}"

# ---------- Step 5: Pull Ollama model ----------
echo ""
echo -e "${BOLD}[5/5] Pulling LLM model...${NC}"

# Load the model name from .env
if [ -f .env ]; then
    MODEL=$(grep OLLAMA_MODEL .env | cut -d= -f2)
fi
MODEL=${MODEL:-llama3.2}

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  Starting Ollama..."
    ollama serve &
    sleep 3
fi

if ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo -e "  ${GREEN}Model '$MODEL' already available${NC}"
else
    echo "  Pulling $MODEL (this may take a few minutes)..."
    ollama pull "$MODEL"
    echo -e "  ${GREEN}Model ready${NC}"
fi

# ---------- Done ----------
echo ""
echo -e "${GREEN}${BOLD}================================================${NC}"
echo -e "${GREEN}${BOLD}       Setup Complete!${NC}"
echo -e "${GREEN}${BOLD}================================================${NC}"
echo ""
echo -e "  To start the app:  ${BOLD}./run.sh${NC}"
echo -e "  Then open:         ${BOLD}http://localhost:${PORT:-8000}${NC}"
echo ""
echo -e "  To import existing data:"
echo -e "  Go to Categories > Data Management > Import Backup"
echo ""
