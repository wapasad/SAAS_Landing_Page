"""
manage_database.py - Command-line utility to view and delete records from SQLite database.
"""

import sys
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nexus.db')

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def view_all():
    conn = get_conn()
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("CUSTOMER ORDERS (orders table):")
    print("=" * 60)
    cursor.execute("SELECT id, order_number, customer_name, customer_email, plan_name, amount, created_at FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    if not orders:
        print("  (No orders found)")
    else:
        for o in orders:
            print(f"  [ID: {o['id']}] {o['order_number']} | {o['customer_name']} ({o['customer_email']}) | {o['plan_name']} | ${o['amount']} | {o['created_at']}")

    print("\n" + "=" * 60)
    print("CONTACT MESSAGES (contacts table):")
    print("=" * 60)
    cursor.execute("SELECT id, name, email, subject, created_at FROM contacts ORDER BY id DESC")
    contacts = cursor.fetchall()
    if not contacts:
        print("  (No contacts found)")
    else:
        for c in contacts:
            print(f"  [ID: {c['id']}] {c['name']} ({c['email']}) | {c['subject']} | {c['created_at']}")
    print()
    conn.close()

def delete_order_cli(order_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    if cursor.rowcount > 0:
        conn.commit()
        print(f">> Successfully deleted order with ID: {order_id}")
    else:
        print(f">> No order found with ID: {order_id}")
    conn.close()

def delete_contact_cli(contact_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    if cursor.rowcount > 0:
        conn.commit()
        print(f">> Successfully deleted contact message with ID: {contact_id}")
    else:
        print(f">> No contact message found with ID: {contact_id}")
    conn.close()

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == 'view':
        view_all()
    elif args[0] == 'delete-order' and len(args) > 1:
        delete_order_cli(int(args[1]))
    elif args[0] == 'delete-contact' and len(args) > 1:
        delete_contact_cli(int(args[1]))
    else:
        print("Usage:")
        print("  python manage_database.py view                 (View all records)")
        print("  python manage_database.py delete-order <id>    (Delete order by ID)")
        print("  python manage_database.py delete-contact <id>  (Delete contact by ID)")
