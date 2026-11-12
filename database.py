"""
database.py - Database setup and management for Nexus SaaS Platform.
Runs in Demo Mode on Vercel using ephemeral SQLite (/tmp/nexus.db) with
auto-seeded sample records, or local nexus.db when running locally.
Optionally supports PostgreSQL if DATABASE_URL / POSTGRES_URL is provided.
"""

import os
import random
import sqlite3
import ssl
import string
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
DEFAULT_SQLITE_PATH = "/tmp/nexus.db" if IS_VERCEL else os.path.join(BASE_DIR, "nexus.db")
DB_FILE = os.environ.get("SQLITE_DB_PATH", DEFAULT_SQLITE_PATH)

_db_initialized = False

DEMO_ORDERS = [
    ("NX-482910", "Rahim Ahmed", "rahim@techbd.io", "+8801712345678", "Tech Solutions BD", "Professional", "Monthly", 79.0, "Credit Card", "completed", "Team onboarding demo"),
    ("NX-739204", "Sarah Jenkins", "sarah@cloudscale.co", "+1-415-555-0192", "CloudScale Labs", "Enterprise", "Yearly", 159.0, "Credit Card", "completed", "Annual workspace plan"),
    ("NX-195382", "Tariqul Islam", "tariq@startuplab.dev", "+8801819001122", "StartupLab", "Starter", "Monthly", 29.0, "PayPal", "completed", "Initial starter subscription"),
]

DEMO_CONTACTS = [
    ("Nadia Rahman", "nadia@fintech.example", "Enterprise SSO Inquiry", "Hi Nexus team, we would like to evaluate SAML SSO for 45 seats."),
    ("David Chen", "david@acme.example", "API Rate Limits", "Could you share the webhook throughput limits on the Professional plan?"),
]


def _get_postgres_url():
    """Return configured PostgreSQL connection URL if present."""
    for key in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def is_postgres():
    """Return True when a PostgreSQL connection URL is configured."""
    url = _get_postgres_url()
    return url.startswith("postgres://") or url.startswith("postgresql://")


def is_demo_mode():
    """Return True when running in Demo Mode (Vercel without external DB, or DEMO_MODE=true)."""
    explicit = os.environ.get("DEMO_MODE", "").strip().lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False
    return IS_VERCEL and not is_postgres()


def _connect_postgres(url):
    """Open a pg8000 DB-API connection from a PostgreSQL URL."""
    import pg8000.dbapi

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sslmode = (query.get("sslmode", [""])[0] or "").lower()
    host = parsed.hostname or "localhost"

    ssl_context = None
    if sslmode != "disable" and (sslmode in ("require", "verify-ca", "verify-full") or host not in ("localhost", "127.0.0.1")):
        ssl_context = ssl.create_default_context()

    return pg8000.dbapi.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or "") if parsed.password is not None else None,
        host=host,
        port=parsed.port or 5432,
        database=(parsed.path or "").lstrip("/") or "postgres",
        ssl_context=ssl_context,
    )


def get_connection():
    """Establish and return a database connection (PostgreSQL or SQLite)."""
    pg_url = _get_postgres_url()
    if pg_url.startswith("postgres://") or pg_url.startswith("postgresql://"):
        return _connect_postgres(pg_url)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _format_sql(query):
    """Translate '?' placeholders to '%s' when running on PostgreSQL."""
    return query.replace("?", "%s") if is_postgres() else query


def _serialize_row(columns, row):
    """Convert a database row tuple/sqlite3.Row into a JSON-serializable dict."""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    record = {}
    for col, val in zip(columns, row):
        if isinstance(val, datetime):
            record[col] = val.strftime("%Y-%m-%d %H:%M:%S")
        else:
            record[col] = val
    return record


def _fetch_all_dicts(cursor):
    """Fetch all rows from cursor as a list of dicts."""
    columns = [desc[0] for desc in cursor.description]
    return [_serialize_row(columns, row) for row in cursor.fetchall()]


def _ensure_initialized():
    """Ensure database schema exists in the current process."""
    global _db_initialized
    if not is_postgres() and not os.path.exists(DB_FILE):
        _db_initialized = False
    if not _db_initialized:
        init_db()


def _seed_demo_records(cursor):
    """Populate initial demo orders and contacts when tables are empty in Demo Mode."""
    cursor.execute("SELECT COUNT(*) FROM orders")
    orders_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM contacts")
    contacts_count = cursor.fetchone()[0]

    if orders_count == 0:
        insert_order_sql = _format_sql("""
            INSERT INTO orders (
                order_number, customer_name, customer_email, customer_phone,
                company_name, plan_name, billing_cycle, amount,
                currency, payment_method, status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, CURRENT_TIMESTAMP)
        """)
        for row in DEMO_ORDERS:
            cursor.execute(insert_order_sql, row)

    if contacts_count == 0:
        insert_contact_sql = _format_sql("""
            INSERT INTO contacts (name, email, subject, message, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """)
        for row in DEMO_CONTACTS:
            cursor.execute(insert_contact_sql, row)


def init_db():
    """Create the necessary database tables if they do not already exist."""
    global _db_initialized
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT,
                company_name TEXT,
                plan_name TEXT NOT NULL,
                billing_cycle TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                currency TEXT DEFAULT 'USD',
                payment_method TEXT DEFAULT 'Credit Card',
                status TEXT DEFAULT 'completed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        target = "PostgreSQL"
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT,
                company_name TEXT,
                plan_name TEXT NOT NULL,
                billing_cycle TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                payment_method TEXT DEFAULT 'Credit Card',
                status TEXT DEFAULT 'completed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        target = DB_FILE

    if is_demo_mode():
        _seed_demo_records(cursor)

    conn.commit()
    conn.close()
    _db_initialized = True
    print(f"Database initialized successfully at: {target}")


def generate_order_number():
    """Generate a unique human-readable order number like NX-849201."""
    digits = "".join(random.choices(string.digits, k=6))
    return f"NX-{digits}"


def save_order(customer_name, customer_email, plan_name, amount,
               customer_phone=None, company_name=None, billing_cycle="Monthly",
               payment_method="Credit Card", notes=None, status="completed"):
    """
    Insert a customer purchase/order record into the database.
    Returns the newly created order record as a dict.
    """
    _ensure_initialized()
    order_number = generate_order_number()
    conn = get_connection()
    cursor = conn.cursor()

    params = (
        order_number, customer_name, customer_email, customer_phone,
        company_name, plan_name, billing_cycle, float(amount),
        payment_method, status, notes,
    )

    if is_postgres():
        cursor.execute("""
            INSERT INTO orders (
                order_number, customer_name, customer_email, customer_phone,
                company_name, plan_name, billing_cycle, amount,
                currency, payment_method, status, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'USD', %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING *
        """, params)
        columns = [desc[0] for desc in cursor.description]
        order_data = _serialize_row(columns, cursor.fetchone())
        conn.commit()
    else:
        cursor.execute("""
            INSERT INTO orders (
                order_number, customer_name, customer_email, customer_phone,
                company_name, plan_name, billing_cycle, amount,
                currency, payment_method, status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, datetime('now'))
        """, params)
        new_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (new_id,))
        row = cursor.fetchone()
        order_data = dict(row) if row else None

    conn.close()
    return order_data


def get_all_orders(limit=200):
    """Retrieve all customer orders ordered by most recent."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_format_sql("SELECT * FROM orders ORDER BY id DESC LIMIT ?"), (limit,))
    orders = _fetch_all_dicts(cursor)
    conn.close()
    return orders


def save_contact(name, email, subject, message):
    """Save a contact inquiry message into the database."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            INSERT INTO contacts (name, email, subject, message, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (name, email, subject, message))
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute("""
            INSERT INTO contacts (name, email, subject, message, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (name, email, subject, message))
        new_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return new_id


def get_all_contacts(limit=200):
    """Retrieve all contact inquiries."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_format_sql("SELECT * FROM contacts ORDER BY id DESC LIMIT ?"), (limit,))
    contacts = _fetch_all_dicts(cursor)
    conn.close()
    return contacts


def get_stats():
    """Retrieve aggregated stats for admin dashboard."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM orders")
    total_orders, total_revenue = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = cursor.fetchone()[0]

    cursor.execute("SELECT plan_name, COUNT(*) as cnt FROM orders GROUP BY plan_name")
    plan_distribution = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()
    return {
        "total_orders": int(total_orders or 0),
        "total_revenue": round(float(total_revenue or 0), 2),
        "total_contacts": int(total_contacts or 0),
        "plan_distribution": plan_distribution,
    }


def delete_order(order_id):
    """Delete a specific order by its database ID."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_format_sql("DELETE FROM orders WHERE id = ?"), (order_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def delete_contact(contact_id):
    """Delete a specific contact message by its database ID."""
    _ensure_initialized()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_format_sql("DELETE FROM contacts WHERE id = ?"), (contact_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


if __name__ == "__main__":
    init_db()
    orders = get_all_orders(limit=1)
    if not orders:
        print("Inserting sample purchase record...")
        sample = save_order(
            customer_name="Rahim Ahmed",
            customer_email="rahim@example.com",
            customer_phone="+8801712345678",
            company_name="Tech Solutions BD",
            plan_name="Professional",
            billing_cycle="Monthly",
            amount=79.0,
            payment_method="Credit Card",
            notes="Initial trial purchase",
        )
        print("Sample order created:", sample)
