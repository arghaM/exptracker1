from __future__ import annotations

import json
import os
import httpx
import db

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT_TEMPLATE = """You are an expense parser for a family in India. Extract expenses from the following message.
Return a JSON array of objects with: person, item, amount, category, notes, account.
Categories: {categories}.
Amounts are in Indian Rupees (INR).

MESSAGE FORMATS:
You will receive two types of messages:

1. SIMPLE MESSAGES like "chicken 250" or "Ratnadeep 1057" or "Arjun bought shoes 2500"
   - Extract item, amount, category, person directly.

2. BANK/UPI TRANSACTION SMS like:
   "Sent Rs.280.00 From HDFC Bank A/C *8603 To RAM REDDY CHICKEN MARKET On 02/04/26 Ref 120942818795 ..."
   or "Debited Rs.500 from A/C *1234 to SWIGGY on 01/04/26 UPI Ref 998877665544"
   or similar bank notification formats.
   For these messages:
   - amount: extract from "Rs.280.00" or "Rs 280" or "INR 280" etc.
   - item: the merchant/store/recipient name (e.g. "RAM REDDY CHICKEN MARKET", "SWIGGY")
   - category: infer from the merchant name using the category rules below
   - person: "Unknown"
   - account: the bank account info, e.g. "HDFC A/C *8603" or "SBI A/C *1234"
   - notes: payment method + reference, e.g. "UPI | Ref: 120942818795"
     Include: payment method (UPI/NEFT/IMPS if mentioned) and reference number.

KNOWN LOCAL CONTEXT:
- "chicken" or "fish" or "mutton" or "CHICKEN MARKET" or "FISH MARKET" → category: Chicken & Fish
- "Zepto" or "zepto" or "Blinkit" or "blinkit" → category: Quick Delivery
- "Swiggy" or "swiggy" or "Zomato" or "zomato" → category: Order Out
- "Ratnadeep" = Ratnadeep grocery store → category: Groceries & Food, item: "Groceries (Ratnadeep)"
- "DMart" or "dmart" = DMart grocery store → category: Groceries & Food
- "restaurant" or "cafe" or "hotel" (dining context) → category: Restaurants
- "petrol" or "diesel" or "fuel" or "HP" or "BPCL" or "IOCL" or "petrol pump" → category: Petrol
- "rent" or "house rent" → category: Rent
- "Netflix" or "Hotstar" or "subscription" or "prime" or "YouTube Premium" → category: Subscription
- "Ola" or "Uber" or "auto" or "riksha" or "rapido" → category: Transport
- "electricity" or "bijli" or "gas" or "wifi" or "internet" or "recharge" or "BESCOM" or "TSSPDCL" → category: Utilities
- "medicine" or "medical" or "pharmacy" or "MEDPLUS" or "APOLLO PHARMACY" → category: Medicine
- "lab test" or "blood test" or "pathology" or "diagnostic" → category: Lab Test
- "doctor" or "hospital" or "consultation" or "clinic" → category: Doctor

PARSING RULES:
- If message is like "StoreName Amount" (e.g. "Ratnadeep 1057"), the store name is the item, not a person.
- If message is like "PersonName bought Item Amount", extract person, item, and amount.
- If person is not clearly mentioned as a human name, use "Unknown".
- If the message doesn't contain any expense information, return an empty array [].
- For simple messages without bank/UPI info, set notes and account to empty string "".
- For bank SMS, always populate account with bank info and notes with payment method + ref.

Respond ONLY with a valid JSON array, no other text."""


def _build_system_prompt() -> str:
    categories = db.get_all_categories()
    return SYSTEM_PROMPT_TEMPLATE.format(categories=", ".join(categories))


async def parse_expense(raw_text: str) -> list[dict]:
    prompt = f'Message: "{raw_text}"'
    system_prompt = _build_system_prompt()
    if not GROQ_API_KEY:
        print("[LLM] GROQ_API_KEY not set")
        return []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            text = result["choices"][0]["message"]["content"].strip()
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break
                else:
                    parsed = [parsed]
            if not isinstance(parsed, list):
                parsed = [parsed]
            # Validate each entry
            valid = []
            for entry in parsed:
                if not isinstance(entry, dict):
                    continue
                try:
                    amount = float(entry.get("amount", 0))
                except (ValueError, TypeError):
                    continue
                if amount <= 0:
                    continue
                valid.append({
                    "person": str(entry.get("person", "Unknown")) or "Unknown",
                    "item": str(entry.get("item", "Unknown")) or "Unknown",
                    "amount": amount,
                    "category": str(entry.get("category", "Other")) or "Other",
                    "notes": str(entry.get("notes", "")) or "",
                    "account": str(entry.get("account", "")) or "",
                })
            return valid
    except Exception as e:
        print(f"[LLM] Error parsing expense: {e}")
        return []
