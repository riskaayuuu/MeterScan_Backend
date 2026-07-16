from flask import Blueprint, render_template, request, redirect, url_for, session
from utils.db import mongo
from collections import Counter
from datetime import datetime
from pymongo import MongoClient

bigdata_bp = Blueprint("bigdata", __name__)

scraping_client = MongoClient(
    "mongodb+srv://dindadestriyani939:dinda54321@cluster0.hw6y1fq.mongodb.net/?appName=Cluster0",
    serverSelectionTimeoutMS=5000
)
try:
    scraping_client.server_info()
    print("✅ Berhasil konek ke MongoDB Atlas")
except Exception as e:
    print("❌ Gagal konek:", e)

scraping_db = scraping_client["meterscan_db"]
scraping_collection = scraping_db["electricity_trends"]

print("="*50)
print("DATABASE :", scraping_db.name)
print("COLLECTION :", scraping_collection.name)
# print("JUMLAH :", scraping_collection.count_documents({}))

for x in scraping_collection.find().limit(3):
    print(x)

print("="*50)

@bigdata_bp.route("/test-smtp")
def test_smtp():
    import socket
    try:
        s = socket.create_connection(("smtp.gmail.com", 587), timeout=5)
        s.close()
        return {"status": "SMTP BISA DIAKSES"}
    except Exception as e:
        return {"status": "SMTP DIBLOKIR / GAGAL", "error": str(e)}

@bigdata_bp.route("/", methods=["GET"])
def home():
    return render_template("login.html")

@bigdata_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username")
    password = request.form.get("password")

    if username == "admin" and password == "admin123":
        session["admin"] = username
        return redirect(url_for("bigdata.dashboard"))

    return render_template(
        "login.html",
        error="Username atau Password salah!"
    )


@bigdata_bp.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("bigdata.home"))

@bigdata_bp.route("/dashboard")
def dashboard():
    
    if "admin" not in session:
        return redirect(url_for("bigdata.home"))

    # ===========================================
    # CARD INTERNAL
    # ===========================================

    total_user = mongo.db.users.count_documents({})

    total_scan = mongo.db.scan_history.count_documents({})

    total_manual = mongo.db.token_history.count_documents({})

    total_meter = mongo.db.meter_predictions.count_documents({})

    total_prabayar = total_scan + total_manual

    total_pascabayar = total_meter

    total_activity = total_prabayar + total_pascabayar

    # ===========================================
    # GRAFIK 1
    # Scan OCR vs Input Manual
    # ===========================================

    prabayar_scan = total_scan

    pascabayar_scan = 0

    prabayar_manual = total_manual

    pascabayar_manual = total_meter

    # ===========================================
    # GRAFIK 2
    # Tren Aktivitas Harian
    # ===========================================

    prabayar_counter = Counter()
    pascabayar_counter = Counter()

    # -------------------------
    # Data Prabayar
    # -------------------------
    for item in mongo.db.scan_history.find():

        if item.get("created_at"):
            tanggal = item["created_at"].strftime("%Y-%m-%d")
            prabayar_counter[tanggal] += 1

    # -------------------------
    # Data Pascabayar
    # -------------------------
    for item in mongo.db.meter_predictions.find():

        if item.get("created_at"):
            tanggal = item["created_at"].strftime("%Y-%m-%d")
            pascabayar_counter[tanggal] += 1

    # -------------------------
    # Gabungkan semua tanggal
    # -------------------------
    activity_labels = sorted(
        set(list(prabayar_counter.keys()) + list(pascabayar_counter.keys()))
    )

    prabayar_activity = [
        prabayar_counter.get(tanggal, 0)
        for tanggal in activity_labels
    ]

    pascabayar_activity = [
        pascabayar_counter.get(tanggal, 0)
        for tanggal in activity_labels
    ]

    # ===========================================
    # GRAFIK 3
    # Nominal Input Token
    # ===========================================

    nominal_counter = {}

    tokens = mongo.db.token_history.find()

    for token in tokens:

        tanggal = str(token.get("created_at"))[:10]

        nominal = float(token.get("nominal",0))

        nominal_counter[tanggal] = nominal_counter.get(tanggal,0)+nominal

    nominal_labels = list(nominal_counter.keys())

    nominal_values = list(nominal_counter.values())

    # ===========================================
    # DATA EXTERNAL
    # ===========================================

    print(scraping_client.list_database_names())
    print(scraping_db.list_collection_names())
    print(scraping_collection.count_documents({}))

    news = list(
        scraping_collection.find()
    )

    print("=" * 50)
    print("TOTAL NEWS :", len(news))

    if len(news) > 0:
        print(news[0])

    print("=" * 50)

    total_article = len(news)

    media_counter = Counter()
    category_counter = Counter()
    trend_counter = Counter()

    for item in news:

        media = item.get("sumber_media", "Unknown")
        media_counter[media] += 1

        kategori = item.get("kategori_listrik", "Lainnya")
        category_counter[kategori] += 1

        tanggal = str(item.get("tanggal_terbit", ""))[:11]
        trend_counter[tanggal] += 1

    total_media = len(media_counter)

    berita_prabayar = category_counter.get(
        "Prabayar",
        0
    )

    berita_pascabayar = category_counter.get(
        "Pascabayar",
        0
    )
    category_labels = list(category_counter.keys())

    category_values = list(category_counter.values())

    media_labels = list(media_counter.keys())

    media_values = list(media_counter.values())

    trend_labels = sorted(trend_counter.keys())

    trend_values = [
        trend_counter[t]
        for t in trend_labels
    ]

    latest_news = []
    for item in news[:10]:
        latest_news.append({
            "title": item.get("judul_berita", "-"),
            "date": item.get("tanggal_terbit", "-"),
            "source": item.get("sumber_media", "-"),
            "category": item.get("kategori_listrik", "Umum"),
            "url": item.get("url_sumber", "#") # Sesuaikan field dengan JSON
        })

    return render_template(

        "dashboard.html",

        # CARD
        total_user=total_user,
        total_prabayar=total_prabayar,
        total_pascabayar=total_pascabayar,
        total_activity=total_activity,

        # CHART INTERNAL
        prabayar_scan=prabayar_scan,
        pascabayar_scan=pascabayar_scan,
        prabayar_manual=prabayar_manual,
        pascabayar_manual=pascabayar_manual,

        activity_labels=activity_labels,
        prabayar_activity=prabayar_activity,
        pascabayar_activity=pascabayar_activity,

        nominal_labels=nominal_labels,
        nominal_values=nominal_values,

        # EXTERNAL
        total_article=total_article,
        total_media=total_media,
        berita_prabayar=berita_prabayar,
        berita_pascabayar=berita_pascabayar,

        category_labels=category_labels,
        category_values=category_values,

        media_labels=media_labels,
        media_values=media_values,

        trend_labels=trend_labels,
        trend_values=trend_values,

        latest_news=latest_news

    )

@bigdata_bp.route("/monitoring")
def monitoring():
    # Ambil semua data histori scan, urutkan dari yang paling baru (created_at: -1)
    scans_data = mongo.db.scan_history.find().sort("created_at", -1)
    
    # Konversi ke list agar bisa di-looping di HTML
    scans_list = list(scans_data)
    
    return render_template("monitoring.html", scans=scans_list)

@bigdata_bp.route("/analytics")
def analytics():
    # 1. Ambil semua data token untuk dianalisis
    tokens = list(mongo.db.token_history.find({}))
    
    total_nominal = 0
    max_nominal = 0
    count = len(tokens)
    
    # Hitung total pembelian, rata-rata, dan pembelian tertinggi
    for t in tokens:
        try:
            nominal = float(t.get("nominal", 0))
            total_nominal += nominal
            if nominal > max_nominal:
                max_nominal = nominal
        except:
            continue
            
    avg_nominal = total_nominal / count if count > 0 else 0

    # 2. Ambil log aktivitas terbaru untuk melihat keaktifan user
    recent_activities = list(mongo.db.activity_logs.find().sort("created_at", -1).limit(5))

    return render_template(
        "analytics.html",
        total_nominal=total_nominal,
        avg_nominal=avg_nominal,
        max_nominal=max_nominal,
        recent_activities=recent_activities
    )

@bigdata_bp.route("/scheduler")
def scheduler():
    # Ambil status sinkronisasi terakhir dari database
    status_sync = mongo.db.dashboard_summary.find_one({"type": "sync_status"})
    
    if status_sync:
        last_run = status_sync.get("last_run", "Belum pernah")
        status = "Aktif (Berjalan Otomatis)"
    else:
        last_run = "Belum pernah"
        status = "Belum Terkoneksi (Menunggu Jadwal)"

    return render_template("scheduler.html", last_run=last_run, status=status)

@bigdata_bp.route("/reports")
def reports():
    # Ambil data agregasi berkala yang dibuat oleh scheduler tadi
    try:
        sync_status = mongo.db.dashboard_summary.find_one({"type": "sync_status"})
        last_sync = sync_status.get("last_run", "Belum tersinkronisasi") if sync_status else "Belum tersinkronisasi"
    except:
        last_sync = "Belum tersinkronisasi"

    # Ambil beberapa sampel data summary/log untuk kebutuhan preview laporan
    total_users = mongo.db.users.count_documents({}) or 0
    total_scans = mongo.db.scan_history.count_documents({}) or 0
    total_tokens = mongo.db.token_history.count_documents({}) or 0

    return render_template(
        "reports.html", 
        last_sync=last_sync,
        total_users=total_users,
        total_scans=total_scans,
        total_tokens=total_tokens
    )
