from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mongo
from datetime import datetime
from datetime import timedelta
from routes.auth_routes import log_user_activity  # Sesuaikan dengan lokasi file asli lokasimu
from utils.ocr_reader import reader

token_bp = Blueprint('token', __name__)

def log_user_activity(user_id, activity, description):
    print(f"--- START LOGGING: {activity} ---")
    try:
        data = {
            "user_id": str(user_id),
            "activity": activity,
            "description": description,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        }
        print(f"DEBUG: Data yang akan di-insert: {data}")
        
        # Insert langsung ke collection tanpa wrapper
        mongo.db.activity_logs.insert_one(data)
        
        print("DEBUG: INSERT BERHASIL!")
    except Exception as e:
        print(f"DEBUG: INSERT GAGAL! Error: {str(e)}")
    print("--- END LOGGING ---")
    

def get_sync_days_remaining(sisa_kwh, power, user_id):
    """
    Rumus terpusat untuk menghitung sisa hari agar Dashboard dan Notifikasi SAMA.
    """
    # Selalu gunakan estimasi berdasarkan daya untuk konsistensi
    avg_daily = _hitung_avg_daily_berdasarkan_daya(power)
    days_remaining = round(sisa_kwh / avg_daily, 1)
    
    # Tentukan status yang seragam
    if days_remaining <= 3:
        status = "SEGERA BELI TOKEN"
    elif days_remaining <= 7:
        status = "PERLU PERHATIAN"
    else:
        status = "AMAN"
    return avg_daily, days_remaining, status    

# =====================================================
# HELPER TARIF
# =====================================================
def get_tariff(power):
    if power == 450:    return 415
    elif power == 900:  return 1352
    elif power == 1300: return 1445
    elif power == 2200: return 1445
    else:               return 1700

# =====================================================
# INPUT TOKEN BARU
# =====================================================
@token_bp.route('/input', methods=['POST'])
@jwt_required()
def input_token():
    try:
        user_id = get_jwt_identity()
        data    = request.get_json()

        nominal      = int(data.get('nominal', 0))
        power        = int(data.get('power', 1300))
        meter_number = data.get('meter_number', '')
        tanggal_beli = data.get('tanggal_beli', datetime.now().strftime('%Y-%m-%d'))

        if nominal <= 0:
            return jsonify({"status": "error", "message": "Nominal wajib diisi"}), 400

        tariff    = get_tariff(power)
        total_kwh = round(nominal / tariff, 2)

        # =====================================================
        # AMBIL SISA KWH TERAKHIR — token baru DITAMBAH ke sisa
        # =====================================================
        last_scan = mongo.db.scan_history.find_one(
            {"user_id": user_id, "type": "prabayar"},
            sort=[("created_at", -1)]
        )
        # and last_scan.get("input_type") != "token_awal"

        if last_scan:
            # Ada sisa sebelumnya — tambahkan
            sisa_sebelumnya = float(last_scan.get("remaining_kwh", 0))
            sisa_baru       = round(sisa_sebelumnya + total_kwh, 2)
        else:
            # Pertama kali atau belum ada scan — pakai total token saja
            sisa_baru = total_kwh

        # Simpan ke token_history
        mongo.db.token_history.insert_one({
            "user_id":      user_id,
            "nominal":      nominal,
            "total_kwh":    total_kwh,
            "tariff":       tariff,
            "power":        power,
            "meter_number": meter_number,
            "tanggal_beli": tanggal_beli,
            "created_at":   datetime.now()
        })

        # Simpan ke scan_history dengan sisa yang sudah ditambah
        mongo.db.scan_history.insert_one({
            "user_id":        user_id,
            "type":           "prabayar",
            "meter_number":   meter_number,
            "remaining_kwh":  sisa_baru,
            "power":          power,
            "daily_usage":    0,
            "days_remaining": 0,
            "status":         "AMAN",
            "input_type":     "token",
            "nominal":        nominal,
            "kwh_dapat":      total_kwh,
            "created_at":     datetime.now()
        })

        # Notifikasi
        mongo.db.notifications.insert_one({
            "user_id":    user_id,
            "type":       "prabayar",
            "title":      "✅ Token Berhasil Dicatat",
            "desc":       f"Token Rp {nominal:,} ({total_kwh} kWh) berhasil dicatat. Sisa sekarang: {sisa_baru} kWh.",
            "time":       "Baru saja",
            "icon":       "check",
            "color":      0xFF4CAF50,
            "created_at": datetime.now()
        })

        log_user_activity(user_id, "Input Token", f"Token Rp {nominal:,} = {total_kwh} kWh. Sisa: {sisa_baru} kWh.")

        # Hitung estimasi awal
        avg_daily      = _hitung_avg_daily_berdasarkan_daya(power)
        days_remaining = round(sisa_baru / avg_daily, 1)

        return jsonify({
            "status":         "success",
            "message":        "Token berhasil dicatat",
            "total_kwh":      total_kwh,
            "sisa_kwh":       sisa_baru,
            "tariff":         tariff,
            "avg_daily":      avg_daily,
            "days_remaining": days_remaining,
            "status_token":   "AMAN"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# =====================================================
# INPUT SISA KWH MANUAL (opsional, untuk akurasi)
# =====================================================
@token_bp.route('/input-sisa', methods=['POST'])
@jwt_required()
def input_sisa_kwh():
    try:
        user_id = get_jwt_identity()
        data    = request.get_json()
        sisa_kwh     = float(data.get('sisa_kwh', 0))
        power        = int(data.get('power', 1300))
        meter_number = data.get('meter_number', '')

        # 1. Panggil fungsi dengan 3 variabel penampung
        avg_daily, days_remaining, status = get_sync_days_remaining(sisa_kwh, power, user_id)
        
        # 2. Tentukan variabel notifikasi
        if days_remaining <= 3:
            notif_title, notif_icon, notif_color = "Sisa kWh Kritis!", "warning", 0xFFF44336
        elif days_remaining <= 7:
            notif_title, notif_icon, notif_color = "Perlu Perhatian", "info", 0xFFFF9800
        else:
            notif_title, notif_icon, notif_color = "Update Sisa kWh Berhasil", "check", 0xFF4CAF50

        # 3. INSERT KE DATABASE (Ini yang sebelumnya gagal)
        mongo.db.scan_history.insert_one({
            "user_id":        user_id,
            "type":           "prabayar",
            "meter_number":   meter_number,
            "remaining_kwh":  sisa_kwh,
            "power":          power,
            "daily_usage":    avg_daily,
            "days_remaining": days_remaining,
            "status":         status,
            "input_type":     "manual",
            "created_at":     datetime.now()
        })

        mongo.db.notifications.insert_one({
            "user_id":    user_id,
            "type":       "prabayar",
            "title":      notif_title,
            "desc":       f"Sisa daya: {sisa_kwh} kWh. Perkiraan sisa waktu: {days_remaining} hari ({status}).",
            "time":       "Baru saja",
            "icon":       notif_icon,
            "color":      notif_color,
            "created_at": datetime.now()
        })

        # 4. Log Aktivitas
        log_user_activity(str(user_id), "Input Sisa kWh Manual", "User memperbarui sisa daya.")

        return jsonify({
            "status":         "success",
            "remaining_kwh":  sisa_kwh,
            "daily_usage":    avg_daily,
            "days_remaining": days_remaining,
            "status_token":   status
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================
# RIWAYAT TOKEN
# =====================================================
# @token_bp.route('/history', methods=['GET'])
# @jwt_required()
# def get_token_history():
#     try:
#         user_id = get_jwt_identity()

#         riwayat = list(
#             mongo.db.token_history
#             .find({"user_id": user_id}, {"_id": 0})
#             .sort("created_at", -1)
#             .limit(10)
#         )

#         for item in riwayat:
#             if "created_at" in item and isinstance(item["created_at"], datetime):
#                 item["created_at"] = item["created_at"].strftime("%Y-%m-%d %H:%M")

#         return jsonify({
#             "status": "success",
#             "data":   riwayat
#         })

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500


# =====================================================
# RIWAYAT PEMBELIAN TOKEN
# =====================================================
@token_bp.route('/history-pembelian', methods=['GET'])
@jwt_required()
def history_pembelian():

    try:

        user_id = get_jwt_identity()

        history = list(
            mongo.db.token_history
            .find(
                {"user_id": user_id},
                {"_id": 0}
            )
            .sort("created_at", -1)
        )

        for item in history:

            if isinstance(item.get("created_at"), datetime):

                item["created_at"] = item["created_at"].strftime(
                    "%d %b %Y %H:%M"
                )

        return jsonify({

            "status": "success",

            "data": history

        })

    except Exception as e:

        return jsonify({

            "status": "error",

            "message": str(e)

        }),500
        
        

# =====================================================
# DASHBOARD PRABAYAR
# =====================================================
@token_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def dashboard_prabayar():
    try:
        user_id = get_jwt_identity()

        # Ambil semua scan history prabayar user ini
        semua_scan = list(
            mongo.db.scan_history.find(
                {"user_id": user_id, "type": "prabayar"},
                {"_id": 0}
            ).sort("created_at", 1)  # urut dari lama ke baru
        )

        # Belum ada data sama sekali
        if not semua_scan:
            return jsonify({
                "status":         "success",
                "sisa_kwh":       0,
                "days_remaining": 0,
                "daily_usage":    0,
                "daily_cost":     0,
                "status_token":   "BELUM ADA DATA",
                "last_update":    "-",
                "estimasi_ready": False,
                "hari":           [],
                "kwh_data":       [],
                "history_beli":   []
            })

        scan_terakhir = semua_scan[-1]
        power         = scan_terakhir.get("power", 1300)
        sisa_kwh      = float(scan_terakhir.get("remaining_kwh", 0))
        tgl_update    = scan_terakhir.get("created_at")
        last_update   = tgl_update.strftime("%d-%m-%Y %H:%M") if isinstance(tgl_update, datetime) else "-"

        # =====================================================
        # HITUNG PEMAKAIAN HARIAN
        # Butuh minimal 2 scan yang bukan "token" untuk estimasi akurat
        # =====================================================
        scan_non_token = [
            s for s in semua_scan
            if s.get("input_type") not in ("token", "token_awal")
        ]

        avg_daily      = _hitung_avg_daily_berdasarkan_daya(power)
        estimasi_ready = False

        #  Ganti bagian ini di dashboard_prabayar:
        if len(scan_non_token) >= 2:
            for i in range(len(scan_non_token) - 1, 0, -1):
                s2 = scan_non_token[i]     # Scan terbaru
                s1 = scan_non_token[i-1]   # Scan sebelumnya
                
                kwh_1 = float(s1.get("remaining_kwh", 0))
                kwh_2 = float(s2.get("remaining_kwh", 0))
                tgl_1 = s1.get("created_at")
                tgl_2 = s2.get("created_at")
                
                # Normalisasi Timezone
                if hasattr(tgl_1, 'tzinfo') and tgl_1.tzinfo: tgl_1 = tgl_1.replace(tzinfo=None)
                if hasattr(tgl_2, 'tzinfo') and tgl_2.tzinfo: tgl_2 = tgl_2.replace(tzinfo=None)
                
                diff_days = (tgl_2 - tgl_1).total_seconds() / 86400
                used      = kwh_1 - kwh_2
                
                # SYARAT UTAMA: Harus ada pemakaian (used > 0) DAN jarak minimal 6 jam
                if used > 0 and diff_days >= 0.25:
                    avg_daily      = round(used / diff_days, 2)
                    estimasi_ready = True
                    print(f"DEBUG: Data valid ditemukan! (Jarak {diff_days*24:.1f} jam)")
                    break # Keluar dari loop jika sudah ketemu pasangan valid
                else:
                    print(f"DEBUG: Lewati pasangan scan ini (Jarak {diff_days*24:.1f} jam)")
                    
        daily_cost     = int(avg_daily * get_tariff(power))
        days_remaining = round(sisa_kwh / avg_daily, 1) if avg_daily > 0 else 0

        if not estimasi_ready:
            status_token = "SCAN LAGI UNTUK ESTIMASI"
        elif days_remaining <= 3:
            status_token = "SEGERA BELI TOKEN"
        elif days_remaining <= 7:
            status_token = "PERLU PERHATIAN"
        else:
            status_token = "AMAN"

        # =====================================================
        # GRAFIK — dari data scan aktual, bukan estimasi flat
        # =====================================================
        def bangun_segmen_usage(scan_non_token):
            """
            Return list of (tgl_mulai, tgl_akhir, rate_per_hari) dari tiap pasang
            scan berurutan yang valid untuk dijadikan estimasi.
            """
            segments = []

            for i in range(len(scan_non_token) - 1):
                s1 = scan_non_token[i]
                s2 = scan_non_token[i + 1]

                kwh_1 = float(s1.get("remaining_kwh", 0))
                kwh_2 = float(s2.get("remaining_kwh", 0))
                tgl_1 = s1.get("created_at")
                tgl_2 = s2.get("created_at")

                if not isinstance(tgl_1, datetime) or not isinstance(tgl_2, datetime):
                    continue

                if hasattr(tgl_1, 'tzinfo') and tgl_1.tzinfo:
                    tgl_1 = tgl_1.replace(tzinfo=None)
                if hasattr(tgl_2, 'tzinfo') and tgl_2.tzinfo:
                    tgl_2 = tgl_2.replace(tzinfo=None)

                diff_days = (tgl_2 - tgl_1).total_seconds() / 86400
                used = kwh_1 - kwh_2

                if used > 0 and diff_days >= 0.25:
                    rate = round(used / diff_days, 2)
                    segments.append((tgl_1, tgl_2, rate))

            return segments


        def bangun_grafik_7_hari(scan_non_token, avg_daily, estimasi_ready):
            """
            Bangun grafik_hari & grafik_kwh untuk 7 hari terakhir,
            berdasarkan segmen usage riil (bukan snapshot field lama).
            """

            segments = bangun_segmen_usage(scan_non_token)

            grafik_hari = []
            grafik_kwh = []

            today = datetime.now()

            for i in range(6, -1, -1):
                tgl = today - timedelta(days=i)
                grafik_hari.append(tgl.strftime("%d/%m"))

                rate_for_day = None

                for (seg_start, seg_end, seg_rate) in segments:
                    if seg_start.date() <= tgl.date() <= seg_end.date():
                        rate_for_day = seg_rate
                        # sengaja TIDAK break -> segmen terakhir yang mencakup
                        # hari ini (lebih baru) yang menang

                if rate_for_day is not None:
                    grafik_kwh.append(rate_for_day)
                else:
                    grafik_kwh.append(0.0)

            return grafik_hari, grafik_kwh
        # grafik_hari = []
        # grafik_kwh  = []

        # # Ambil scan mulai dari tanggal token pertama
        # if semua_scan:
        #     tgl_pertama = semua_scan[0].get("created_at")
        #     if isinstance(tgl_pertama, datetime):
        #         from datetime import timedelta
        #         # Tampilkan 7 hari terakhir dari data yang ada
        #         today = datetime.now()
        #         for i in range(6, -1, -1):
        #             tgl = today - timedelta(days=i)
        #             tgl_str = tgl.strftime("%d/%m")
        #             grafik_hari.append(tgl_str)

        #             # Cari scan di hari ini
        #             scan_hari_ini = [
        #                 s for s in semua_scan
        #                 if isinstance(s.get("created_at"), datetime)
        #                 and s["created_at"].date() == tgl.date()
        #                 and s.get("input_type") not in ("token", "token_awal")
        #             ]

        #             # if scan_hari_ini:
        #             #     # Ambil pemakaian harian dari scan hari itu
        #             #     kwh_val = float(scan_hari_ini[-1].get("daily_usage", avg_daily))
        #             #     grafik_kwh.append(kwh_val if kwh_val > 0 else avg_daily)
        #             # else:
        #             #     # Tidak ada scan hari ini — pakai estimasi atau 0
        #             #     grafik_kwh.append(avg_daily if estimasi_ready else 0.0)
                    
        #             if scan_hari_ini:
        #                 # Ambil scan terakhir di hari tersebut
        #                 scan_terbaru_hari_ini = scan_hari_ini[-1]
                        
        #                 # HANYA ambil daily_usage dari data yang estimasinya sudah VALID (estimasi_ready = True)
        #                 # Jika belum ready, biarkan 0 atau nilai default yang aman
        #                 if estimasi_ready:
        #                     kwh_val = float(scan_terbaru_hari_ini.get("daily_usage", avg_daily))
        #                     grafik_kwh.append(kwh_val)
        #                 else:
        #                     grafik_kwh.append(0.0) # Grafik 0 jika belum ada data valid
        #             else:
        #                 grafik_kwh.append(0.0) # Grafik 0 jika tidak ada scan di hari itu

        grafik_hari, grafik_kwh = bangun_grafik_7_hari(
            scan_non_token, avg_daily, estimasi_ready
        )
        # =====================================================
        # RIWAYAT BELI TOKEN
        # =====================================================
        riwayat_token = list(
            mongo.db.token_history
            .find({"user_id": user_id}, {"_id": 0})
            .sort("created_at", -1)
            .limit(10)
        )

        history_beli = []
        for item in riwayat_token:
            tgl = item.get("created_at")
            history_beli.append({
                "tanggal":   tgl.strftime("%Y-%m-%d") if isinstance(tgl, datetime) else "-",
                "nominal":   item.get("nominal", 0),
                "total_kwh": item.get("total_kwh", 0),
                "power":     item.get("power", 1300),
            })

        return jsonify({
            "status":          "success",
            "sisa_kwh":        sisa_kwh,
            "days_remaining":  days_remaining,
            "daily_usage":     avg_daily,
            "daily_cost":      daily_cost,
            "status_token":    status_token,
            "last_update":     last_update,
            "estimasi_ready":  estimasi_ready,
            "hari":            grafik_hari,
            "kwh_data":        grafik_kwh,
            "history_beli":    history_beli,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# =====================================================
# HELPER — HITUNG RATA-RATA HARIAN DARI RIWAYAT TOKEN
# =====================================================
def _hitung_avg_daily(riwayat, power=1300):
    if len(riwayat) >= 2:
        total_kwh  = 0
        total_hari = 0
        for i in range(len(riwayat) - 1):
            tgl_baru = riwayat[i].get("created_at", datetime.now())
            tgl_lama = riwayat[i + 1].get("created_at", datetime.now())

            if isinstance(tgl_baru, str):
                try: tgl_baru = datetime.strptime(tgl_baru, "%Y-%m-%d %H:%M")
                except: tgl_baru = datetime.now()
            if isinstance(tgl_lama, str):
                try: tgl_lama = datetime.strptime(tgl_lama, "%Y-%m-%d %H:%M")
                except: tgl_lama = datetime.now()

            hari = (tgl_baru - tgl_lama).days
            
            if hari < 1:
                continue

            kwh = riwayat[i + 1].get("total_kwh", 0)
            total_kwh  += kwh
            total_hari += hari

        if total_hari > 0:
            return round(total_kwh / total_hari, 2)

    # Fallback estimasi dari daya (dipakai juga kalau semua pasangan
    # dilewati karena jaraknya kurang dari 1 hari)
    return round((power / 1000) * 8, 2)


# =====================================================
# HELPER — BUAT DATA GRAFIK 7 HARI
# =====================================================
def _buat_grafik(riwayat, avg_daily):
    from datetime import timedelta
    today      = datetime.now() # Menggunakan waktu lokal server
    hari_label = []
    kwh_data   = []

    for i in range(6, -1, -1):
        tgl = today - timedelta(days=i)
        hari_label.append(tgl.strftime("%d/%m"))
        # Set ke nilai rata-rata real (akan bernilai 0 jika data scan baru satu)
        kwh_data.append(avg_daily if avg_daily > 0 else 0.0)

    return hari_label, kwh_data

# =====================================================
# HELPER — ESTIMASI KONSUMSI REALISTIS BERDASARKAN DAYA
# =====================================================
def _hitung_avg_daily_berdasarkan_daya(power):
    """
    Menghitung standar estimasi pemakaian kWh per hari 
    berdasarkan daya batas (VA) rumah tangga dari 450VA hingga 5500VA.
    """
    if power <= 450:
        return 2.0   # 450VA: Lampu, TV kecil, Kipas (± 2 kWh/hari)
    elif power <= 900:
        return 3.5   # 900VA: Tambah Magicom, Kulkas kecil (± 3.5 kWh/hari)
    elif power <= 1300:
        return 5.2   # 1300VA: Tambah Pompa Air, Setrika (± 5.2 kWh/hari)
    elif power <= 2200:
        return 8.5   # 2200VA: Tambah AC 1 PK / Microwave (± 8.5 kWh/hari)
    elif power <= 3500:
        return 13.0  # 3500VA: Tambah AC beberapa buah / Water Heater (± 13 kWh/hari)
    elif power <= 4400:
        return 16.5  # 4400VA: Rumah besar dengan banyak elektronik (± 16.5 kWh/hari)
    elif power <= 5500:
        return 21.0  # 5500VA: Penggunaan intensif / Home Office (± 21 kWh/hari)
    else:
        return 25.0  # Di atas 5500VA (± 25 kWh/hari)