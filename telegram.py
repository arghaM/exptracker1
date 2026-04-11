import httpx
from datetime import datetime

API_BASE = "https://api.telegram.org/bot{token}"


async def fetch_new_messages(bot_token: str, chat_id: str, last_update_id: int) -> tuple[list[dict], int]:
    """Fetch new messages from Telegram.
    Returns (messages, new_last_update_id).
    Each message dict has: message_id, text, date.
    """
    url = f"{API_BASE.format(token=bot_token)}/getUpdates"
    params = {"timeout": 5, "allowed_updates": '["message"]'}
    if last_update_id > 0:
        params["offset"] = last_update_id + 1

    messages = []
    new_last_update_id = last_update_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                return messages, new_last_update_id

            for update in data.get("result", []):
                update_id = update["update_id"]
                if update_id > new_last_update_id:
                    new_last_update_id = update_id

                msg = update.get("message", {})
                msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                print(f"[Telegram] Update {update_id}: chat_id={msg_chat_id}, expected={chat_id}, text={text!r}")

                if msg_chat_id == str(chat_id).strip() and text:
                    messages.append({
                        "message_id": msg["message_id"],
                        "text": text,
                        "date": datetime.fromtimestamp(msg["date"]).strftime("%Y-%m-%d"),
                    })
    except Exception as e:
        print(f"[Telegram] Error fetching messages: {e}")

    return messages, new_last_update_id
