"""
database.py - Database setup and management for Nexus SaaS Platform.
Uses SQLite for robust, portable, zero-configuration data storage.
"""

import sqlite3
import os
import random
import string
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nexus.db')

def get_connection():
    """Establish and return a connection to the SQLite database with dictionary rows."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the necessary database tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table: orders (Customer product purchase details)
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

    # Table: contacts (Inquiries / Leads from the contact form)
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

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at: {DB_FILE}")

def generate_order_number():
    """Generate a unique human-readable order number like NX-849201."""
    digits = ''.join(random.choices(string.digits, k=6))
    return f"NX-{digits}"

def save_order(customer_name, customer_email, plan_name, amount, 
               customer_phone=None, company_name=None, billing_cycle="Monthly", 
               payment_method="Credit Card", notes=None, status="completed"):
    """
    Insert a customer purchase/order record into the database.
    Returns the newly created order record as a dict.
    """
    order_number = generate_order_number()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders (
            order_number, customer_name, customer_email, customer_phone,
            company_name, plan_name, billing_cycle, amount,
            currency, payment_method, status, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, datetime('now'))
    """, (
        order_number, customer_name, customer_email, customer_phone,
        company_name, plan_name, billing_cycle, float(amount),
        payment_method, status, notes
    ))

    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (new_id,))
    row = cursor.fetchone()
    order_data = dict(row) if row else None
    conn.close()

    return order_data

def get_all_orders(limit=200):
    """Retrieve all customer orders ordered by most recent."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    orders = [dict(row) for row in rows]
    conn.close()
    return orders

def save_contact(name, email, subject, message):
    """Save a contact inquiry message into the database."""
    conn = get_connection()
    cursor = conn.cursor()
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
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    contacts = [dict(row) for row in rows]
    conn.close()
    return contacts

def get_stats():
    """Retrieve aggregated stats for admin dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM orders")
    total_orders, total_revenue = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = cursor.fetchone()[0]

    cursor.execute("SELECT plan_name, COUNT(*) as cnt FROM orders GROUP BY plan_name")
    plan_distribution = {row['plan_name']: row['cnt'] for row in cursor.fetchall()}

    conn.close()
    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "total_contacts": total_contacts,
        "plan_distribution": plan_distribution
    }

def delete_order(order_id):
    """Delete a specific order by its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def delete_contact(contact_id):
    """Delete a specific contact message by its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

if __name__ == "__main__":
    init_db()
    # Add a sample order if empty
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
            notes="Initial trial purchase"
        )
        print("Sample order created:", sample)
