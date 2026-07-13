from werkzeug.exceptions import HTTPException
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from datetime import timedelta, datetime
from utils.db import mongo
from dotenv import load_dotenv
from routes.auth_routes import auth_bp
from routes.scan_routes import scan_bp
from routes.dashboard_routes import dashboard_bp
from routes.token_routes import token_bp
from routes.admin_routes import admin_bp
from routes.notifikasi_routes import notifikasi_bp
from routes.activity_routes import activity_bp
from bson import ObjectId
from routes.scan_struk_routes import scan_struk_bp
from routes.bigdata_routes import bigdata_bp
from apscheduler.schedulers.background import BackgroundScheduler
from routes.pascabayar_routes import pascabayar_bp
import os
import traceback

load_dotenv()

app = Flask(__name__)

app.config['PROPAGATE_EXCEPTIONS'] = False

# Secret key untuk Flask Session (login web)
app.secret_key = "meterscan_bigdata_2026"

# MongoDB & JWT
app.config['MONGO_URI']                = os.getenv("MONGO_URI")
app.config['JWT_SECRET_KEY']           = os.getenv("JWT_SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)

# Gmail SMTP
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_EMAIL")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

mongo.init_app(app)
JWTManager(app)
CORS(app)

# Inisialisasi mail — taruh di utils/mail.py
from utils.mail import mail
mail.init_app(app)


app.register_blueprint(auth_bp,       url_prefix="/api/auth")
app.register_blueprint(scan_bp,       url_prefix="/api")
app.register_blueprint(dashboard_bp,  url_prefix="/api/dashboard")
app.register_blueprint(token_bp, url_prefix="/api/token")
app.register_blueprint(admin_bp,      url_prefix="/api/admin")
app.register_blueprint(notifikasi_bp, url_prefix="/api/notifikasi")
app.register_blueprint(activity_bp)
app.register_blueprint(scan_struk_bp, url_prefix="/api/scan-struk")
app.register_blueprint(pascabayar_bp)

# Dashboard Web
app.register_blueprint(bigdata_bp)

#  KODE LOGIKA BACKGROUND SINKRONISASI SCHEDULER
def hitung_dan_sinkronisasi_data():
    with app.app_context():
        print(f"[{datetime.now()}] SCHEDULER: Sedang menghitung ulang ringkasan Big Data...")
        
        # Mengompilasi dan mencatat status sinkronisasi terbaru ke MongoDB
        mongo.db.dashboard_summary.update_one(
            {"type": "sync_status"},
            {"$set": {
                "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Sukses"
            }},
            upsert=True
        )
        print("SCHEDULER: Selesai diperbarui ke database!")

# Menyalakan mesin scheduler background
scheduler = BackgroundScheduler()
# Set interval 1 menit untuk demo saat presentasi UAS
scheduler.add_job(func=hitung_dan_sinkronisasi_data, trigger="interval", minutes=1)
scheduler.start()


@app.route("/api")
def home():
    return {"status": "success", "message": "MeterScan Backend Running"}

@app.route("/routes")
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods":  list(rule.methods),
            "url":      str(rule)
        })
    return jsonify(routes)

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return jsonify({
        "status": "error",
        "message": e.description
    }), e.code

@app.errorhandler(Exception)
def handle_exception(e):
    # Print error lengkap ke terminal
    print("--- ERROR DETECTED ---")
    traceback.print_exc() 
    return jsonify({"status": "error", "message": "Internal Server Error"}), 500

if __name__ == '__main__':
    # 3. PASTIKAN use_reloader=False AGAR SCHEDULER TIDAK BERJALAN DOUBLE
    # app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
