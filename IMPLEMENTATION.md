# ExpTracker — Implementation Guide

A personal/family expense tracker that auto-imports transactions from a Telegram channel, parses them with a local LLM (Ollama), and provides a web dashboard for review and budgeting.

## Project Structure

```
app.py             → FastAPI routes and Telegram sync logic
db.py              → SQLite database layer (all tables, queries)
llm.py             → Ollama integration for parsing expense messages
telegram.py        → Telegram Bot API client (fetch messages)
main.py            → Entry point (loads .env, inits DB, starts uvicorn)
run.sh             → One-command startup script

dashboard.html     → Main dashboard with spending overview and charts
transactions.html  → Transaction list with approve/edit/delete
admin.html         → Category management (groups, budgets, exclusions)
accounts.html      → Account management
bills.html         → Recurring bills tracker

expenses.db        → SQLite database (auto-created)
requirements.txt   → Python dependencies
```

## Setup

1. **Prerequisites**: Python 3.10+, [Ollama](https://ollama.ai) installed locally.

2. **Environment variables** — create a `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   OLLAMA_MODEL=llama3.2          # optional, default llama3.2
   OLLAMA_URL=http://localhost:11434  # optional
   PORT=8000                       # optional
   ```

3. **Run**:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
   This will: start Ollama if needed, pull the model, create a venv, install deps, and start the server on port 8000.

   Or manually:
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

## Database Schema

All tables are created automatically by `db.init_db()` on startup.

| Table | Purpose |
|---|---|
| `expenses` | All transactions (date, item, amount, category, status, etc.) |
| `categories` | Category definitions (name, icon, color, budget, excluded, group_name) |
| `category_overrides` | Item → category mapping overrides for LLM corrections |
| `processed_messages` | Telegram message IDs already processed (dedup) |
| `app_settings` | Key-value store for persistent app state |
| `bills` | Recurring bill definitions |
| `bill_resolutions` | Bill payment tracking |

## Telegram Sync — How It Works

The app pulls messages from a Telegram channel via the Bot API and parses them into expenses using Ollama.

### Deduplication (3 layers)

1. **API-level**: Uses `last_update_id` offset so Telegram only returns new messages. This ID is **persisted in the `app_settings` table** (key: `last_update_id`) so it survives app restarts — the app won't re-fetch old messages after a restart.

2. **Application-level**: Before processing, each message is checked against the `processed_messages` table. Already-seen `message_id`s are skipped.

3. **Database-level**: The `expenses` table has a `UNIQUE` constraint on `telegram_message_id`. Even if layers 1 and 2 fail, the DB rejects duplicates.

### Flow

```
Sync button clicked
  → GET Telegram updates (offset = last_update_id + 1)
  → Save new last_update_id to DB immediately
  → For each message:
      → Skip if message_id in processed_messages
      → Send text to Ollama for parsing
      → Insert parsed expenses into DB (status = "pending")
      → Mark message_id as processed
  → User reviews pending transactions in the Transactions page
```

### Edge case: multi-expense messages

A single Telegram message can produce multiple expenses. Only the first expense gets `telegram_message_id` set (others get NULL). The `processed_messages` table is the primary dedup guard for these.

## Category Groups

Categories can be organized into groups for visual grouping on the admin page.

### Backend

- `categories.group_name` column — nullable, stores group membership
- `PUT /categories/{name}/group` — assign a category to a group (or `null` to ungroup)
- `PUT /groups/rename` — rename a group
- `DELETE /groups/{group_name}` — ungroup all categories in a group

### Frontend (admin.html)

- Regular categories are rendered grouped by `group_name` with collapsible headers
- Group headers show aggregated spent/budget totals and a progress bar
- The `···` menu on each category has a "Change group" option opening a modal
- Groups auto-disappear when their last category is removed

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/categories/spending` | Categories with spent/budget for a date range |
| GET | `/categories/{name}/detail` | Full category detail (metrics, budget, etc.) |
| GET | `/categories/{name}/history` | Monthly spending history |
| GET | `/categories/{name}/transactions-grouped` | Transactions grouped by month |
| PUT | `/categories/{name}/budget` | Set budget amount |
| PUT | `/categories/{name}/details` | Update category properties |
| PUT | `/categories/{name}/group` | Set group membership |
| POST | `/categories` | Create a new category |
| DELETE | `/categories/{name}` | Delete a category |
| POST | `/sync/telegram` | Trigger Telegram sync |
| GET | `/expenses` | List expenses with filters |
| PUT | `/expenses/{id}` | Update an expense |
| DELETE | `/expenses/{id}` | Delete an expense |
