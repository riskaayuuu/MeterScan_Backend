# import app
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from flask_mail import Message
from utils import db
from utils.db import mongo
from utils.mail import mail
from utils.activity_logger import save_activity
import bcrypt
import random
import string
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt_identity
# from services.ocr_service import reader
from services.ocr_service import receipt_to_text
import pytz
import os
import requests

auth_bp = Blueprint('auth', __name__)
scan_struk_bp = Blueprint(
    'scan_struk',
    __name__
)


def log_user_activity(user_id, activity_name, description):
    try:
        wib = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(wib).strftime('%Y-%m-%d %H:%M:%S.%f')

        log_data = {
            "user_id":     str(user_id),
            "activity":    activity_name,
            "description": description,
            "created_at":  current_time
        }
        
        mongo.db.activity_logs.insert_one(log_data)
        print(f"Log sukses dibuat: {activity_name}")
    except Exception as e:
        print(f"Gagal mencatat log aktivitas: {e}")


# =====================================================
# HELPER — GENERATE OTP
# =====================================================
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


# =====================================================
# HELPER — KIRIM EMAIL OTP
# =====================================================
def send_otp_email(email, otp, name):
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "from": "MeterScan <onboarding@resend.dev>",
                "to": [email],
                "subject": "Kode Verifikasi MeterScan",
                "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto; 
                            padding: 32px; border-radius: 16px; border: 1px solid #e2e8f0;">
                    <div style="text-align: center; margin-bottom: 24px;">
                        <h2 style="color: #0F766E; margin: 0;">⚡ MeterScan</h2>
                    </div>
                    <p style="font-size: 16px; color: #334155;">Halo, <b>{name}</b>!</p>
                    <p style="color: #64748b;">Gunakan kode berikut untuk verifikasi akun MeterScan kamu:</p>
                    <div style="text-align: center; margin: 32px 0;">
                        <span style="font-size: 42px; font-weight: bold; letter-spacing: 12px; color: #0F766E;">
                            {otp}
                        </span>
                    </div>
                    <p style="color: #94a3b8; font-size: 13px; text-align: center;">
                        Kode berlaku selama <b>5 menit</b>.<br>Jangan bagikan kode ini kepada siapapun.
                    </p>
                </div>
                """
            },
            timeout=10
        )
        if response.status_code in (200, 201):
            return True
        else:
            print(f"Resend gagal: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error kirim email: {e}")
        return False
# =====================================================
# REGISTER — kirim OTP, belum simpan user
# =====================================================
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    electricity_type = data.get('electricity_type')

    # Validasi
    if not username or not email or not password or not electricity_type:
        return jsonify({
        "message": "Data tidak lengkap"
    }), 400

    # Cek email sudah terdaftar
    if mongo.db.users.find_one({"email": email}):
        return jsonify({"message": "Email sudah digunakan"}), 400

    # Generate OTP
    otp     = generate_otp()
    expired = datetime.utcnow() + timedelta(minutes=5)

    # Hash password
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Simpan ke collection otp_pending (belum jadi user)
    mongo.db.otp_pending.delete_many({"email": email})  # hapus OTP lama
    mongo.db.otp_pending.insert_one({
    "username": username,
    "email": email,
    "password": hashed,
    "electricity_type": electricity_type,
    "otp": otp,
    "expired_at": expired,
    "created_at": datetime.utcnow()
    })

    # Kirim email
    sent = send_otp_email(email, otp, username)
    if not sent:
        return jsonify({"message": "Gagal mengirim email OTP"}), 500

    return jsonify({
        "status":  "success",
        "message": "OTP dikirim ke email kamu",
        "email":   email
    }), 200


# =====================================================
# VERIFY OTP — cek OTP, baru simpan user
# =====================================================
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data  = request.get_json()
    email = data.get('email')
    otp   = data.get('otp')

    if not email or not otp:
        return jsonify({"message": "Email dan OTP wajib diisi"}), 400

    # Cari data pending
    pending = mongo.db.otp_pending.find_one({"email": email})

    if not pending:
        return jsonify({"message": "Data registrasi tidak ditemukan"}), 404

    # Cek expired
    if datetime.utcnow() > pending['expired_at']:
        mongo.db.otp_pending.delete_one({"email": email})
        return jsonify({"message": "OTP sudah expired, daftar ulang"}), 400

    # Cek OTP
    if pending['otp'] != otp:
        return jsonify({"message": "OTP salah"}), 400

    # OTP benar → simpan user ke collection users
    # mongo.db.users.insert_one({
    #     "name":       pending['username'],
    #     "email":      pending['email'],
    #     "password":   pending['password'],
    #     "created_at": datetime.utcnow()
    # })
    
    # OTP benar → simpan user ke collection users
    result = mongo.db.users.insert_one({
        "name": pending['username'],
        "email": pending['email'],
        "password": pending['password'],
        "electricity_type": pending['electricity_type'],
        "created_at": datetime.utcnow()
    })

    # Ambil ID user yang baru saja terdaftar
    user_id = result.inserted_id
    
    # 🌟 FIX: Pastikan memanggil 'log_user_activity' (bukan save_activity)
    log_user_activity(
        user_id,
        "Registrasi Akun",
        "User berhasil membuat akun baru"
    )

    # Hapus data pending OTP
    mongo.db.otp_pending.delete_one({"email": email})

    # Langsung login — buat token
    user         = mongo.db.users.find_one({"email": email})
    access_token = create_access_token(identity=str(user['_id']))

    return jsonify({
        "status":       "success",
        "message":      "Registrasi berhasil",
        "access_token": access_token,
        "user": {
        "username": user['name'],
        "email": user['email'],
        "electricity_type": user['electricity_type']
    }
    }), 201


# =====================================================
# RESEND OTP
# =====================================================
@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    data  = request.get_json()
    email = data.get('email')

    pending = mongo.db.otp_pending.find_one({"email": email})
    if not pending:
        return jsonify({"message": "Data tidak ditemukan, daftar ulang"}), 404

    # Generate OTP baru
    otp     = generate_otp()
    expired = datetime.utcnow() + timedelta(minutes=5)

    mongo.db.otp_pending.update_one(
        {"email": email},
        {"$set": {"otp": otp, "expired_at": expired}}
    )

    sent = send_otp_email(email, otp, pending['username'])
    if not sent:
        return jsonify({"message": "Gagal mengirim email"}), 500

    return jsonify({
        "status":  "success",
        "message": "OTP baru dikirim ke email kamu"
    }), 200

# =====================================================
# LOGIN
# =====================================================
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Cari user berdasarkan email
    user = mongo.db.users.find_one({"email": email})

    # ===== EMAIL TIDAK TERDAFTAR =====
    if user is None:
        return jsonify({
            "status": "error",
            "message": "Akun tidak terdaftar"
        }), 404

    # ===== PASSWORD SALAH =====
    if not bcrypt.checkpw(
        password.encode('utf-8'),
        user['password']
    ):
        return jsonify({
            "status": "error",
            "message": "Password salah"
        }), 401

    # ===== LOGIN BERHASIL =====
    log_user_activity(
        user['_id'],
        "Login",
        "User berhasil login ke aplikasi"
    )

    access_token = create_access_token(
        identity=str(user['_id'])
    )

    return jsonify({
        "status": "success",
        "message": "Login berhasil",
        "user": {
        "_id": str(user['_id']),
        "username": user['name'],
        "email": user['email'],
        "electricity_type": user.get("electricity_type", "prabayar")
    },
        "access_token": access_token
    }), 200
    
# =====================================================
# EDIT PROFILE
# =====================================================
@auth_bp.route('/edit-profile', methods=['PUT'])
def edit_profile():
    try:
        data = request.get_json()
        user_id = data.get('user_id')  # ID yang dikirim dari Flutter
        new_name = data.get('name')
        new_email = data.get('email')

        if not user_id:
            return jsonify({"status": "error", "message": "User ID wajib diisi"}), 400

        # Pastikan user_id dibungkus ObjectId agar dikenali MongoDB
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "name": new_name,
                "email": new_email
            }}
        )

        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "User tidak ditemukan di database"}), 404

        # Catat ke Log Aktivitas WIB
        log_user_activity(
            user_id,
            "Edit Profile",
            f"User berhasil memperbarui profil menjadi nama: {new_name}"
        )

        return jsonify({
            "status": "success",
            "message": "Profil berhasil diperbarui di database"
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
# =====================================================
# HAPUS AKUN — Hapus user, meter, dan activity log
# =====================================================    
@auth_bp.route('/delete-account', methods=['DELETE'])
@jwt_required()
def delete_account():
    try:

        user_id = get_jwt_identity()

        print("USER ID:", user_id)

        mongo.db.users.delete_one({
            "_id": ObjectId(user_id)
        })

        return jsonify({
            "success": True,
            "message": "Akun berhasil dihapus"
        }), 200

    except Exception as e:
        print("DELETE ACCOUNT ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
        
# =====================================================
# SCAN STRUK TOKEN
# =====================================================
@scan_struk_bp.route('/scan-struk', methods=['POST'])
@jwt_required()
def scan_struk():

    user_id = get_jwt_identity()

    if "image" not in request.files:
        return jsonify({
            "status": "error",
            "message": "File gambar struk wajib diupload"
        }), 400

    image_file = request.files["image"]

    try:
        import cv2
        import numpy as np

        file_bytes = np.frombuffer(image_file.read(), np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        raw_text = receipt_to_text(image)

    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"OCR gagal membaca gambar: {exc}"
        }), 500
