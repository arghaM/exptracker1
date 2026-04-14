from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timedelta, date

DB_PATH = os.getenv("DB_PATH", "expenses.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            item TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            person TEXT,
            telegram_message_id INTEGER UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS processed_messages (
            message_id INTEGER PRIMARY KEY,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS category_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_pattern TEXT NOT NULL UNIQUE,
            corrected_category TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT DEFAULT '',
            frequency TEXT NOT NULL,
            anchor_date TEXT NOT NULL,
            alert_days INTEGER DEFAULT 15,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bill_resolutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            expense_id INTEGER,
            resolved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#3b82f6'
        );

        CREATE TABLE IF NOT EXISTS expense_tags (
            expense_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (expense_id, tag_id),
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
    """)
    conn.commit()

    # Migration: add notes column if missing
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN notes TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Migration: add account column if missing
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN account TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Migration: add group_name column to categories if missing
    try:
        conn.execute("ALTER TABLE categories ADD COLUMN group_name TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Seed default categories with groups
    default_categories = {
        'Groceries & Food': 'Food & Dining',
        'Order Out': 'Food & Dining',
        'Restaurants': 'Food & Dining',
        'Quick Delivery': 'Food & Dining',
        'Chicken & Fish': 'Food & Dining',
        'Rent': 'Housing',
        'Subscription': 'Bills & Utilities',
        'Utilities': 'Bills & Utilities',
        'Clothing': 'Shopping',
        'Shopping': 'Shopping',
        'Gifting': 'Shopping',
        'Travel': 'Auto & Transport',
        'Petrol': 'Auto & Transport',
        'Transport': 'Auto & Transport',
        'Investment': 'Financial',
        'Entertainment': 'Entertainment',
        'Medicine': 'Health',
        'Lab Test': 'Health',
        'Doctor': 'Health',
        'Other': None,
    }
    for cat, group in default_categories.items():
        conn.execute("INSERT OR IGNORE INTO categories (name, group_name) VALUES (?, ?)", (cat, group))
    conn.commit()

    # Backfill group_name for existing categories that have NULL group_name
    for cat, group in default_categories.items():
        if group is not None:
            conn.execute(
                "UPDATE categories SET group_name = ? WHERE name = ? AND group_name IS NULL",
                (group, cat),
            )
    conn.commit()

    # Migration: add status column to expenses if missing
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN status TEXT DEFAULT 'approved'")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Migration: add end_date column to bills if missing
    try:
        conn.execute("ALTER TABLE bills ADD COLUMN end_date TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Migration: add icon, color, excluded to categories
    for col, default in [("icon", "NULL"), ("color", "NULL"), ("excluded", "0")]:
        try:
            conn.execute(f"ALTER TABLE categories ADD COLUMN {col} TEXT DEFAULT {default}" if col != "excluded"
                         else f"ALTER TABLE categories ADD COLUMN {col} INTEGER DEFAULT {default}")
            conn.commit()
        except Exception:
            pass

    # Create category_budgets table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_budgets (
            category TEXT NOT NULL PRIMARY KEY,
            amount REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_labels (
            account_key TEXT NOT NULL PRIMARY KEY,
            label TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Migration: add icon and color columns to account_labels
    for col in ["icon", "color"]:
        try:
            conn.execute(f"ALTER TABLE account_labels ADD COLUMN {col} TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

    # Seed default icons/colors for existing categories
    _default_cat_meta = {
        'Groceries & Food': ('🛒', '#22c55e'),
        'Order Out': ('🛵', '#f97316'),
        'Restaurants': ('🍽️', '#ef4444'),
        'Quick Delivery': ('📦', '#8b5cf6'),
        'Chicken & Fish': ('🍗', '#f59e0b'),
        'Rent': ('🏠', '#3b82f6'),
        'Subscription': ('📺', '#a855f7'),
        'Utilities': ('⚡', '#f59e0b'),
        'Clothing': ('👔', '#ec4899'),
        'Shopping': ('🛍️', '#06b6d4'),
        'Gifting': ('🎁', '#ef4444'),
        'Travel': ('✈️', '#0ea5e9'),
        'Petrol': ('⛽', '#f97316'),
        'Transport': ('🚗', '#14b8a6'),
        'Investment': ('💰', '#84cc16'),
        'Entertainment': ('🎬', '#a855f7'),
        'Medicine': ('💊', '#ef4444'),
        'Lab Test': ('🔬', '#06b6d4'),
        'Doctor': ('🩺', '#3b82f6'),
        'Other': ('📋', '#94a3b8'),
        'Insurance premium payment': ('🛡️', '#8b5cf6'),
        'Maid Salary': ('🧹', '#14b8a6'),
        'Internet': ('📡', '#3b82f6'),
        'Flight': ('✈️', '#0ea5e9'),
        'Hotels': ('🏨', '#f97316'),
        'Car Insurance': ('🚗', '#8b5cf6'),
        'Car Service': ('🔧', '#64748b'),
        'FasTag': ('🛣️', '#22c55e'),
        'Car EMI': ('🚗', '#ef4444'),
        'Drinking Water': ('💧', '#06b6d4'),
    }
    for cat, (icon, color) in _default_cat_meta.items():
        conn.execute(
            "UPDATE categories SET icon = ?, color = ? WHERE name = ? AND icon IS NULL",
            (icon, color, cat),
        )
    conn.commit()

    # Migration: add refund_of column to expenses if missing
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN refund_of INTEGER DEFAULT NULL")
        conn.commit()
    except Exception:
        pass

    conn.close()


def insert_expense(date: str, raw_text: str, item: str, amount: float,
                   category: str, person: str | None, telegram_message_id: int | None,
                   notes: str = "", account: str = "", status: str = "approved") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO expenses (date, raw_text, item, amount, category, person, telegram_message_id, notes, account, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date, raw_text, item, amount, category, person, telegram_message_id, notes, account, status),
    )
    expense_id = cur.lastrowid
    conn.commit()
    conn.close()
    return expense_id


def get_pending_expenses() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE status = 'pending' ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_expense(id: int):
    conn = get_connection()
    conn.execute("UPDATE expenses SET status = 'approved' WHERE id = ?", (id,))
    conn.commit()
    conn.close()


def discard_expense(id: int):
    conn = get_connection()
    conn.execute("UPDATE expenses SET status = 'discarded' WHERE id = ?", (id,))
    conn.commit()
    conn.close()


def bulk_approve_expenses(ids: list[int]):
    if not ids:
        return
    conn = get_connection()
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE expenses SET status = 'approved' WHERE id IN ({placeholders})",
        ids,
    )
    conn.commit()
    conn.close()


def is_message_processed(msg_id: int) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM processed_messages WHERE message_id = ?", (msg_id,)).fetchone()
    conn.close()
    return row is not None


def mark_message_processed(msg_id: int):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO processed_messages (message_id) VALUES (?)", (msg_id,))
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_expenses_by_date_range(start: str, end: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE date >= ? AND date <= ? AND status = 'approved' ORDER BY date DESC",
        (start, end),
    ).fetchall()
    conn.close()
    expenses = [dict(r) for r in rows]
    if expenses:
        tag_map = get_tags_for_expenses([e["id"] for e in expenses])
        for e in expenses:
            e["tags"] = tag_map.get(e["id"], [])
    return expenses


def get_summary(start: str, end: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT category, SUM(amount) as total, COUNT(*) as count
           FROM expenses WHERE date >= ? AND date <= ? AND status = 'approved'
           GROUP BY category ORDER BY total DESC""",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_expenses_by_category(category: str, start: str | None = None, end: str | None = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM expenses WHERE category = ? AND status = 'approved'"
    params: list = [category]
    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)
    query += " ORDER BY date DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_person_summary(start: str | None = None, end: str | None = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT person, SUM(amount) as total, COUNT(*) as count FROM expenses"
    params: list = []
    conditions = ["status = 'approved'"]
    if start:
        conditions.append("date >= ?")
        params.append(start)
    if end:
        conditions.append("date <= ?")
        params.append(end)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY person ORDER BY total DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_trends(months: int = 6) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y-%m', date) as month, SUM(amount) as total, COUNT(*) as count
           FROM expenses
           WHERE date >= date('now', ?) AND status = 'approved'
           GROUP BY month ORDER BY month""",
        (f"-{months} months",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_expense(id: int, date: str, item: str, amount: float, category: str, notes: str = "", account: str = ""):
    conn = get_connection()
    conn.execute(
        """UPDATE expenses SET date = ?, item = ?, amount = ?, category = ?, notes = ?, account = ?
           WHERE id = ?""",
        (date, item, amount, category, notes, account, id),
    )
    conn.commit()
    conn.close()


def upsert_category_override(item_pattern: str, category: str):
    normalized = item_pattern.strip().lower()
    conn = get_connection()
    conn.execute(
        """INSERT INTO category_overrides (item_pattern, corrected_category, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(item_pattern)
           DO UPDATE SET corrected_category = ?, updated_at = CURRENT_TIMESTAMP""",
        (normalized, category, category),
    )
    conn.commit()
    conn.close()


def get_category_override(item: str) -> str | None:
    normalized = item.strip().lower()
    conn = get_connection()
    row = conn.execute(
        "SELECT corrected_category FROM category_overrides WHERE item_pattern = ?",
        (normalized,),
    ).fetchone()
    conn.close()
    return row["corrected_category"] if row else None


def get_all_overrides() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM category_overrides ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_bar_data(months: int = 12) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
           FROM expenses
           WHERE date >= date('now', ?) AND status = 'approved'
           GROUP BY month ORDER BY month""",
        (f"-{months} months",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_categories() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_category_meta() -> dict:
    """Return {category_name: {icon, color}} map for rendering badges."""
    conn = get_connection()
    rows = conn.execute("SELECT name, icon, color FROM categories").fetchall()
    conn.close()
    return {r["name"]: {"icon": r["icon"] or "\U0001f4cb", "color": r["color"] or "#94a3b8"} for r in rows}


def add_category(name: str, group_name: str | None = None):
    conn = get_connection()
    conn.execute("INSERT INTO categories (name, group_name) VALUES (?, ?)", (name.strip(), group_name))
    conn.commit()
    conn.close()


def delete_category(name: str):
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()
    conn.close()


def get_categories_grouped() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT name, group_name FROM categories ORDER BY name").fetchall()
    conn.close()
    groups: dict[str, list[str]] = {}
    ungrouped: list[str] = []
    for r in rows:
        if r["group_name"]:
            groups.setdefault(r["group_name"], []).append(r["name"])
        else:
            ungrouped.append(r["name"])
    return {"groups": groups, "ungrouped": ungrouped}


def update_category_group(name: str, group_name: str | None):
    conn = get_connection()
    conn.execute("UPDATE categories SET group_name = ? WHERE name = ?", (group_name, name))
    conn.commit()
    conn.close()


def rename_group(old_name: str, new_name: str):
    conn = get_connection()
    conn.execute(
        "UPDATE categories SET group_name = ? WHERE group_name = ?",
        (new_name, old_name),
    )
    conn.commit()
    conn.close()


def delete_group(group_name: str):
    conn = get_connection()
    conn.execute(
        "UPDATE categories SET group_name = NULL WHERE group_name = ?",
        (group_name,),
    )
    conn.commit()
    conn.close()


def get_group_summary(start: str, end: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.group_name, SUM(e.amount) as total, COUNT(*) as count
           FROM expenses e
           LEFT JOIN categories c ON e.category = c.name
           WHERE e.date >= ? AND e.date <= ? AND e.status = 'approved'
           GROUP BY c.group_name
           ORDER BY total DESC""",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


import re as _re


def _normalize_account(name: str) -> str:
    """Normalize account name for fuzzy grouping.

    Strips *, #, collapses whitespace, normalizes a/c variants,
    lowercases, and removes common filler words so that
    'HDFC Bank Card *8803' and 'HDFC Bank Card 8803' match.
    """
    s = name.strip()
    # Remove * and # characters (often around card numbers)
    s = s.replace('*', '').replace('#', '')
    # Normalize a/c, A/C, Ac, ac → ac
    s = _re.sub(r'\ba[/\\]?c\b', 'ac', s, flags=_re.IGNORECASE)
    # Remove filler words (ending, no, no., number, xx, credit, debit)
    s = _re.sub(r'\b(ending|no\.?|number|xx+|credit|debit)\b', '', s, flags=_re.IGNORECASE)
    # Collapse multiple spaces
    s = _re.sub(r'\s+', ' ', s).strip()
    # Lowercase for comparison
    s = s.lower()
    return s


def _build_account_groups(rows: list[dict]) -> dict[str, list[str]]:
    """Map normalized key → list of raw account names.

    The display name chosen is the longest raw variant (most detail).
    """
    groups: dict[str, list[str]] = {}
    for r in rows:
        raw = r["account"] if r["account"] else ""
        if not raw:
            key = ""
        else:
            key = _normalize_account(raw)
        groups.setdefault(key, [])
        if raw not in groups[key]:
            groups[key].append(raw)
    return groups


def _pick_display_name(raw_names: list[str]) -> str:
    """Pick the best display name from a list of raw account variants."""
    if not raw_names or all(n == "" for n in raw_names):
        return "Manual"
    # Prefer the longest name (most complete)
    return max(raw_names, key=len)


def get_account_summary(start: str, end: str) -> list[dict]:
    """Return spending grouped by account (fuzzy-matched) for the given date range."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT account, amount FROM expenses WHERE date >= ? AND date <= ? AND status = 'approved'",
        (start, end),
    ).fetchall()
    label_rows = conn.execute("SELECT account_key, label, icon, color FROM account_labels").fetchall()
    conn.close()
    label_map = {r["account_key"]: {"label": r["label"], "icon": r["icon"], "color": r["color"]} for r in label_rows}

    groups = _build_account_groups([dict(r) for r in rows])

    # Aggregate per normalized group
    result = []
    for key, raw_names in groups.items():
        display = _pick_display_name(raw_names)
        total = 0.0
        count = 0
        for r in rows:
            raw = r["account"] if r["account"] else ""
            rkey = _normalize_account(raw) if raw else ""
            if rkey == key:
                total += r["amount"]
                count += 1
        label_info = label_map.get(key, {})
        result.append({
            "account_name": display,
            "total": round(total, 2),
            "count": count,
            "raw_names": raw_names,
            "label": label_info.get("label", "") if isinstance(label_info, dict) else label_info,
            "icon": label_info.get("icon") if isinstance(label_info, dict) else None,
            "color": label_info.get("color") if isinstance(label_info, dict) else None,
        })

    result.sort(key=lambda x: x["total"], reverse=True)
    return result


def set_account_label(account_name: str, label: str, icon: str | None = None, color: str | None = None):
    """Set a user-friendly label for an account (by normalized key)."""
    key = _normalize_account(account_name) if account_name != "Manual" else ""
    conn = get_connection()
    has_label = label.strip() if label else ""
    has_icon = icon.strip() if icon else ""
    has_color = color.strip() if color else ""
    if has_label or has_icon or has_color:
        conn.execute(
            """INSERT INTO account_labels (account_key, label, icon, color)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(account_key) DO UPDATE SET label = ?, icon = ?, color = ?""",
            (key, has_label, has_icon or None, has_color or None,
             has_label, has_icon or None, has_color or None),
        )
    else:
        conn.execute("DELETE FROM account_labels WHERE account_key = ?", (key,))
    conn.commit()
    conn.close()


def get_all_account_labels() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT account_key, label FROM account_labels ORDER BY label").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_transactions(account: str, start: str, end: str) -> list[dict]:
    """Return transactions for a specific account (fuzzy-matched) in the given date range."""
    conn = get_connection()
    if account == 'Manual':
        rows = conn.execute(
            """SELECT * FROM expenses
               WHERE (account IS NULL OR account = '') AND date >= ? AND date <= ? AND status = 'approved'
               ORDER BY date DESC""",
            (start, end),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # Get all transactions in range, then filter by normalized match
    all_rows = conn.execute(
        "SELECT * FROM expenses WHERE date >= ? AND date <= ? AND status = 'approved' ORDER BY date DESC",
        (start, end),
    ).fetchall()
    conn.close()

    target_key = _normalize_account(account)
    return [
        dict(r) for r in all_rows
        if r["account"] and _normalize_account(r["account"]) == target_key
    ]


def get_daily_totals(year: int, month: int) -> dict[int, float]:
    """Returns {day_of_month: total} for the given month."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"
    conn = get_connection()
    rows = conn.execute(
        """SELECT CAST(strftime('%d', date) AS INTEGER) as day, SUM(amount) as total
           FROM expenses
           WHERE date >= ? AND date < ? AND status = 'approved'
           GROUP BY day ORDER BY day""",
        (start, end),
    ).fetchall()
    conn.close()
    return {r["day"]: r["total"] for r in rows}


def get_weekly_breakdown_for_month(year: int, month: int) -> list[dict]:
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               ((strftime('%d', date) - 1) / 7 + 1) as week_num,
               MIN(date) as week_start,
               MAX(date) as week_end,
               SUM(amount) as total,
               COUNT(*) as count
           FROM expenses
           WHERE date >= ? AND date < ? AND status = 'approved'
           GROUP BY week_num ORDER BY week_num""",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Bills ---

def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping day to valid range."""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    import calendar
    max_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, max_day))


def _next_due_date(anchor: date, frequency: str, after: date) -> date:
    """Find next occurrence of bill on or after `after` date."""
    if frequency in ('weekly', 'biweekly'):
        interval = 14 if frequency == 'biweekly' else 7
        if anchor >= after:
            return anchor
        days_diff = (after - anchor).days
        periods_ahead = days_diff // interval
        candidate = anchor + timedelta(days=periods_ahead * interval)
        if candidate < after:
            candidate += timedelta(days=interval)
        return candidate

    freq_months = {
        'monthly': 1,
        'quarterly': 3,
        'half-yearly': 6,
        'yearly': 12,
        'once_in_2_years': 24,
        'once_in_3_years': 36,
        'once_in_4_years': 48,
        'once_in_5_years': 60,
    }
    months = freq_months.get(frequency, 12)

    if anchor >= after:
        return anchor

    # Estimate how many periods to jump
    month_diff = (after.year - anchor.year) * 12 + (after.month - anchor.month)
    periods = max(0, month_diff // months)
    candidate = _add_months(anchor, periods * months)
    while candidate < after:
        periods += 1
        candidate = _add_months(anchor, periods * months)
    return candidate


def create_bill(name: str, amount: float, category: str, frequency: str,
                anchor_date: str, alert_days: int = 15, notes: str = "",
                end_date: str | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO bills (name, amount, category, frequency, anchor_date, alert_days, notes, end_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, amount, category, frequency, anchor_date, alert_days, notes, end_date),
    )
    conn.commit()
    bill_id = cur.lastrowid
    conn.close()
    return bill_id


def get_all_bills() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM bills ORDER BY name").fetchall()
    conn.close()
    today = date.today()
    bills = []
    for r in rows:
        b = dict(r)
        anchor = date.fromisoformat(b["anchor_date"])
        ndd = _next_due_date(anchor, b["frequency"], today)
        b["next_due_date"] = ndd.isoformat()
        b["days_until_due"] = (ndd - today).days
        b["expired"] = False
        if b.get("end_date") and ndd > date.fromisoformat(b["end_date"]):
            b["expired"] = True
        bills.append(b)
    return bills


def update_bill(bill_id: int, name: str, amount: float, category: str,
                frequency: str, anchor_date: str, alert_days: int = 15, notes: str = "",
                end_date: str | None = None):
    conn = get_connection()
    conn.execute(
        """UPDATE bills SET name=?, amount=?, category=?, frequency=?, anchor_date=?, alert_days=?, notes=?, end_date=?
           WHERE id=?""",
        (name, amount, category, frequency, anchor_date, alert_days, notes, end_date, bill_id),
    )
    conn.commit()
    conn.close()


def delete_bill(bill_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM bill_resolutions WHERE bill_id = ?", (bill_id,))
    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()


def get_upcoming_alerts(today_str: str | None = None) -> list[dict]:
    today = date.fromisoformat(today_str) if today_str else date.today()
    conn = get_connection()
    bills = conn.execute("SELECT * FROM bills").fetchall()
    alerts = []
    for r in bills:
        b = dict(r)
        anchor = date.fromisoformat(b["anchor_date"])
        ndd = _next_due_date(anchor, b["frequency"], today - timedelta(days=b["alert_days"]))
        # Skip expired bills
        if b.get("end_date") and ndd > date.fromisoformat(b["end_date"]):
            continue
        # Check if this due date is within the alert window
        alert_start = ndd - timedelta(days=b["alert_days"])
        if today < alert_start:
            continue
        # Check if resolved
        res = conn.execute(
            "SELECT 1 FROM bill_resolutions WHERE bill_id = ? AND due_date = ?",
            (b["id"], ndd.isoformat()),
        ).fetchone()
        if res:
            continue
        b["next_due_date"] = ndd.isoformat()
        b["days_until_due"] = (ndd - today).days
        if today > ndd:
            b["status"] = "overdue"
        elif (ndd - today).days <= 7:
            b["status"] = "urgent"
        else:
            b["status"] = "upcoming"
        alerts.append(b)
    conn.close()
    alerts.sort(key=lambda x: x["next_due_date"])
    return alerts


def resolve_bill(bill_id: int, due_date: str, expense_id: int | None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO bill_resolutions (bill_id, due_date, expense_id) VALUES (?, ?, ?)",
        (bill_id, due_date, expense_id),
    )
    conn.commit()
    conn.close()


def get_bill_calendar(start_date: str, end_date: str) -> list[dict]:
    """Return all bill due dates within [start_date, end_date] range."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM bills").fetchall()
    conn.close()
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    events = []
    for r in rows:
        b = dict(r)
        anchor = date.fromisoformat(b["anchor_date"])
        bill_end = date.fromisoformat(b["end_date"]) if b.get("end_date") else None
        # Walk through all due dates in the range
        cursor = _next_due_date(anchor, b["frequency"], sd)
        while cursor <= ed:
            is_expired = bill_end is not None and cursor > bill_end
            is_end_date = bill_end is not None and b["end_date"] == cursor.isoformat()
            events.append({
                "date": cursor.isoformat(),
                "bill_id": b["id"],
                "name": b["name"],
                "amount": b["amount"],
                "category": b["category"],
                "frequency": b["frequency"],
                "expired": is_expired,
                "is_end_date": is_end_date,
                "end_date": b.get("end_date"),
            })
            # Advance to next occurrence
            if b["frequency"] in ('weekly', 'biweekly'):
                cursor += timedelta(days=14 if b["frequency"] == 'biweekly' else 7)
            else:
                freq_months = {'monthly': 1, 'quarterly': 3, 'half-yearly': 6, 'yearly': 12, 'once_in_2_years': 24, 'once_in_3_years': 36, 'once_in_4_years': 48, 'once_in_5_years': 60}
                months = freq_months.get(b["frequency"], 12)
                next_cursor = _next_due_date(anchor, b["frequency"], cursor + timedelta(days=1))
                if next_cursor <= cursor:
                    break  # safety
                cursor = next_cursor
    events.sort(key=lambda x: x["date"])
    return events


def get_bill_resolutions(bill_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT br.*, e.item as expense_item, e.amount as expense_amount, e.date as expense_date
           FROM bill_resolutions br
           LEFT JOIN expenses e ON br.expense_id = e.id
           WHERE br.bill_id = ?
           ORDER BY br.due_date DESC""",
        (bill_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Category Budgets & Details ---

def get_categories_with_spending(start: str, end: str) -> dict:
    """Return categories with spending and budget data for the categories page."""
    conn = get_connection()
    cats_rows = conn.execute(
        "SELECT name, group_name, icon, color, excluded FROM categories ORDER BY name"
    ).fetchall()
    spending_rows = conn.execute(
        """SELECT category, SUM(amount) as total, COUNT(*) as count
           FROM expenses WHERE date >= ? AND date <= ? AND status = 'approved'
           GROUP BY category""",
        (start, end),
    ).fetchall()
    spending_map = {r["category"]: {"total": r["total"], "count": r["count"]} for r in spending_rows}
    budget_rows = conn.execute("SELECT category, amount FROM category_budgets").fetchall()
    budget_map = {r["category"]: r["amount"] for r in budget_rows}
    conn.close()

    regular = []
    excluded_list = []
    for c in cats_rows:
        cat = dict(c)
        s = spending_map.get(cat["name"], {})
        cat["spent"] = round(s.get("total", 0), 2)
        cat["txn_count"] = s.get("count", 0)
        cat["budget"] = budget_map.get(cat["name"], 0)
        if cat.get("excluded"):
            excluded_list.append(cat)
        else:
            regular.append(cat)

    regular.sort(key=lambda x: x["spent"], reverse=True)
    excluded_list.sort(key=lambda x: x["spent"], reverse=True)
    total_spent = round(sum(c["spent"] for c in regular), 2)
    total_budget = round(sum(c["budget"] for c in regular), 2)
    return {
        "regular": regular,
        "excluded": excluded_list,
        "total_spent": total_spent,
        "total_budget": total_budget,
    }


def set_category_budget(category: str, amount: float):
    conn = get_connection()
    if amount <= 0:
        conn.execute("DELETE FROM category_budgets WHERE category = ?", (category,))
    else:
        conn.execute(
            """INSERT INTO category_budgets (category, amount)
               VALUES (?, ?)
               ON CONFLICT(category) DO UPDATE SET amount = ?""",
            (category, amount, amount),
        )
    conn.commit()
    conn.close()


def get_category_detail(category: str) -> dict | None:
    """Full category detail for the right panel."""
    conn = get_connection()
    cat = conn.execute(
        "SELECT name, group_name, icon, color, excluded FROM categories WHERE name = ?",
        (category,),
    ).fetchone()
    if not cat:
        conn.close()
        return None
    result = dict(cat)

    b = conn.execute("SELECT amount FROM category_budgets WHERE category = ?", (category,)).fetchone()
    result["budget"] = b["amount"] if b else 0

    now = datetime.now()
    import calendar as _cal
    last_day = _cal.monthrange(now.year, now.month)[1]
    month_start = f"{now.year}-{now.month:02d}-01"
    month_end = f"{now.year}-{now.month:02d}-{last_day:02d}"

    cur = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE category = ? AND date >= ? AND date <= ? AND status = 'approved'",
        (category, month_start, month_end),
    ).fetchone()
    result["current_month_spent"] = round(cur["total"], 2)

    # Yearly metrics for up to last 5 years
    yearly_metrics = []
    for y in range(now.year, now.year - 5, -1):
        yr = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) as total,
                   COUNT(DISTINCT strftime('%Y-%m', date)) as month_count
               FROM expenses WHERE category = ? AND date >= ? AND date <= ? AND status = 'approved'""",
            (category, f"{y}-01-01", f"{y}-12-31"),
        ).fetchone()
        if yr["total"] > 0:
            mc = yr["month_count"] or 1
            yearly_metrics.append({
                "year": y,
                "spent": round(yr["total"], 2),
                "avg_monthly": round(yr["total"] / mc, 2),
            })
    result["yearly_metrics"] = yearly_metrics
    result["current_month_name"] = now.strftime("%B %Y")

    conn.close()
    return result


def get_category_monthly_history(category: str, months: int = 18) -> dict:
    """Monthly spending history for chart + budget line."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y-%m', date) as month, SUM(amount) as spent
           FROM expenses WHERE category = ? AND date >= date('now', ?) AND status = 'approved'
           GROUP BY month ORDER BY month""",
        (category, f"-{months} months"),
    ).fetchall()
    b = conn.execute("SELECT amount FROM category_budgets WHERE category = ?", (category,)).fetchone()
    conn.close()
    return {"months": [dict(r) for r in rows], "budget": b["amount"] if b else 0}


def get_category_transactions_grouped(category: str, months: int = 6) -> list[dict]:
    """Transactions for a category grouped by month."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM expenses WHERE category = ? AND date >= date('now', ?) AND status = 'approved'
           ORDER BY date DESC""",
        (category, f"-{months} months"),
    ).fetchall()
    conn.close()

    from collections import OrderedDict
    groups: OrderedDict[str, dict] = OrderedDict()
    for r in rows:
        m = r["date"][:7]
        if m not in groups:
            groups[m] = {"month": m, "transactions": [], "total": 0}
        groups[m]["transactions"].append(dict(r))
        groups[m]["total"] = round(groups[m]["total"] + r["amount"], 2)
    return list(groups.values())


def update_category_details(name: str, icon: str | None = None, color: str | None = None,
                            excluded: bool | None = None):
    conn = get_connection()
    if icon is not None:
        conn.execute("UPDATE categories SET icon = ? WHERE name = ?", (icon, name))
    if color is not None:
        conn.execute("UPDATE categories SET color = ? WHERE name = ?", (color, name))
    if excluded is not None:
        conn.execute("UPDATE categories SET excluded = ? WHERE name = ?", (1 if excluded else 0, name))
    conn.commit()
    conn.close()


# --- Tags ---

def get_all_tags() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT id, name, color FROM tags ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_tag(name: str, color: str = "#3b82f6") -> dict:
    conn = get_connection()
    cur = conn.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name.strip(), color))
    conn.commit()
    tag = {"id": cur.lastrowid, "name": name.strip(), "color": color}
    conn.close()
    return tag


def update_tag(tag_id: int, name: str, color: str) -> dict:
    conn = get_connection()
    conn.execute("UPDATE tags SET name = ?, color = ? WHERE id = ?", (name.strip(), color, tag_id))
    conn.commit()
    conn.close()
    return {"id": tag_id, "name": name.strip(), "color": color}


def delete_tag(tag_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM expense_tags WHERE tag_id = ?", (tag_id,))
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    conn.close()


def get_tags_for_expense(expense_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.id, t.name, t.color FROM tags t
           JOIN expense_tags et ON t.id = et.tag_id
           WHERE et.expense_id = ?
           ORDER BY t.name""",
        (expense_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tags_for_expenses(expense_ids: list[int]) -> dict[int, list[dict]]:
    if not expense_ids:
        return {}
    conn = get_connection()
    placeholders = ",".join("?" for _ in expense_ids)
    rows = conn.execute(
        f"""SELECT et.expense_id, t.id, t.name, t.color FROM tags t
            JOIN expense_tags et ON t.id = et.tag_id
            WHERE et.expense_id IN ({placeholders})
            ORDER BY t.name""",
        expense_ids,
    ).fetchall()
    conn.close()
    result: dict[int, list[dict]] = {eid: [] for eid in expense_ids}
    for r in rows:
        result[r["expense_id"]].append({"id": r["id"], "name": r["name"], "color": r["color"]})
    return result


def set_expense_tags(expense_id: int, tag_ids: list[int]):
    conn = get_connection()
    conn.execute("DELETE FROM expense_tags WHERE expense_id = ?", (expense_id,))
    for tid in tag_ids:
        conn.execute("INSERT INTO expense_tags (expense_id, tag_id) VALUES (?, ?)", (expense_id, tid))
    conn.commit()
    conn.close()


# --- Backup & Restore ---

ALL_TABLES = [
    "expenses", "processed_messages", "category_overrides", "categories",
    "bills", "bill_resolutions", "app_settings", "tags", "expense_tags",
    "category_budgets", "account_labels",
]

# FK children first so deletes don't violate constraints
_DELETE_ORDER = [
    "expense_tags", "bill_resolutions", "category_budgets", "account_labels",
    "processed_messages", "category_overrides", "app_settings",
    "tags", "bills", "expenses", "categories",
]


def export_all_data() -> dict:
    conn = get_connection()
    tables = {}
    for table in ALL_TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        tables[table] = [dict(r) for r in rows]
    conn.close()
    return {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "tables": tables,
    }


def import_all_data(data: dict):
    if "version" not in data or "tables" not in data:
        raise ValueError("Invalid backup format: missing 'version' or 'tables' keys")

    conn = get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # Delete all existing data
        for table in _DELETE_ORDER:
            conn.execute(f"DELETE FROM {table}")

        # Insert from backup
        for table in ALL_TABLES:
            rows = data["tables"].get(table, [])
            if not rows:
                continue
            columns = list(rows[0].keys())
            placeholders = ",".join("?" for _ in columns)
            col_names = ",".join(columns)
            for row in rows:
                values = [row[c] for c in columns]
                conn.execute(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    # Re-run migrations to ensure schema is up to date
    init_db()


# --- Refunds ---

def create_refund(original_id: int, amount: float) -> int:
    """Create a refund (negative amount) transaction linked to the original."""
    conn = get_connection()
    orig = conn.execute("SELECT * FROM expenses WHERE id = ?", (original_id,)).fetchone()
    if not orig:
        conn.close()
        raise ValueError("Original transaction not found")

    # Check not already refunded
    existing = conn.execute(
        "SELECT id FROM expenses WHERE refund_of = ?", (original_id,)
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError("Transaction already refunded")

    refund_amount = -abs(amount)
    cur = conn.execute(
        """INSERT INTO expenses (date, raw_text, item, amount, category, person,
           telegram_message_id, notes, account, status, refund_of)
           VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 'approved', ?)""",
        (
            datetime.now().strftime("%Y-%m-%d"),
            orig["raw_text"],
            orig["item"],
            refund_amount,
            orig["category"],
            orig["person"],
            f"Refund of transaction #{original_id}",
            orig["account"] or "",
            original_id,
        ),
    )
    refund_id = cur.lastrowid
    conn.commit()
    conn.close()
    return refund_id


def get_expense_by_id(expense_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_refund_for(expense_id: int) -> dict | None:
    """Get the refund transaction for a given expense, if any."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM expenses WHERE refund_of = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
