from flask import Blueprint, request, jsonify
from datetime import datetime
from flask_jwt_extended import (jwt_required, get_jwt_identity)
import routes
from utils.db import mongo
from services.pascabayar_service import calculate_pascabayar
import cv2
import numpy as np
from services.ocr_service import scan_meter_image
from routes.auth_routes import log_user_activity

pascabayar_bp = Blueprint(
    "pascabayar",
    __name__,
    url_prefix="/api/pascabayar"
)

# ==========================================================
# INPUT / UPDATE METER
# ==========================================================
@pascabayar_bp.route("/input-meter-awal", methods=["POST"])
@jwt_required()
def input_meter_awal():

    user_id = get_jwt_identity()
    data = request.json

    current_meter = float(data["current_meter"])
    power = int(data.get("power", 1300))
    budget = int(data.get("budget", 0))

    now = datetime.now()

    # Cek apakah bulan ini sudah ada meter awal
    first_scan = mongo.db.meter_predictions.find_one(
        {
            "user_id": user_id,
            "bulan": now.month,
            "tahun": now.year,
            "is_first": True
        }
    )

    if first_scan:

        return jsonify({
            "status": "error",
            "message": "Meter awal bulan ini sudah pernah diinput."
        }),400

    data_meter = {

        "user_id": user_id,

        "bulan": now.month,
        "tahun": now.year,

        "is_first": True,

        "previous_meter": current_meter,
        "current_meter": current_meter,

        "daily_usage": 0,
        "daily_cost": 0,

        "avg_daily_usage": 0,

        "kwh_terpakai": 0,

        "tagihan_berjalan": 0,

        "estimasi_kwh": 0,

        "estimasi_tagihan": 0,

        "hari_ke": now.day,

        "progress": 0,

        "status": "BELUM ADA PEMAKAIAN",

        "grafik_hari": [],
        "grafik_kwh": [],

        "power": power,

        "budget": budget,

        "sumber": "manual",

        "created_at": now

    }

    mongo.db.meter_predictions.insert_one(data_meter)
    
    # LOG
    log_user_activity(
        str(user_id),
        "Input Meter Awal",
        f"User menginput meter awal: {current_meter} kWh, budget Rp{budget:,}."
    )
    
    return jsonify({
        "status":"success",
        "message":"Meter awal berhasil disimpan.",
        "data":data_meter
    })

    mongo.db.pasca_history.insert_one({
        "user_id": user_id,
        "meter": current_meter,
        "daily_usage": 0,
        "estimasi_tagihan": 0,
        "sumber": "manual",
        "is_first": True,
        "created_at": now
    })

@pascabayar_bp.route("/input-meter-update", methods=["POST"])
@jwt_required()
def input_meter_update():

    user_id = get_jwt_identity()

    data = request.json

    current_meter = float(data["current_meter"])

    # power = int(data.get("power",1300))

    # budget = int(data.get("budget",0))

    now = datetime.now()

    # ======================================
    # CEK SUDAH INPUT HARI INI BELUM
    # ======================================

    today = now.date()

    already_input = mongo.db.meter_predictions.find_one(
        {
            "user_id": user_id,
            "is_first": False,
            "bulan": now.month,
            "tahun": now.year,
        },
        sort=[("created_at", -1)]
    )

    if already_input:

        last_date = already_input["created_at"]

        if isinstance(last_date, str):
            last_date = datetime.fromisoformat(last_date)

        if last_date.date() == today:

            return jsonify({

                "status":"error",

                "message":"Hari ini Anda sudah melakukan update meter."

            }),400

    all_readings = list(

        mongo.db.meter_predictions.find(

            {

                "user_id":user_id,

                "bulan":now.month,

                "tahun":now.year

            }

        ).sort("created_at",1)

    )

    if len(all_readings)==0:

        return jsonify({

            "status":"error",

            "message":"Silakan input Meter Awal terlebih dahulu."

        }),400
    
    # ==========================
    # VALIDASI ANGKA METER
    # ==========================

    previous_meter = all_readings[-1]["current_meter"]

    if current_meter <= previous_meter:

        return jsonify({
            "status": "error",
            "message": "Angka meter harus lebih besar dari meter sebelumnya."
        }), 400

    # ==========================
    # AMBIL DAYA DAN BUDGET DARI METER AWAL
    # ==========================

    meter_awal = mongo.db.meter_predictions.find_one({

        "user_id": user_id,

        "bulan": now.month,

        "tahun": now.year,

        "is_first": True

    })

    power = meter_awal["power"]

    budget = meter_awal["budget"]


    hasil = calculate_pascabayar(

        current_meter=current_meter,

        power=power,

        monthly_budget=budget,

        readings=all_readings

    )

    hasil.update({

        "user_id": user_id,

        "bulan": now.month,

        "tahun": now.year,

        "is_first": False,

        "sumber": "manual",

        "created_at": now

    })

    mongo.db.meter_predictions.insert_one(hasil)
    
    # LOG
    log_user_activity(
        str(user_id),
        "Update Meter Pascabayar",
        f"User update meter: {current_meter} kWh, estimasi tagihan Rp{hasil['estimasi_tagihan']:,}."
    )

    return jsonify({
        "status":"success",
        "message":"Data meter berhasil diperbarui.",
        "data":hasil
    })

    mongo.db.pasca_history.insert_one({
        "user_id": user_id,
        "meter": current_meter,
        "daily_usage": hasil["daily_usage"],
        "estimasi_tagihan": hasil["estimasi_tagihan"],
        "sumber": "manual",
        "is_first": False,
        "created_at": now
    })

    return jsonify({

        "status":"success",

        "message":"Data meter berhasil diperbarui.",

        "data":hasil

    })

# ==========================================================
# PREVIEW TAGIHAN
# ==========================================================
@pascabayar_bp.route("/preview-tagihan", methods=["POST"])
@jwt_required()
def preview_tagihan():

    user_id = get_jwt_identity()
    data = request.json

    current_meter = float(data["current_meter"])
    now = datetime.now()

    meter_awal = mongo.db.meter_predictions.find_one({
        "user_id": user_id,
        "bulan": now.month,
        "tahun": now.year,
        "is_first": True
    })

    if not meter_awal:
        return jsonify({
            "status": "error",
            "message": "Meter awal belum diinput."
        }), 400

    readings = list(
        mongo.db.meter_predictions.find({
            "user_id": user_id,
            "bulan": now.month,
            "tahun": now.year
        }).sort("created_at", 1)
    )

    hasil = calculate_pascabayar(
        current_meter=current_meter,
        power=meter_awal["power"],
        monthly_budget=meter_awal["budget"],
        readings=readings
    )

    return jsonify({
        "status": "success",
        "estimasi": hasil["estimasi_tagihan"]
    })


# ==========================================================
# SCAN METER IMAGE
# ==========================================================
@pascabayar_bp.route("/scan", methods=["POST"])
@jwt_required()
def scan_meter():

    user_id = get_jwt_identity()

    if "image" not in request.files:
        return jsonify({
            "status": "error",
            "message": "File gambar tidak ditemukan."
        }), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "File kosong."
        }), 400

    try:

        image_bytes = file.read()

        image = cv2.imdecode(
            np.frombuffer(image_bytes, np.uint8),
            cv2.IMREAD_COLOR
        )

        # current_meter = scan_meter_image(image)
        current_meter = scan_meter_image(image, has_decimal=False)

        if current_meter is None:
            return jsonify({
                "status": "error",
                "message": "Meter gagal dibaca."
            }), 400

        power = int(request.form.get("power", 1300))
        budget = int(request.form.get("budget", 0))

        now = datetime.now()

        readings = list(
            mongo.db.meter_predictions.find({
                "user_id": user_id,
                "bulan": now.month,
                "tahun": now.year
            }).sort("created_at", 1)
        )

        if len(readings) == 0:
            return jsonify({
                "status": "error",
                "message": "Silakan input meter awal terlebih dahulu."
            }), 400

        hasil = calculate_pascabayar(
            current_meter=current_meter,
            power=power,
            monthly_budget=budget,
            readings=readings
        )

        hasil.update({
            "user_id": user_id,
            "bulan": now.month,
            "tahun": now.year,
            "is_first": False,
            "power": power,
            "budget": budget,
            "sumber": "manual",
            "created_at": now
        })

        mongo.db.meter_predictions.insert_one(hasil)
        
        log_user_activity(
            str(user_id),
            "Scan Meter Pascabayar",
            f"User scan meter: {current_meter} kWh terdeteksi, estimasi tagihan Rp{hasil['estimasi_tagihan']:,}."
        )

        return jsonify({
            "status": "success",
            "data": hasil
        })

        mongo.db.pasca_history.insert_one({
            "user_id": user_id,
            "meter": current_meter,
            "daily_usage": hasil["daily_usage"],
            "estimasi_tagihan": hasil["estimasi_tagihan"],
            "sumber": "scan",
            "is_first": False,
            "created_at": now
        })

        return jsonify({
            "status": "success",
            "data": hasil
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@pascabayar_bp.route("/history", methods=["GET"])
@jwt_required()
def history():
    user_id = get_jwt_identity()

    history = list(
        mongo.db.meter_predictions.find(
            {"user_id": user_id}
        ).sort("created_at", -1)
    )

    result = []
    for item in history:
        result.append({
            "tanggal":          item["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "current_meter":    item.get("current_meter", 0),
            "previous_meter":   item.get("previous_meter", 0),
            "daily_usage":      item.get("daily_usage", 0),
            "daily_cost":       item.get("daily_cost", 0),
            "estimasi_tagihan": item.get("estimasi_tagihan", 0),
            "estimasi_kwh":     item.get("estimasi_kwh", 0),
            "tagihan_berjalan": item.get("tagihan_berjalan", 0),
            "progress":         item.get("progress", 0),
            "sisa_hari":        item.get("sisa_hari", 0),
            "budget":           item.get("budget", 0),
            "status":           item.get("status", ""),
            # jenis untuk filter chip di Flutter
            "jenis":  "tagihan" if item.get("is_first") else "prediksi",
            "sumber": "manual",
            # nominal dipetakan ke estimasi_tagihan supaya subtitle di card muncul
            "nominal": item.get("estimasi_tagihan", 0),
        })

    return jsonify({
        "status": "success",
        "data": result
    })
# ==========================================================
# DASHBOARD
# ==========================================================
@pascabayar_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():

    user_id = get_jwt_identity()

    terakhir = mongo.db.meter_predictions.find_one(

        {
            "user_id": user_id
        },

        sort=[("created_at", -1)]

    )

    if terakhir is None:

        return jsonify({

            "status": "success",

            "estimasi_tagihan": 0,

            "persen_perubahan": 0,

            "daily_usage": 0,

            "daily_cost": 0,

            "kwh_berjalan": 0,

            "tagihan_berjalan": 0,

            "hari_ke": 0,

            "budget": 0,

            "power":0,

            "progress": 0,

            "status_budget": "BELUM ADA DATA",

            "last_update": "-",

            "hari": [],

            "kwh_data": [],

            "history_tagihan": []

        })

    # ==========================
    # Ambil 7 data terakhir
    # ==========================

    history = list(

        mongo.db.meter_predictions.find(

            {
                "user_id": user_id
            }

        ).sort("created_at", -1).limit(7)

    )

    history.reverse()

    # ==========================
    # Ambil data meter awal
    # ==========================

    meter_awal = mongo.db.meter_predictions.find_one(
        {
            "user_id": user_id,
            "is_first": True
        }
    )

    budget = meter_awal["budget"] if meter_awal else 0

    estimasi = terakhir["estimasi_tagihan"]

    sisa_budget = max(0, budget - estimasi)

    hari = []
    kwh_data = []
    history_tagihan = []

    for item in history:

        hari.append(

            item["created_at"].strftime("%d/%m")

        )

        kwh_data.append(

            item["daily_usage"]

        )

        history_tagihan.append({

            "tanggal": item["created_at"].strftime("%d/%m"),

            "tagihan": item["estimasi_tagihan"]

        })

    return jsonify({

        "status": "success",

        "estimasi_tagihan": estimasi,

        "persen_perubahan": 0,

        "daily_usage": terakhir["daily_usage"],

        "daily_cost": terakhir["daily_cost"],

        "kwh_berjalan": terakhir["kwh_terpakai"],

        "tagihan_berjalan": terakhir["tagihan_berjalan"],

        "hari_ke": terakhir["hari_ke"],

        "budget": budget,

        "sisa_budget": sisa_budget,

        "power": meter_awal["power"] if meter_awal else 0,

        "progress": terakhir["progress"],

        "status_budget": terakhir["status"],

        "last_update": terakhir["created_at"].strftime("%d %b %Y, %H:%M"),

        "hari": hari,

        "kwh_data": kwh_data,

        "history_tagihan": history_tagihan

    })