import sqlite3
import psycopg2
import os

def migrate():
    # 1. Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL environment variable not set!")
        return

    print("Connecting to Neon PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(db_url, sslmode='require')
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"Connection Failed: {e}")
        return

    # Create tables first
    print("Creating tables in Neon if they don't exist...")
    pg_cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE,
        total_fine INTEGER DEFAULT 0,
        paid_fine INTEGER DEFAULT 0,
        violations INTEGER DEFAULT 0
    )
    """)
    pg_cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        name TEXT,
        timestamp TEXT,
        amount TEXT
    )
    """)

    # 2. Migrate Members
    print("Migrating members data...")
    sqlite_cursor.execute("SELECT name, total_fine, paid_fine, violations FROM members")
    members = sqlite_cursor.fetchall()
    
    for m in members:
        # Use ON CONFLICT to either insert or update
        pg_cursor.execute(
            """
            INSERT INTO members (name, total_fine, paid_fine, violations) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (name) 
            DO UPDATE SET total_fine = EXCLUDED.total_fine, paid_fine = EXCLUDED.paid_fine, violations = EXCLUDED.violations
            """,
            (m[0], m[1], m[2], m[3])
        )
    
    # 3. Migrate Transactions
    print("Migrating transaction logs...")
    sqlite_cursor.execute("SELECT name, timestamp, amount FROM transactions")
    txs = sqlite_cursor.fetchall()
    
    # Clear remote transactions first to avoid duplicates
    pg_cursor.execute("DELETE FROM transactions")
    
    for tx in txs:
        pg_cursor.execute(
            "INSERT INTO transactions (name, timestamp, amount) VALUES (%s, %s, %s)",
            (tx[0], tx[1], tx[2])
        )

    # 4. Save and Close
    pg_conn.commit()
    print("Migration Successful! Your data is now in the Cloud.")
    
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    migrate()
