from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Query, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

import db
import gsheet
import llm
import telegram

app = FastAPI(title="Expense Tracker")


class ExpenseUpdate(BaseModel):
    date: str
    item: str
    amount: float
    category: str
    notes: str = ""
    account: str = ""
    apply_override: bool = False
    tag_ids: Optional[List[int]] = None

async def sync_telegram_once() -> dict:
    """Fetch and process new Telegram messages once. Returns sync stats."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or bot_token == "your_bot_token_here":
        return {"error": "TELEGRAM_BOT_TOKEN not set"}
    if not chat_id or chat_id == "your_chat_id_here":
        return {"error": "TELEGRAM_CHAT_ID not set"}

    last_update_id = int(db.get_setting("last_update_id", "0"))

    messages_processed = 0
    expenses_added = 0

    messages, last_update_id = await telegram.fetch_new_messages(bot_token, chat_id, last_update_id)
    db.set_setting("last_update_id", str(last_update_id))
    for msg in messages:
        if db.is_message_processed(msg["message_id"]):
            continue
        print(f"[Sync] Processing: {msg['text']}")
        expenses = await llm.parse_expense(msg["text"])
        print(f"[Sync] LLM returned {len(expenses)} expenses: {expenses}")
        if not expenses:
            print(f"[Sync] No expenses parsed, skipping")
            db.mark_message_processed(msg["message_id"])
            messages_processed += 1
            continue
        for i, exp in enumerate(expenses):
            try:
                override = db.get_category_override(exp["item"])
                if override:
                    print(f"[Sync] Category override: {exp['category']} → {override} for '{exp['item']}'")
                    exp["category"] = override
                db.insert_expense(
                    date=msg["date"],
                    raw_text=msg["text"],
                    item=exp["item"],
                    amount=exp["amount"],
                    category=exp["category"],
                    person=exp["person"],
                    telegram_message_id=msg["message_id"] if i == 0 else None,
                    notes=exp.get("notes", ""),
                    account=exp.get("account", ""),
                    status="pending",
                )
                expenses_added += 1
                print(f"[Sync] Stored: {exp['item']} - {exp['amount']} ({exp['category']})")
            except Exception as e:
                print(f"[Sync] DB insert error: {e}")
        db.mark_message_processed(msg["message_id"])
        messages_processed += 1

    db.set_setting("last_sync_at", datetime.now().isoformat())
    return {"messages_processed": messages_processed, "expenses_added": expenses_added}


async def sync_gsheet_once() -> dict:
    """Fetch and process new messages from Google Sheet. Returns sync stats."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        return {"error": "GOOGLE_SHEET_ID not set"}

    last_row = int(db.get_setting("last_sheet_row", "0"))

    messages_processed = 0
    expenses_added = 0

    try:
        messages, new_last_row = gsheet.fetch_new_messages(sheet_id, last_row)
    except Exception as e:
        return {"error": f"Google Sheet read failed: {e}"}

    db.set_setting("last_sheet_row", str(new_last_row))

    for msg in messages:
        if db.is_message_processed(msg["message_id"]):
            continue
        print(f"[GSheet Sync] Processing: {msg['text']}")
        expenses = await llm.parse_expense(msg["text"])
        print(f"[GSheet Sync] LLM returned {len(expenses)} expenses: {expenses}")
        if not expenses:
            print(f"[GSheet Sync] No expenses parsed, skipping")
            db.mark_message_processed(msg["message_id"])
            messages_processed += 1
            continue
        for i, exp in enumerate(expenses):
            try:
                override = db.get_category_override(exp["item"])
                if override:
                    print(f"[GSheet Sync] Category override: {exp['category']} → {override} for '{exp['item']}'")
                    exp["category"] = override
                db.insert_expense(
                    date=msg["date"],
                    raw_text=msg["text"],
                    item=exp["item"],
                    amount=exp["amount"],
                    category=exp["category"],
                    person=exp["person"],
                    telegram_message_id=msg["message_id"] if i == 0 else None,
                    notes=exp.get("notes", ""),
                    account=exp.get("account", ""),
                    status="pending",
                )
                expenses_added += 1
                print(f"[GSheet Sync] Stored: {exp['item']} - {exp['amount']} ({exp['category']})")
            except Exception as e:
                print(f"[GSheet Sync] DB insert error: {e}")
        db.mark_message_processed(msg["message_id"])
        messages_processed += 1

    db.set_setting("last_sync_at", datetime.now().isoformat())
    return {"messages_processed": messages_processed, "expenses_added": expenses_added}


@app.on_event("startup")
async def startup():
    db.init_db()


@app.post("/telegram/sync")
async def telegram_sync():
    """Sync messages. Uses Google Sheet if configured, falls back to Telegram."""
    try:
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        if sheet_id:
            result = await sync_gsheet_once()
        else:
            result = await sync_telegram_once()
        if "error" in result:
            return {"status": "error", **result}
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/gsheet/sync")
async def gsheet_sync():
    """Sync messages from Google Sheet explicitly."""
    try:
        result = await sync_gsheet_once()
        if "error" in result:
            return {"status": "error", **result}
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = Path(__file__).parent / "dashboard.html"
    return html_path.read_text()


@app.get("/transactions", response_class=HTMLResponse)
def transactions():
    html_path = Path(__file__).parent / "transactions.html"
    return html_path.read_text()


@app.get("/admin", response_class=HTMLResponse)
def admin():
    html_path = Path(__file__).parent / "admin.html"
    return html_path.read_text()


@app.get("/accounts-page", response_class=HTMLResponse)
def accounts_page():
    html_path = Path(__file__).parent / "accounts.html"
    return html_path.read_text()


@app.get("/reports-page", response_class=HTMLResponse)
def reports_page():
    html_path = Path(__file__).parent / "reports.html"
    return html_path.read_text()


# --- Accounts ---

@app.get("/reports/accounts")
def account_summary(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    return {"accounts": db.get_account_summary(start, end)}


@app.get("/reports/accounts/transactions")
def account_transactions(
    account: str = Query(..., description="Account name"),
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    return {"transactions": db.get_account_transactions(account, start, end)}


class AccountLabelUpdate(BaseModel):
    account_name: str
    label: str
    icon: Optional[str] = None
    color: Optional[str] = None


@app.put("/accounts/label")
def set_account_label(body: AccountLabelUpdate):
    db.set_account_label(body.account_name, body.label, body.icon, body.color)
    return {"status": "updated", "account_name": body.account_name, "label": body.label}


# --- Categories ---

class CategoryCreate(BaseModel):
    name: str
    group_name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    excluded: bool = False


class GroupRename(BaseModel):
    old_name: str
    new_name: str


class CategoryGroupUpdate(BaseModel):
    group_name: Optional[str] = None


class BudgetUpdate(BaseModel):
    amount: float


class CategoryDetailsUpdate(BaseModel):
    icon: Optional[str] = None
    color: Optional[str] = None
    excluded: Optional[bool] = None
    need_want: Optional[str] = None


@app.get("/categories")
def list_categories(grouped: bool = Query(False)):
    if grouped:
        return db.get_categories_grouped()
    return {"categories": db.get_all_categories()}


@app.get("/categories/meta")
def categories_meta():
    return db.get_category_meta()


@app.get("/categories/spending")
def categories_spending(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    if not start or not end:
        start, end = _month_range()
    return db.get_categories_with_spending(start, end)


@app.post("/categories")
def create_category(body: CategoryCreate):
    name = body.name.strip()
    if not name:
        return {"error": "Category name cannot be empty"}, 400
    try:
        db.add_category(name, body.group_name)
    except Exception:
        return {"error": "Category already exists"}
    if body.icon or body.color or body.excluded:
        db.update_category_details(name, body.icon, body.color, body.excluded)
    return {"status": "created", "name": name}


@app.delete("/categories")
def remove_category(name: str = Query(...)):
    db.delete_category(name)
    return {"status": "deleted", "name": name}


@app.put("/categories/{name}/group")
def update_category_group(name: str, body: CategoryGroupUpdate):
    db.update_category_group(name, body.group_name)
    return {"status": "updated", "name": name, "group_name": body.group_name}


@app.put("/categories/{name}/budget")
def set_category_budget(name: str, body: BudgetUpdate):
    db.set_category_budget(name, body.amount)
    return {"status": "updated", "name": name, "budget": body.amount}


@app.get("/categories/{name}/detail")
def category_detail(name: str):
    detail = db.get_category_detail(name)
    if not detail:
        return {"error": "Category not found"}
    return detail


@app.get("/categories/{name}/history")
def category_history(name: str, months: int = Query(18)):
    return db.get_category_monthly_history(name, months)


@app.get("/categories/{name}/transactions-grouped")
def category_transactions_grouped(name: str, months: int = Query(6)):
    return {"groups": db.get_category_transactions_grouped(name, months)}


@app.put("/categories/{name}/details")
def update_cat_details(name: str, body: CategoryDetailsUpdate):
    db.update_category_details(name, body.icon, body.color, body.excluded, body.need_want)
    return {"status": "updated"}


@app.put("/groups/rename")
def rename_group(body: GroupRename):
    db.rename_group(body.old_name, body.new_name)
    return {"status": "renamed", "old_name": body.old_name, "new_name": body.new_name}


@app.delete("/groups/{group_name}")
def delete_group(group_name: str):
    db.delete_group(group_name)
    return {"status": "deleted", "group_name": group_name}


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Expenses ---

@app.get("/sync/status")
def sync_status():
    last_sync = db.get_setting("last_sync_at", "")
    return {"last_sync_at": last_sync}


@app.get("/expenses")
def list_expenses(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500),
):
    if not start:
        start = "2000-01-01"
    if not end:
        end = "2099-12-31"
    expenses = db.get_expenses_by_date_range(start, end)
    return {"expenses": expenses[:limit], "total": len(expenses)}


class ExpenseCreate(BaseModel):
    date: str
    item: str
    amount: float
    category: str
    notes: str = ""
    account: str = ""


@app.post("/expenses")
def create_expense(body: ExpenseCreate):
    expense_id = db.insert_expense(
        date=body.date,
        raw_text="manual",
        item=body.item,
        amount=body.amount,
        category=body.category,
        person=None,
        telegram_message_id=None,
        notes=body.notes,
        account=body.account,
        status="approved",
    )
    return {"status": "created", "id": expense_id}


@app.get("/expenses/pending")
def list_pending_expenses():
    return {"expenses": db.get_pending_expenses()}


class BulkApproveRequest(BaseModel):
    ids: List[int]


@app.put("/expenses/approve-bulk")
def approve_bulk(body: BulkApproveRequest):
    db.bulk_approve_expenses(body.ids)
    return {"status": "approved", "count": len(body.ids)}


@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseUpdate):
    db.update_expense(expense_id, body.date, body.item, body.amount, body.category, body.notes, body.account)
    if body.apply_override:
        db.upsert_category_override(body.item, body.category)
    if body.tag_ids is not None:
        db.set_expense_tags(expense_id, body.tag_ids)
    return {"status": "updated", "id": expense_id}


@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int):
    expense = db.get_expense_by_id(expense_id)
    if not expense:
        return {"error": "Not found"}
    return expense


@app.get("/expenses/{expense_id}/linked")
def get_linked_transaction(expense_id: int):
    expense = db.get_expense_by_id(expense_id)
    if not expense:
        return {"parent": None, "refund": None}
    result = {"parent": None, "refund": None}
    # If this is a refund, fetch the parent
    if expense.get("refund_of"):
        result["parent"] = db.get_expense_by_id(expense["refund_of"])
    # If this is an original, fetch the refund child
    refund = db.get_refund_for(expense_id)
    if refund:
        result["refund"] = refund
    return result


@app.put("/expenses/{expense_id}/approve")
def approve_expense(expense_id: int):
    db.approve_expense(expense_id)
    return {"status": "approved", "id": expense_id}


@app.put("/expenses/{expense_id}/discard")
def discard_expense(expense_id: int):
    db.discard_expense(expense_id)
    return {"status": "discarded", "id": expense_id}


# --- Category Overrides ---

@app.get("/category-overrides")
def list_overrides():
    return {"overrides": db.get_all_overrides()}


# --- Chart Data ---

@app.get("/reports/need-want-breakdown")
def need_want_breakdown(start: str = Query(...), end: str = Query(...)):
    return db.get_need_want_breakdown(start, end)


@app.get("/reports/chart/monthly")
def chart_monthly(months: int = Query(12, ge=1, le=36)):
    return {"data": db.get_monthly_bar_data(months)}


@app.get("/reports/chart/daily-comparison/{year}/{month}")
def chart_daily_comparison(year: int, month: int):
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]

    # Current month daily totals
    current = db.get_daily_totals(year, month)

    # Historical: up to 12 previous months
    hist_by_day: dict[int, list[float]] = {d: [] for d in range(1, 32)}
    for i in range(1, 13):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        hist_days_in_month = calendar.monthrange(y, m)[1]
        monthly = db.get_daily_totals(y, m)
        if not monthly:
            continue
        for d in range(1, hist_days_in_month + 1):
            hist_by_day[d].append(monthly.get(d, 0))

    # Build cumulative series
    current_cum = []
    hist_cum = []
    c_total = 0
    h_total = 0
    for d in range(1, days_in_month + 1):
        c_total += current.get(d, 0)
        current_cum.append(round(c_total, 2))
        counts = hist_by_day[d]
        h_total += (sum(counts) / len(counts)) if counts else 0
        hist_cum.append(round(h_total, 2))

    num_hist = max(len(v) for v in hist_by_day.values() if v) if any(hist_by_day.values()) else 0
    return {
        "days": list(range(1, days_in_month + 1)),
        "current": current_cum,
        "historical_avg": hist_cum,
        "months_averaged": num_hist,
    }


@app.get("/reports/chart/weekly/{year}/{month}")
def chart_weekly(year: int, month: int):
    return {"data": db.get_weekly_breakdown_for_month(year, month), "year": year, "month": month}


# --- Reports ---

def _week_range(date_str: Optional[str] = None):
    d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.now().date()
    start = d - timedelta(days=d.weekday())  # Monday
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _month_range(year: Optional[int] = None, month: Optional[int] = None):
    now = datetime.now().date()
    y = year or now.year
    m = month or now.month
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y + 1:04d}-01-01"
    else:
        end = f"{y:04d}-{m + 1:02d}-01"
    # end is exclusive, so use the day before
    end_date = datetime.strptime(end, "%Y-%m-%d").date() - timedelta(days=1)
    return start, end_date.isoformat()


@app.get("/reports/weekly")
def weekly_report():
    start, end = _week_range()
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/weekly/{date}")
def weekly_report_by_date(date: str):
    start, end = _week_range(date)
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/monthly")
def monthly_report():
    start, end = _month_range()
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/monthly/{year}/{month}")
def monthly_report_by_month(year: int, month: int):
    start, end = _month_range(year, month)
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/yearly")
def yearly_report():
    year = datetime.now().year
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/yearly/{year}")
def yearly_report_by_year(year: int):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    summary = db.get_summary(start, end)
    total = sum(row["total"] for row in summary)
    return {"period": f"{start} to {end}", "categories": summary, "total": total}


@app.get("/reports/group-summary")
def group_summary_report(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    if not start:
        start, _ = _month_range()
    if not end:
        _, end = _month_range()
    data = db.get_group_summary(start, end)
    total = sum(r["total"] for r in data)
    return {"period": f"{start} to {end}", "groups": data, "total": total}


@app.get("/reports/category")
def category_report(
    category: str = Query(..., description="Category name"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    expenses = db.get_expenses_by_category(category, start, end)
    total = sum(e["amount"] for e in expenses)
    return {"category": category, "expenses": expenses, "total": total}


@app.get("/reports/person")
def person_report(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    return {"persons": db.get_person_summary(start, end)}


@app.get("/reports/trends")
def trends_report(months: int = Query(6, ge=1, le=24)):
    return {"trends": db.get_monthly_trends(months)}


# --- Bills ---

class BillCreate(BaseModel):
    name: str
    amount: float
    category: str = ""
    frequency: str
    anchor_date: str
    alert_days: int = 15
    notes: str = ""
    end_date: Optional[str] = None


class BillUpdate(BaseModel):
    name: str
    amount: float
    category: str = ""
    frequency: str
    anchor_date: str
    alert_days: int = 15
    notes: str = ""
    end_date: Optional[str] = None


class BillResolve(BaseModel):
    due_date: str
    expense_id: Optional[int] = None


@app.get("/bills-page", response_class=HTMLResponse)
def bills_page():
    html_path = Path(__file__).parent / "bills.html"
    return html_path.read_text()


@app.get("/bills/calendar")
def bill_calendar(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    return {"events": db.get_bill_calendar(start, end)}


@app.get("/bills/alerts")
def bill_alerts():
    return {"alerts": db.get_upcoming_alerts()}


@app.get("/bills")
def list_bills():
    return {"bills": db.get_all_bills()}


@app.post("/bills")
def create_bill(body: BillCreate):
    bill_id = db.create_bill(
        body.name, body.amount, body.category, body.frequency,
        body.anchor_date, body.alert_days, body.notes, body.end_date,
    )
    return {"status": "created", "id": bill_id}


@app.put("/bills/{bill_id}")
def update_bill(bill_id: int, body: BillUpdate):
    db.update_bill(
        bill_id, body.name, body.amount, body.category, body.frequency,
        body.anchor_date, body.alert_days, body.notes, body.end_date,
    )
    return {"status": "updated", "id": bill_id}


@app.delete("/bills/{bill_id}")
def delete_bill(bill_id: int):
    db.delete_bill(bill_id)
    return {"status": "deleted", "id": bill_id}


@app.post("/bills/{bill_id}/resolve")
def resolve_bill(bill_id: int, body: BillResolve):
    db.resolve_bill(bill_id, body.due_date, body.expense_id)
    return {"status": "resolved", "bill_id": bill_id, "due_date": body.due_date}


@app.get("/bills/{bill_id}/history")
def bill_history(bill_id: int):
    return {"resolutions": db.get_bill_resolutions(bill_id)}


# --- Backup & Restore ---

@app.get("/backup/export")
def backup_export():
    data = db.export_all_data()
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"exptracker-backup-{datetime.now().strftime('%Y-%m-%d')}.json"
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/backup/import")
async def backup_import(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        data = json.loads(contents)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "error": "Invalid JSON file"}

    if "version" not in data or "tables" not in data:
        return {"status": "error", "error": "Invalid backup format: missing 'version' or 'tables' keys"}

    try:
        db.import_all_data(data)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"status": "ok", "message": "Backup restored successfully"}


# --- Tags ---

class RefundRequest(BaseModel):
    refund_type: str  # "full" or "partial"
    amount: Optional[float] = None


@app.post("/expenses/{expense_id}/refund")
def refund_expense(expense_id: int, body: RefundRequest):
    try:
        exp = db.get_expenses_by_date_range("2000-01-01", "2099-12-31")
        original = next((e for e in exp if e["id"] == expense_id), None)
        if not original:
            return {"status": "error", "error": "Transaction not found"}

        if body.refund_type == "partial":
            if not body.amount or body.amount <= 0:
                return {"status": "error", "error": "Partial refund requires a positive amount"}
            if body.amount > original["amount"]:
                return {"status": "error", "error": "Refund amount cannot exceed original amount"}
            refund_amount = body.amount
        else:
            refund_amount = original["amount"]

        refund_id = db.create_refund(expense_id, refund_amount)
        return {"status": "ok", "refund_id": refund_id}
    except ValueError as e:
        return {"status": "error", "error": str(e)}


class SplitItem(BaseModel):
    amount: float
    category: str


class SplitRequest(BaseModel):
    splits: List[SplitItem]


@app.post("/expenses/{expense_id}/split")
def split_expense(expense_id: int, body: SplitRequest):
    original = db.get_expense_by_id(expense_id)
    if not original:
        return {"status": "error", "error": "Transaction not found"}

    if len(body.splits) < 2:
        return {"status": "error", "error": "Need at least 2 splits"}

    total = round(sum(s.amount for s in body.splits), 2)
    if abs(total - original["amount"]) > 0.01:
        return {"status": "error", "error": f"Split total {total} != original {original['amount']}"}

    # Get tags from original
    tags_map = db.get_tags_for_expenses([expense_id])
    original_tag_ids = [t["id"] for t in tags_map.get(expense_id, [])]

    # Delete the original
    db.discard_expense(expense_id)

    # Create new transactions for each split
    new_ids = []
    for s in body.splits:
        new_id = db.insert_expense(
            date=original["date"],
            raw_text=original.get("raw_text") or "split",
            item=original["item"],
            amount=s.amount,
            category=s.category,
            person=original.get("person"),
            telegram_message_id=None,
            notes=original.get("notes") or "",
            account=original.get("account") or "",
            status="approved",
        )
        if original_tag_ids:
            db.set_expense_tags(new_id, original_tag_ids)
        new_ids.append(new_id)

    return {"status": "ok", "new_ids": new_ids}


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"


class TagUpdate(BaseModel):
    name: str
    color: str


@app.get("/tags")
def list_tags():
    return {"tags": db.get_all_tags()}


@app.post("/tags")
def create_tag(body: TagCreate):
    try:
        tag = db.create_tag(body.name, body.color)
        return {"status": "created", "tag": tag}
    except Exception:
        return {"error": "Tag already exists"}


@app.put("/tags/{tag_id}")
def update_tag(tag_id: int, body: TagUpdate):
    tag = db.update_tag(tag_id, body.name, body.color)
    return {"status": "updated", "tag": tag}


@app.delete("/tags/{tag_id}")
def delete_tag(tag_id: int):
    db.delete_tag(tag_id)
    return {"status": "deleted", "id": tag_id}
