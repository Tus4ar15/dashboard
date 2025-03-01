from flask import Flask, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import psycopg2
import json
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ============================
# Google Sheets API Setup
# ============================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "your_service_account.json"  # Replace with your JSON key file
SPREADSHEET_ID = "1gD5dHGu8g8N8-0gPTdDS8meYnCc6NGISmZYTVvtDMLs"  # Replace with your Google Sheet ID

def fetch_data():
    """
    Fetches all records from the first sheet of the specified Google Sheet.
    """
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        data = sheet.get_all_records()
        print("Data fetched successfully from Google Sheets.")
        return data
    except Exception as e:
        print("Error fetching data from Google Sheets:", str(e))
        return {"error": str(e)}

@app.route("/data", methods=["GET"])
def get_data():
    data = fetch_data()
    return jsonify(data)

@app.route("/")
def home():
    return "Database connected! Use /data to fetch data."

# ============================
# PostgreSQL Setup & Sync Code
# ============================

# Database connection parameters – update these for your PostgreSQL server
DB_HOST = "postgres"
DB_NAME = "gsheet"
DB_USER = "postgres"
DB_PASSWORD = "admin"
DB_PORT = "5432"  # Update if necessary

def get_db_connection():
    """
    Returns a new connection to the PostgreSQL database.
    """
    conn = psycopg2.connect(
         host=DB_HOST,
         database=DB_NAME,
         user=DB_USER,
         password=DB_PASSWORD,
         port=DB_PORT
    )
    return conn

def init_db():
    """
    Creates the 'gsheet_data' table if it doesn't exist.
    Assumes each row from Google Sheets has a unique 'id' key.
    """
    conn = get_db_connection()
    print(f"Connected to PostgreSQL at {DB_HOST}:{DB_PORT}")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gsheet_data (
            id TEXT PRIMARY KEY,
            row_data JSONB,
            row_hash TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully.")

def compute_row_hash(row):
    """
    Computes a SHA256 hash for a given row (dictionary).
    Using json.dumps with sorted keys ensures consistent ordering.
    """
    row_str = json.dumps(row, sort_keys=True)
    return hashlib.sha256(row_str.encode('utf-8')).hexdigest()

def sync_data():
    """
    Fetches data from Google Sheets and upserts each row into PostgreSQL.
    It checks changes by computing a hash of each row.
    """
    data = fetch_data()
    if isinstance(data, dict) and "error" in data:
        print("Error fetching data:", data["error"])
        return

    conn = get_db_connection()
    cur = conn.cursor()
    for row in data:
        # Assumes each row has a unique 'id' field.
        row_id = row.get("id")
        if row_id is None:
            # If no unique identifier is found, skip this row or implement alternative logic.
            continue
        hash_val = compute_row_hash(row)
        upsert_query = """
            INSERT INTO gsheet_data (id, row_data, row_hash, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE
            SET row_data = EXCLUDED.row_data,
                row_hash = EXCLUDED.row_hash,
                updated_at = NOW()
            WHERE gsheet_data.row_hash <> EXCLUDED.row_hash;
        """
        cur.execute(upsert_query, (row_id, json.dumps(row), hash_val))
    conn.commit()
    cur.close()
    conn.close()
    print("Sync complete.")

@app.route("/sync", methods=["GET"])
def trigger_sync():
    """
    Endpoint to manually trigger synchronization between Google Sheets and PostgreSQL.
    """
    sync_data()
    return jsonify({"message": "Sync completed."})

# ============================
# Background Scheduler Setup
# ============================

if __name__ == "__main__":
    # Initialize the database table
    init_db()
    
    # Set up background scheduler to sync data every 10 minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=sync_data, trigger="interval", minutes=10)
    scheduler.start()
    print("Background Scheduler started: Sync will run every 10 minutes.")
    
    # Log the server port and that it's running
    SERVER_PORT = 5000  # Default Flask port; change if needed.
    print(f"Server is running on http://localhost:{SERVER_PORT}")
    
    # Run the Flask app (disable the reloader to avoid duplicate scheduler jobs)
    try:
        app.run(debug=True, use_reloader=False, port=SERVER_PORT)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
