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
    """Read all rows from the Google Sheet (duplicate check is done by caller via processed_messages).

    The sheet is expected to have columns: A=timestamp, B=chat_id, C=message_id, D=text.
    Row 1 is a header and is skipped.

    Returns (messages, new_last_row) where messages match the telegram.py format:
        [{"message_id": int, "text": str, "date": "YYYY-MM-DD"}, ...]
    """
    service = _get_sheets_service()

    # Always read all rows from row 2 (skip header), ignore last_row
    range_str = "Sheet1!A2:D"

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=range_str)
        .execute()
    )

    rows = result.get("values", [])
    if not rows:
        return [], 0

    messages = []

    for row in rows:
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

    return messages, 0
