"""
app.py - Flask Server & REST API for Nexus SaaS Landing Page and Order Database.
"""

import os
import csv
import io
from flask import Flask, request, jsonify, send_file, render_template_string, Response, session
from database import (
    init_db, save_order, get_all_orders, delete_order,
    save_contact, get_all_contacts, delete_contact, get_stats
)

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'nexus_secure_admin_key_2026_xyz')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Admin credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
ADMIN_TOKEN = "nexus_admin_secure_token_key"

def is_admin_authenticated():
    """Verify if user is authenticated via session or Bearer token."""
    if session.get('admin_logged_in'):
        return True
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1]
        if token == ADMIN_TOKEN:
            return True
    return False

# Initialize database on startup
init_db()

@app.after_request
def add_cors_headers(response):
    """Enable CORS so frontend works whether opened via http://localhost:5000 or file://"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,DELETE,OPTIONS'
    return response

@app.route('/')
def home():
    """Serve the SaaS landing page."""
    html_path = os.path.join(BASE_DIR, 'index.html')
    return send_file(html_path)

@app.route('/admin')
def admin_page():
    """Serve the Admin Dashboard page."""
    admin_path = os.path.join(BASE_DIR, 'admin.html')
    if os.path.exists(admin_path):
        return send_file(admin_path)
    return "Admin page not found", 404

# ==========================================
# Authentication Endpoints
# ==========================================

@app.route('/api/admin/login', methods=['POST', 'OPTIONS'])
def admin_login():
    """Admin login endpoint."""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json(silent=True) or request.form.to_dict()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': ADMIN_TOKEN
        })
    return jsonify({
        'success': False,
        'error': 'User ID or Password didn\'t match.'
    }), 401

@app.route('/api/admin/logout', methods=['POST', 'OPTIONS'])
def admin_logout():
    """Admin logout endpoint."""
    if request.method == 'OPTIONS':
        return '', 204
    session.pop('admin_logged_in', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/admin/check', methods=['GET'])
def admin_check():
    """Check admin authentication status."""
    return jsonify({'authenticated': is_admin_authenticated()})

# ==========================================
# REST API Endpoints
# ==========================================

@app.route('/api/purchase', methods=['POST', 'OPTIONS'])
def handle_purchase():
    if request.method == 'OPTIONS':
        return '', 204
    """
    Handle customer product purchase / order placement.
    Expected JSON:
    {
        "name": "...",
        "email": "...",
        "phone": "...",
        "company": "...",
        "plan": "Starter" | "Professional" | "Enterprise",
        "billing_cycle": "Monthly" | "Yearly",
        "amount": 79.0,
        "payment_method": "Credit Card" | "PayPal" | "Demo",
        "notes": "..."
    }
    """
    data = request.get_json(silent=True) or request.form.to_dict()

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    plan = data.get('plan', 'Professional').strip()
    billing_cycle = data.get('billing_cycle', 'Monthly').strip()
    phone = data.get('phone', '').strip() or None
    company = data.get('company', '').strip() or None
    payment_method = data.get('payment_method', 'Credit Card').strip()
    notes = data.get('notes', '').strip() or None

    # Determine amount if not provided
    amount_raw = data.get('amount')
    if amount_raw is not None:
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            amount = 79.0
    else:
        # Default price matrix
        plan_prices = {
            'starter': {'monthly': 29.0, 'yearly': 23.0},
            'professional': {'monthly': 79.0, 'yearly': 63.0},
            'enterprise': {'monthly': 199.0, 'yearly': 159.0}
        }
        cycle_key = 'yearly' if 'year' in billing_cycle.lower() else 'monthly'
        amount = plan_prices.get(plan.lower(), {}).get(cycle_key, 79.0)

    # Basic validation
    if not name or not email:
        return jsonify({
            'success': False,
            'error': 'Customer name and email are required.'
        }), 400

    try:
        new_order = save_order(
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            company_name=company,
            plan_name=plan,
            billing_cycle=billing_cycle,
            amount=amount,
            payment_method=payment_method,
            notes=notes,
            status='completed'
        )

        return jsonify({
            'success': True,
            'message': 'Order processed and saved successfully!',
            'order': new_order
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders', methods=['GET'])
def list_orders():
    """Retrieve list of all customer orders from SQLite."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'error': 'Unauthorized. Authentication required.'}), 401
    limit = request.args.get('limit', default=100, type=int)
    orders = get_all_orders(limit=limit)
    return jsonify({
        'success': True,
        'count': len(orders),
        'orders': orders
    })

@app.route('/api/orders/<int:order_id>', methods=['DELETE', 'OPTIONS'])
def remove_order(order_id):
    """Delete a customer order by ID."""
    if request.method == 'OPTIONS':
        return '', 204
    if not is_admin_authenticated():
        return jsonify({'success': False, 'error': 'Unauthorized. Authentication required.'}), 401
    success = delete_order(order_id)
    if success:
        return jsonify({'success': True, 'message': f'Order #{order_id} deleted successfully.'})
    return jsonify({'success': False, 'error': 'Order not found.'}), 404

@app.route('/api/contact', methods=['POST', 'OPTIONS'])
def handle_contact():
    if request.method == 'OPTIONS':
        return '', 204
    """Handle contact message submission from landing page."""
    data = request.get_json(silent=True) or request.form.to_dict()

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    subject = data.get('subject', 'Website enquiry').strip()
    message = data.get('message', '').strip()

    if not name or not email or not message:
        return jsonify({
            'success': False,
            'error': 'Name, email, and message are required.'
        }), 400

    try:
        contact_id = save_contact(name, email, subject, message)
        return jsonify({
            'success': True,
            'message': 'Message received and saved to database.',
            'id': contact_id
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/contacts', methods=['GET'])
def list_contacts():
    """Retrieve list of contact inquiries."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'error': 'Unauthorized. Authentication required.'}), 401
    contacts = get_all_contacts()
    return jsonify({
        'success': True,
        'count': len(contacts),
        'contacts': contacts
    })

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE', 'OPTIONS'])
def remove_contact(contact_id):
    """Delete a contact message by ID."""
    if request.method == 'OPTIONS':
        return '', 204
    if not is_admin_authenticated():
        return jsonify({'success': False, 'error': 'Unauthorized. Authentication required.'}), 401
    success = delete_contact(contact_id)
    if success:
        return jsonify({'success': True, 'message': f'Contact #{contact_id} deleted successfully.'})
    return jsonify({'success': False, 'error': 'Contact not found.'}), 404

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Retrieve summary statistics."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'error': 'Unauthorized. Authentication required.'}), 401
    stats = get_stats()
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/api/export-orders-csv', methods=['GET'])
def export_orders_csv():
    """Export all orders to a downloadable CSV file."""
    if not is_admin_authenticated():
        return "Unauthorized. Authentication required.", 401
    orders = get_all_orders(limit=1000)
    if not orders:
        return "No orders to export", 404

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=orders[0].keys())
    writer.writeheader()
    for row in orders:
        writer.writerow(row)

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=nexus_orders.csv"}
    )

if __name__ == '__main__':
    print("=" * 60)
    print(">> Nexus SaaS Web Server & Database Running!")
    print(">> Landing Page: http://localhost:5000")
    print(">> Admin Orders Dashboard: http://localhost:5000/admin")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
