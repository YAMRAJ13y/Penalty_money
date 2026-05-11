import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Bad Word Penalty Tracker - Full-Stack Edition")

# Configuration
DB_FILE = os.path.join(os.path.dirname(__file__), "database.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_conn():
    if DATABASE_URL:
        import psycopg2
        # Use SSL for Neon/Heroku/Supabase
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect(DB_FILE)

def get_placeholder():
    return "%s" if DATABASE_URL else "?"

# Create static directory if it doesn't exist
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

fixed_members = [
    "Krishiv", "Sumit", "Jesika", "Parth", "Jay", 
    "Raj", "Riya .S", "Riya .D", "Renuka", "Kashish"
]

def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    p = get_placeholder()
    
    # Create tables
    if DATABASE_URL:
        # Postgres syntax
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            total_fine INTEGER DEFAULT 0,
            paid_fine INTEGER DEFAULT 0,
            violations INTEGER DEFAULT 0
        )
        """)
    else:
        # SQLite syntax
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            total_fine INTEGER DEFAULT 0,
            paid_fine INTEGER DEFAULT 0,
            violations INTEGER DEFAULT 0
        )
        """)
    
    # Check if paid_fine column exists (Postgres usually doesn't need this if created fresh, but good for migrations)
    if not DATABASE_URL:
        cursor.execute("PRAGMA table_info(members)")
        columns = [col[1] for col in cursor.fetchall()]
        if "paid_fine" not in columns:
            cursor.execute("ALTER TABLE members ADD COLUMN paid_fine INTEGER DEFAULT 0")

    if DATABASE_URL:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            name TEXT,
            timestamp TEXT,
            amount TEXT
        )
        """)
    else:
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
        try:
            cursor.execute(f"INSERT INTO members (name, total_fine, paid_fine, violations) VALUES ({p}, 0, 0, 0) ON CONFLICT (name) DO NOTHING", (name,))
        except:
            # Fallback for SQLite which doesn't support ON CONFLICT in some versions or uses INSERT OR IGNORE
            cursor.execute(f"INSERT OR IGNORE INTO members (name, total_fine, paid_fine, violations) VALUES ({p}, 0, 0, 0)", (name,))
        
    conn.commit()
    conn.close()

init_db()

# Models
class ActionRequest(BaseModel):
    name: str
    action: str  # "add", "deduct", or "pay"
    amount: int = 10

class LoginRequest(BaseModel):
    role: str
    password: str

# In-memory session check for demonstration
VALID_CREDENTIALS = {
    "admin": "nahi@13",
    "user": "user123"
}

@app.post("/api/login")
def login(req: LoginRequest):
    if req.role in VALID_CREDENTIALS and VALID_CREDENTIALS[req.role] == req.password:
        return {"status": "success", "role": req.role}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/members")
def get_members():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, total_fine, paid_fine, violations FROM members ORDER BY total_fine DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"name": row[0], "totalFine": row[1], "paidFine": row[2], "violations": row[3]}
        for row in rows
    ]

@app.post("/api/action")
def record_action(req: ActionRequest, role: str = ""):
    conn = get_db_conn()
    cursor = conn.cursor()
    p = get_placeholder()
    
    cursor.execute(f"SELECT total_fine, paid_fine, violations FROM members WHERE name = {p}", (req.name,))
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
        
    cursor.execute(f"UPDATE members SET total_fine = {p}, paid_fine = {p}, violations = {p} WHERE name = {p}", (new_fine, new_paid, new_violations, req.name))
    
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
    cursor.execute(f"INSERT INTO transactions (name, timestamp, amount) VALUES ({p}, {p}, {p})", (req.name, timestamp, amt_str))
    
    conn.commit()
    conn.close()
    return {"status": "success", "new_fine": new_fine, "new_paid": new_paid, "new_violations": new_violations}


@app.get("/api/transactions")
def get_transactions():
    conn = get_db_conn()
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
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE members SET total_fine = 0, paid_fine = 0, violations = 0")
    cursor.execute("DELETE FROM transactions")
    conn.commit()
    conn.close()
    return {"status": "success"}

# Serve static files for frontend routes
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
