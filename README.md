# ExpTracker

A self-hosted personal expense tracker with Telegram integration and local LLM-powered expense parsing.

Send a message like `chicken 250` or forward a bank SMS to your Telegram bot — ExpTracker uses a local AI model to parse it into structured expenses automatically.

## Features

- **Telegram Sync** — Forward bank SMS or type expenses in natural language
- **LLM Parsing** — Local Ollama model extracts item, amount, category, account from any message format
- **Dashboard** — Monthly spending overview with category breakdown, daily comparison charts
- **Transactions** — Browse, search, edit, tag expenses; make any transaction a recurring bill
- **Categories** — Grouped categories with icons, colors, budgets, and exclusion controls
- **Query Mode** — Drag-and-drop categories/groups to calculate custom spending totals
- **Bills & Recurring** — Track recurring bills with alerts, calendar view, and resolution tracking
- **Accounts** — Fuzzy-matched account grouping with custom labels, icons, colors
- **Reports** — Weekly, monthly, yearly summaries; person-wise splits; group-level breakdowns
- **Backup & Restore** — Full JSON export/import of all data
- **Pending Review** — Telegram-sourced expenses land as "pending" for manual approval
- **Tags** — Color-coded tags on any expense for custom tracking

## Prerequisites

- **Python 3.12+**
- **Ollama** — [ollama.com](https://ollama.com)
- **Telegram Bot** (optional) — for auto-syncing expenses from chat

## Quick Start

```bash
git clone https://github.com/arghaM/exptracker1.git
cd exptracker1
./setup.sh    # Interactive wizard — configures everything
./run.sh      # Start the app
```

Open **http://localhost:8000** in your browser.

## Setup Details

### 1. Run the setup wizard

```bash
./setup.sh
```

This will:
- Check Python and Ollama are installed
- Walk you through `.env` configuration (Telegram tokens, LLM model, port)
- Create a Python virtual environment and install dependencies
- Pull the selected Ollama model

### 2. Configure Telegram (optional)

If you want to sync expenses from Telegram:

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID (send a message to your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Enter both values during `./setup.sh` or edit `.env` manually:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Choose an LLM model

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `llama3.2:1b` | 1.3 GB | Fastest | Good for simple messages |
| `llama3.2` | 2 GB | Fast | Good balance (default) |
| `qwen2.5:14b` | 9 GB | Slower | Best for bank SMS parsing |

Set in `.env`:
```env
OLLAMA_MODEL=llama3.2
```

## Usage

### Adding Expenses

**Via Telegram** — Send messages to your bot:
```
chicken 250
Ratnadeep 1057
Arjun bought shoes 2500
```

Or forward bank/UPI SMS directly — the LLM extracts merchant, amount, account, and category automatically.

Then click **Sync** on the dashboard to pull new messages. Expenses arrive as "pending" for review.

**Via UI** — Use the transactions page to view and edit all expenses.

### Pages

| Page | What it does |
|------|-------------|
| **Dashboard** (`/`) | Monthly overview, category pie chart, daily spending comparison, bill alerts |
| **Transactions** (`/transactions`) | Full expense list, search, edit, tag, make recurring |
| **Accounts** (`/accounts-page`) | Spending by payment account with fuzzy grouping |
| **Bills** (`/bills-page`) | Recurring bills calendar, alerts, resolution tracking |
| **Reports** (`/reports-page`) | Weekly/monthly/yearly reports, trends, person-wise splits |
| **Categories** (`/admin`) | Category management, budgets, query mode, backup/restore |

### Query Mode

On the Categories page, click **Query Mode** to enter a drag-and-drop calculation mode:
1. Drag any category or group into the query box
2. See the combined spending total instantly
3. Groups auto-exclude their child categories to prevent double-counting

### Backup & Restore

On the Categories page, scroll to **Data Management**:
- **Export Backup** — Downloads a JSON file with all your data (all 11 tables)
- **Import Backup** — Upload a backup file to restore all data (replaces everything)

Use this to migrate data between machines or as a periodic backup.

## Updating

When running from a git clone:

```bash
./update.sh   # Pulls latest code, backs up DB, installs new deps
./run.sh      # Restart
```

`run.sh` also checks for updates automatically on startup and notifies you.

## Project Structure

```
exptracker1/
  main.py             # Entry point — starts uvicorn server
  app.py              # FastAPI routes (API + page serving)
  db.py               # SQLite database layer (all 11 tables, migrations)
  llm.py              # Ollama LLM integration for expense parsing
  telegram.py         # Telegram Bot API client
  dashboard.html      # Dashboard page
  transactions.html   # Transactions page
  accounts.html       # Accounts page
  bills.html          # Bills page
  reports.html        # Reports page
  admin.html          # Categories page (+ query mode, backup/restore)
  requirements.txt    # Python dependencies
  run.sh              # Start the app
  setup.sh            # First-time setup wizard
  update.sh           # Pull updates safely
  .env.example        # Environment variable template
  .gitignore          # Excludes venv, .env, database
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | — | Telegram chat ID to read messages from |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `DB_PATH` | `expenses.db` | SQLite database file path |
| `PORT` | `8000` | Server port |
| `POLL_INTERVAL` | `30` | Telegram polling interval in seconds |

## Tech Stack

- **Backend** — Python, FastAPI, SQLite
- **Frontend** — Vanilla HTML/CSS/JS, Chart.js
- **LLM** — Ollama (local, private, no API costs)
- **Telegram** — Bot API for message ingestion

## License

MIT
