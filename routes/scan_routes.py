from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import numpy as np
import cv2
from datetime import datetime
from utils.db import mongo
from services.ocr_service import scan_meter_image
from services.pascabayar_service import calculate_pascabayar
from services.prabayar_service import calculate_prabayar
from utils.ocr_reader import reader
from routes.auth_routes import log_user_activity

scan_bp = Blueprint("scan_bp", __name__)

# =====================================================
# SAFE PARSER
# =====================================================
def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

@scan_bp.route("/prabayar/scan", methods=["POST"])
@jwt_required()
def scan_prabayar():
    try:
        user_id      = get_jwt_identity()
        file         = request.files.get("image")
        
        print("===== SCAN PRABAYAR =====")

        # =====================================================
        # AMBIL FORM DATA — definisikan SEMUA variabel dulu
        # =====================================================
        power        = safe_int(request.form.get("power"))
        meter_number = request.form.get("meter_number", "")
        
        print(f"Power: {power}")               # DEBUG
        print(f"Meter Number: {meter_number}")

        # Kalau power tidak dikirim atau 0, ambil dari riwayat
        if power <= 0:
            last_record = mongo.db.scan_history.find_one(
                {"user_id": user_id},
                sort=[("created_at", -1)]
            )
            power = last_record.get("power", 1300) if last_record else 1300

        # Kalau meter_number kosong, ambil dari riwayat
        if not meter_number or meter_number == "prabayar_user":
            last_record = mongo.db.scan_history.find_one(
                {"user_id": user_id},
                sort=[("created_at", -1)]
            )
            meter_number = last_record.get("meter_number", "UNKNOWN") \
                if last_record else "UNKNOWN"

        # =====================================================
        # VALIDASI IMAGE
        # =====================================================
        if not file:
            print("ERROR: File image tidak ditemukan") 
            return jsonify({
                "status":  "error",
                "message": "Image tidak ditemukan"
            }), 400
            
            print(f"Nama File: {file.filename}") 

        # Decode image
        file_bytes = np.frombuffer(file.read(), np.uint8)
        image      = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None:
            print("ERROR: Gagal decode image")
            return jsonify({
                "status":  "error",
                "message": "Gagal decode image"
            }), 400
            
        print(f"Ukuran Image: {image.shape}")

        # =====================================================
        # OCR
        # =====================================================
        remaining_kwh = scan_meter_image(image)
        print(f"Hasil OCR: {remaining_kwh}")
        if remaining_kwh is None:
            print("ERROR: OCR mengembalikan None")
            return jsonify({
                "status":  "error",
                "message": "OCR gagal membaca meter. Pastikan foto jelas dan terang."
            }), 400
            

        # =====================================================
        # HITUNG PREDIKSI
        # =====================================================
        last_scan = mongo.db.scan_history.find_one(
            {"user_id": user_id, "type": "prabayar"},
            sort=[("created_at", -1)]
        )

        result = calculate_prabayar(
            remaining_kwh=remaining_kwh,
            power=power,
            last_scan=last_scan
        )

        # =====================================================
        # SIMPAN KE SCAN HISTORY
        # =====================================================
        mongo.db.scan_history.insert_one({
            "user_id":        user_id,
            "type":           "prabayar",
            "meter_number":   meter_number,
            "remaining_kwh":  remaining_kwh,
            "power":          power,
            "daily_usage":    result["daily_usage"],
            "days_remaining": result["days_remaining"],
            "status":         result["status"],
            "input_type":     "scan",
            "created_at":     datetime.now()
        })
        
        # =====================================================
        # LOG AKTIVITAS
        # =====================================================
        log_user_activity(
            str(user_id),
            "Scan Token Meteran",
            f"User melakukan scan LCD meteran, sisa {remaining_kwh} kWh terdeteksi."
        )

        # =====================================================
        # SIMPAN NOTIFIKASI
        # =====================================================
        status_kwh = result.get("status", "AMAN")
        days_rem   = result.get("days_remaining", 0)

        if status_kwh == "SEGERA BELI TOKEN":
            notif_title = "⚠️ Sisa kWh Kritis!"
            notif_icon  = "warning"
            notif_color = 0xFFF44336
        elif status_kwh == "PERLU PERHATIAN":
            notif_title = "🔔 Perlu Perhatian"
            notif_icon  = "info"
            notif_color = 0xFFFF9800
        else:
            notif_title = "✅ Scan Meteran Berhasil"
            notif_icon  = "check"
            notif_color = 0xFF4CAF50

        mongo.db.notifications.insert_one({
            "user_id":    user_id,
            "type":       "prabayar",
            "title":      notif_title,
            "desc":       f"Sisa {remaining_kwh} kWh. Estimasi habis dalam {days_rem} hari ({status_kwh}).",
            "time":       "Baru saja",
            "icon":       notif_icon,
            "color":      notif_color,
            "created_at": datetime.now()
        })

        return jsonify({
            "status":        "success",
            "meter_number":  meter_number,
            "remaining_kwh": remaining_kwh,
            "result":        result
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================
# RIWAYAT SCAN
# =====================================================
@scan_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    try:
        user_id  = get_jwt_identity()
        scan_type = request.args.get("type")  # prabayar / pascabayar

        query = {"user_id": user_id}
        if scan_type:
            query["type"] = scan_type

        history = list(
            mongo.db.scan_history
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .limit(30)
        )

        # Convert datetime ke string
        for item in history:
            if "created_at" in item:
                item["created_at"] = item["created_at"].strftime("%Y-%m-%d %H:%M")

        return jsonify({"status": "success", "data": history})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500