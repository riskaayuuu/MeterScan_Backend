from flask import Blueprint
from flask import render_template

from utils.db import mongo

# =========================
# BLUEPRINT
# =========================

admin_bp = Blueprint(
    'admin',
    __name__
)

# =========================
# LOGIN PAGE
# =========================

@admin_bp.route('/')
def login_page():

    return render_template(
        'login.html'
    )

# =========================
# REGISTER PAGE
# =========================

@admin_bp.route('/register')
def register_page():

    return render_template(
        'register.html'
    )

# =========================
# DASHBOARD
# =========================

@admin_bp.route('/dashboard')
def dashboard_page():

    total_user = mongo.db.users.count_documents({})

    total_scan = mongo.db.scans.count_documents({})

    total_prabayar = mongo.db.scans.count_documents({
        'payment_type':'prabayar'
    })

    total_pascabayar = mongo.db.scans.count_documents({
        'payment_type':'pascabayar'
    })

    return render_template(

        'dashboard.html',

        total_user=total_user,

        total_scan=total_scan,

        total_prabayar=total_prabayar,

        total_pascabayar=total_pascabayar
    )

# =========================
# HISTORY
# =========================

@admin_bp.route('/history')
def history_page():

    data = mongo.db.scans.find()

    return render_template(

        'history.html',

        data=data
    )

# =========================
# CHART
# =========================

@admin_bp.route('/chart')
def chart_page():

    data = mongo.db.scans.find()

    labels = []
    usage_data = []

    nomor = 1

    for item in data:

        labels.append(
            f'Scan {nomor}'
        )

        usage_data.append(
            item.get('usage',0)
        )

        nomor += 1

    return render_template(

        'chart.html',

        labels=labels,

        usage_data=usage_data
    )

# =========================
# SCAN PAGE
# =========================

@admin_bp.route('/scan')
def scan_page():

    return render_template(
        'scan.html'
    )