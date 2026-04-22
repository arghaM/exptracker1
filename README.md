# ExpTracker

A self-hosted personal expense tracker with Telegram/Google Sheets integration and AI-powered expense parsing.

Send a message like `chicken 250` or forward a bank SMS to your Telegram bot — ExpTracker uses an AI model to parse it into structured expenses automatically.

## Features

- **Telegram Sync** — Forward bank SMS or type expenses in natural language
- **Google Sheets Sync** — Sync expenses from Google Sheets (avoids Telegram 24h message expiry)
- **LLM Parsing** — Groq-hosted Llama 3.3 70B extracts item, amount, category, account from any message format
- **Dashboard** — Monthly spending overview with need/want stacked bars, category breakdown, daily comparison charts
- **Transactions** — Browse, search, edit, split, refund, tag expenses; make any transaction a recurring bill
- **Categories** — Grouped categories with icons, colors, budgets, need/want classification, and exclusion controls
- **Query Mode** — Drag-and-drop categories/groups to calculate custom spending totals
- **Bills & Recurring** — Track recurring bills with alerts, calendar view, and resolution tracking
- **Accounts** — Fuzzy-matched account grouping with custom labels, icons, colors
- **Reports** — Weekly, monthly, yearly summaries; person-wise splits; group-level breakdowns; need vs want analysis
- **Backup & Restore** — Full JSON export/import of all data
- **Pending Review** — Telegram-sourced expenses land as "pending" for manual approval
- **Tags** — Color-coded tags on any expense for custom tracking

## Prerequisites

- **Python 3.12+**
- **Groq API key** (free) — [console.groq.com](https://console.groq.com)
- **Telegram Bot** (optional) — for auto-syncing expenses from chat
- **Google Cloud credentials** (optional) — for Google Sheets sync

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
- Check Python is installed
- Walk you through `.env` configuration (Groq API key, Telegram tokens, port)
- Create a Python virtual environment and install dependencies

### 2. Configure Groq API (required for LLM parsing)

1. Sign up at [console.groq.com](https://console.groq.com) (free, no credit card)
2. Go to **API Keys** → **Create API Key**
3. Copy the key (starts with `gsk_...`)
4. Add to `.env`:

```env
GROQ_API_KEY=gsk_your_key_here
```

The free tier gives you 14,400 requests/day — more than enough for personal expense tracking.

### 3. Configure Telegram (optional)

If you want to sync expenses from Telegram:

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID (send a message to your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Enter both values during `./setup.sh` or edit `.env` manually:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Configure Google Sheets Sync (optional)

If you want to sync expenses from Google Sheets (recommended — avoids Telegram's 24h message expiry):

1. Create a Google Cloud project and enable the **Google Sheets API**
2. Create a **Service Account** and download `credentials.json`
3. Place `credentials.json` in the project root
4. Create a Google Sheet and share it with the service account email
5. Add to `.env`:

```env
GOOGLE_SHEET_ID=your_sheet_id_here
```

When both Telegram and Google Sheets are configured, the sync endpoint prefers Google Sheets.

### 5. Choose an LLM model (optional)

The default model is `llama-3.3-70b-versatile` on Groq, which works great for all message types. You can override it:

```env
GROQ_MODEL=llama-3.3-70b-versatile
```

| Model | Speed | Accuracy | Notes |
|-------|-------|----------|-------|
| `llama-3.3-70b-versatile` | ~1s | Excellent | Default, best for bank SMS |
| `llama-3.1-8b-instant` | ~0.5s | Good | Faster, good for simple messages |
| `gemma2-9b-it` | ~0.5s | Good | Alternative option |

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

**Via UI** — Use the dashboard's manual entry or the transactions page to add and edit expenses.

### Pages

| Page | What it does |
|------|-------------|
| **Dashboard** (`/`) | Monthly overview, need/want stacked bars, category pie chart, daily spending comparison, bill alerts |
| **Transactions** (`/transactions`) | Full expense list, search, edit, split, refund, tag, make recurring |
| **Accounts** (`/accounts-page`) | Spending by payment account with fuzzy grouping |
| **Bills** (`/bills-page`) | Recurring bills calendar, alerts, resolution tracking |
| **Reports** (`/reports-page`) | Weekly/monthly/yearly reports, trends, person-wise splits, need vs want breakdown |
| **Categories** (`/admin`) | Category management, need/want toggle, budgets, query mode, backup/restore |

### Transaction Features

- **Split** — Split a transaction into multiple categories (e.g. a grocery bill with household + food items)
- **Refund** — Mark a transaction as refunded (creates a linked reversal)
- **Edit** — Click any transaction in admin to edit inline

### Query Mode

On the Categories page, click **Query Mode** to enter a drag-and-drop calculation mode:
1. Drag any category or group into the query box
2. See the combined spending total instantly
3. Groups auto-exclude their child categories to prevent double-counting

### Need vs Want

Each category can be classified as **Need** or **Want** (default: Want):
1. Go to **Categories** (`/admin`) → click a category
2. Toggle **Need/Want** in the detail panel
3. Dashboard shows need/want breakdown in the monthly spending chart
4. Reports page has a **Need vs Want** group-by option with category drill-down

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
  db.py               # SQLite database layer (all tables, migrations)
  llm.py              # Groq LLM integration for expense parsing
  telegram.py         # Telegram Bot API client
  gsheet.py           # Google Sheets sync client
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
  .gitignore          # Excludes venv, .env, database, credentials
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq API key for LLM parsing (free at console.groq.com) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | — | Telegram chat ID to read messages from |
| `GOOGLE_SHEET_ID` | — | Google Sheet ID for sync |
| `DB_PATH` | `expenses.db` | SQLite database file path |
| `PORT` | `8000` | Server port |

## Tech Stack

- **Backend** — Python, FastAPI, SQLite
- **Frontend** — Vanilla HTML/CSS/JS, Chart.js
- **LLM** — Groq API (Llama 3.3 70B, free tier)
- **Integrations** — Telegram Bot API, Google Sheets API

## License

MIT
