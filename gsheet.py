from __future__ import annotations

from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
CREDENTIALS_FILE = "credentials.json"


def _get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def fetch_new_messages(sheet_id: str, last_row: int) -> tuple[list[dict], int]:
    """Read new rows from the Google Sheet after last_row.

    The sheet is expected to have columns: A=timestamp, B=chat_id, C=message_id, D=text.
    Rows are 1-indexed (row 1 may be a header).

    Returns (messages, new_last_row) where messages match the telegram.py format:
        [{"message_id": int, "text": str, "date": "YYYY-MM-DD"}, ...]
    """
    service = _get_sheets_service()

    # Start reading from the row after last_row. If last_row is 0, start from row 2 (skip header).
    start_row = max(last_row + 1, 2)
    range_str = f"Sheet1!A{start_row}:D"

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=range_str)
        .execute()
    )

    rows = result.get("values", [])
    if not rows:
        return [], last_row

    messages = []
    new_last_row = start_row - 1  # will be incremented per row

    for i, row in enumerate(rows):
        new_last_row = start_row + i
        # Expect at least 4 columns: timestamp, chat_id, message_id, text
        if len(row) < 4:
            continue

        timestamp_str, _chat_id, message_id_str, text = row[0], row[1], row[2], row[3]

        if not text or not text.strip():
            continue

        try:
            message_id = int(message_id_str)
        except (ValueError, TypeError):
            continue

        # Parse date from the ISO timestamp logged by Apps Script
        try:
            date_str = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = datetime.now().strftime("%Y-%m-%d")

        messages.append({
            "message_id": message_id,
            "text": text,
            "date": date_str,
        })

    return messages, new_last_row
