import os
from dotenv import load_dotenv

load_dotenv()

import db
db.init_db()

import uvicorn
from app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Expense Tracker on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
