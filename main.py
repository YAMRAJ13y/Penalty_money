import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Bad Word Penalty Tracker - Full-Stack Edition")

DB_FILE = os.path.join(os.path.dirname(__file__), "database.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Create static directory if it doesn't exist
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

fixed_members = [
    "Krishiv", "Sumit", "Jesika", "Parth", "Jay", 
    "Raj", "Riya .S", "Riya .D", "Renuka", "Kashish"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        total_fine INTEGER DEFAULT 0,
        paid_fine INTEGER DEFAULT 0,
        violations INTEGER DEFAULT 0
    )
    """)
    
    # Check if paid_fine column exists
    cursor.execute("PRAGMA table_info(members)")
    columns = [col[1] for col in cursor.fetchall()]
    if "paid_fine" not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN paid_fine INTEGER DEFAULT 0")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        timestamp TEXT,
        amount TEXT
    )
    """)
    
    # Seed fixed members
    for name in fixed_members:
        cursor.execute("INSERT OR IGNORE INTO members (name, total_fine, paid_fine, violations) VALUES (?, 0, 0, 0)", (name,))
        
    conn.commit()
    conn.close()

init_db()

# Models
class ActionRequest(BaseModel):
    name: str
    action: str  # "add", "deduct", or "pay"
    amount: int = 10

@app.get("/api/members")
def get_members():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, total_fine, paid_fine, violations FROM members ORDER BY total_fine DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"name": row[0], "totalFine": row[1], "paidFine": row[2], "violations": row[3]}
        for row in rows
    ]

@app.post("/api/action")
def record_action(req: ActionRequest):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT total_fine, paid_fine, violations FROM members WHERE name = ?", (req.name,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Member not found")
        
    current_fine, current_paid, current_violations = row
    amt = req.amount if req.amount in [5, 10] else 10
    
    if req.action == "add":
        new_fine = current_fine + amt
        new_paid = current_paid
        new_violations = current_violations + 1
        amt_str = f"+₹{amt}"
    elif req.action == "deduct":
        if current_fine <= 0:
            conn.close()
            raise HTTPException(status_code=400, detail="Fine balance is already ₹0")
        new_fine = max(current_fine - amt, 0)
        new_paid = current_paid
        new_violations = max(current_violations - 1, 0)
        amt_str = f"-₹{amt}"
    elif req.action == "pay":
        if current_fine <= 0:
            conn.close()
            raise HTTPException(status_code=400, detail="No pending fine to pay")
        pay_amount = min(amt, current_fine)
        new_fine = current_fine - pay_amount
        new_paid = current_paid + pay_amount
        new_violations = current_violations
        amt_str = f"Paid ₹{pay_amount}"
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid action")
        
    cursor.execute("UPDATE members SET total_fine = ?, paid_fine = ?, violations = ? WHERE name = ?", (new_fine, new_paid, new_violations, req.name))
    
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
    cursor.execute("INSERT INTO transactions (name, timestamp, amount) VALUES (?, ?, ?)", (req.name, timestamp, amt_str))
    
    conn.commit()
    conn.close()
    return {"status": "success", "new_fine": new_fine, "new_paid": new_paid, "new_violations": new_violations}


@app.get("/api/transactions")
def get_transactions():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, timestamp, amount FROM transactions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"name": row[0], "timestamp": row[1], "amount": row[2]}
        for row in rows
    ]

@app.post("/api/reset")
def reset_all_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE members SET total_fine = 0, paid_fine = 0, violations = 0")
    cursor.execute("DELETE FROM transactions")
    conn.commit()
    conn.close()
    return {"status": "success"}

# Serve static files for frontend routes
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
