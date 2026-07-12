from flask import Blueprint, jsonify
from utils.db import mongo
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId # <--- PENTING: Jangan lupa import ini!

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/pascabayar', methods=['GET'])
@jwt_required()
def get_dashboard_pasca():
    # Mengambil user_id dari token JWT yang sedang login
    user_id = get_jwt_identity()
    
    # 1. Ambil data dari koleksi khusus pascabayar
    # Pastikan di MongoDB sudah ada koleksi 'dashboard_pasca_summary'
    data = mongo.db.dashboard_pasca_summary.find_one({"user_id": ObjectId(user_id)})
    
    if not data:
        # Jika data belum ada, kirim data default atau pesan error
        return jsonify({
            "status": "success", 
            "message": "Data belum ada",
            "estimasi_tagihan": 0,
            "progress": 0.0,
            "daily_usage": 0.0,
            "daily_cost": 0,
            "hari": [],
            "kwh_data": [],
            "history_tagihan": []
        }), 200
        
    # 2. Hapus _id (BSON) agar bisa dikirim ke Flutter (JSON)
    # Flutter tidak bisa membaca object ObjectId dari BSON
    data['_id'] = str(data['_id'])
    data['user_id'] = str(data['user_id'])
    
    return jsonify({"status": "success", "data": data})
# from flask import Blueprint, jsonify, request
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from services.pln_scraper import cek_tagihan_pln
# from utils.db import mongo
# from datetime import datetime, timedelta
# import random
# import calendar

# dashboard_bp = Blueprint("dashboard", __name__)

# from services.pln_scraper import cek_tagihan_pln

# # =====================================================
# # Flask kirim request ke listrik.okcek.com untuk cek tagihan PLN
# # =====================================================
# @dashboard_bp.route("/connect", methods=["POST"])
# @jwt_required()
# def connect_pln():
#     try:
#         user_id      = get_jwt_identity()
#         data         = request.get_json()
#         id_pelanggan = data.get("id_pelanggan")
#         budget       = data.get("budget", 0)
#         tipe         = data.get("tipe", "pascabayar")

#         if not id_pelanggan:
#             return jsonify({
#                 "status":  "error",
#                 "message": "ID Pelanggan wajib diisi"
#             }), 400

#         # Coba scraping data PLN asli dulu
#         data_pln_asli = cek_tagihan_pln(id_pelanggan)

#         if data_pln_asli:
#             # Berhasil dapat data asli dari PLN
#             # Parse tagihan ke angka
#             tagihan_str = data_pln_asli.get("tagihan", "0")
#             tagihan_num = int(''.join(filter(str.isdigit, tagihan_str))) if tagihan_str else 0

#             # Parse daya dari tarif_daya (misal "R1/900VA" → 900)
#             tarif_daya = data_pln_asli.get("tarif_daya", "1300")
#             daya       = 1300
#             import re
#             match = re.search(r'(\d+)\s*VA', tarif_daya, re.IGNORECASE)
#             if match:
#                 daya = int(match.group(1))

#             pln_data = {
#                 "user_id":      user_id,
#                 "tipe":         tipe,
#                 "id_pelanggan": id_pelanggan,
#                 "nama":         data_pln_asli.get("nama", ""),
#                 "tarif_daya":   tarif_daya,
#                 "daya":         daya,
#                 "tarif":        1444,
#                 "budget":       budget,
#                 "tagihan_bulan_ini": tagihan_num,
#                 "kwh_bulan_ini":     round(tagihan_num / 1444, 1) if tagihan_num else 0,
#                 "stand_meter":  data_pln_asli.get("stand_meter", ""),
#                 "periode":      data_pln_asli.get("periode", ""),
#                 "sumber":       "PLN_ASLI",
#                 "updated_at":   datetime.utcnow()
#             }

#             # Generate history mock berdasarkan tagihan asli
#             from services.dashboard_routes import generate_mock_history
#             pln_data["history_tagihan"] = generate_mock_history(tagihan_num)

#         else:
#             # Gagal scraping → pakai mock data
#             pln_data          = generate_mock_pln(user_id, tipe)
#             pln_data["sumber"] = "MOCK"

#         pln_data["id_pelanggan"] = id_pelanggan
#         pln_data["budget"]       = budget

#         # Simpan atau update
#         mongo.db.pln_data.delete_one({"user_id": user_id, "tipe": tipe})
#         mongo.db.pln_data.insert_one(pln_data.copy())
#         pln_data.pop("_id", None)

#         # Convert datetime
#         if "updated_at" in pln_data:
#             pln_data["updated_at"] = pln_data["updated_at"].strftime("%Y-%m-%d %H:%M")

#         sumber_label = "PLN" if pln_data.get("sumber") == "PLN_ASLI" else "estimasi"

#         return jsonify({
#             "status":  "success",
#             "message": f"Data {sumber_label} berhasil dihubungkan",
#             "sumber":  pln_data.get("sumber"),
#             "nama":    pln_data.get("nama", ""),
#         })

#     except Exception as e:
#         return jsonify({
#             "status":  "error",
#             "message": str(e)
#         }), 500
        
# # =====================================================
# # HELPER UNTUK GENERATE MOCK HISTORY TAGIHAN BERDASARKAN TAGIHAN BULAN INI
# # =====================================================        
        
# def generate_mock_history(tagihan_bulan_ini):
#     from datetime import datetime, timedelta
#     import random
#     today  = datetime.utcnow()
#     result = []
#     base   = tagihan_bulan_ini if tagihan_bulan_ini > 0 else 250000
#     for i in range(5, -1, -1):
#         tgl = today - timedelta(days=30 * i)
#         t   = base + random.randint(-30000, 30000)
#         result.append({
#             "bulan":   tgl.strftime("%b %Y"),
#             "kwh":     round(t / 1444, 1),
#             "tagihan": t,
#             "status":  "lunas" if i > 0 else "belum"
#         })
#     return result        

# # =====================================================
# # HELPER — GENERATE MOCK PLN DATA
# # =====================================================
# def generate_mock_pln(user_id, tipe):
#     import hashlib
#     today = datetime.utcnow()

#     # Generate angka konsisten dari user_id
#     # Jadi tiap user dapat data berbeda tapi tidak berubah-ubah
#     seed = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)

#     daya_list  = [900, 1300, 2200, 3500]
#     nama_list  = ["Budi Santoso", "Siti Rahayu", "Ahmad Fauzi",
#                   "Dewi Lestari", "Hendra Wijaya"]

#     daya  = daya_list[seed % len(daya_list)]
#     nama  = nama_list[seed % len(nama_list)]
#     tarif = 1444

#     if tipe == "prabayar":
#         sisa_kwh = round(20 + (seed % 80), 1)
#         return {
#             "user_id":          user_id,
#             "tipe":             "prabayar",
#             "id_pelanggan":     f"5{str(seed)[:10]}",
#             "nama":             nama,
#             "daya":             daya,
#             "tarif":            tarif,
#             "sisa_kwh":         sisa_kwh,
#             "nominal_terakhir": 100000,
#             "kwh_terakhir":     round(100000 / tarif, 1),
#             "tanggal_beli":     (today - timedelta(days=seed % 15)).strftime("%Y-%m-%d"),
#             "history_beli": [
#                 {
#                     "tanggal": (today - timedelta(days=seed % 15)).strftime("%Y-%m-%d"),
#                     "nominal": 100000,
#                     "kwh":     round(100000 / tarif, 1),
#                 },
#                 {
#                     "tanggal": (today - timedelta(days=30 + seed % 10)).strftime("%Y-%m-%d"),
#                     "nominal": 50000,
#                     "kwh":     round(50000 / tarif, 1),
#                 },
#                 {
#                     "tanggal": (today - timedelta(days=45 + seed % 10)).strftime("%Y-%m-%d"),
#                     "nominal": 100000,
#                     "kwh":     round(100000 / tarif, 1),
#                 },
#             ],
#             "updated_at": today
#         }

#     else:
#         base_kwh   = 150 + (seed % 100)  # antara 150-250 kWh/bulan
#         history    = []
#         for i in range(5, -1, -1):
#             tgl = today - timedelta(days=30 * i)
#             kwh = base_kwh + (seed % 30) - 15 + (i * 3)
#             history.append({
#                 "bulan":   tgl.strftime("%b %Y"),
#                 "kwh":     kwh,
#                 "tagihan": kwh * tarif,
#                 "status":  "lunas" if i > 0 else "belum"
#             })

#         # Tambah kalkulasi harian
#         hari_ini    = today.day
#         total_hari  = calendar.monthrange(today.year, today.month)[1]
#         avg_daily   = round(base_kwh / total_hari, 2)
#         kwh_berjalan = round(avg_daily * hari_ini, 1)

#         kwh_bulan_ini = base_kwh + (seed % 20)

#         return {
#             "user_id":           user_id,
#             "tipe":              "pascabayar",
#             "id_pelanggan":      f"5{str(seed)[:10]}",
#             "nama":              nama,
#             "daya":              daya,
#             "tarif":             tarif,
#             "budget":            0,           # ← 0 dulu, user set sendiri
#             "kwh_bulan_ini":     kwh_bulan_ini,
#             "tagihan_bulan_ini": kwh_bulan_ini * tarif,
#             "kwh_berjalan":      kwh_berjalan, # ← tambah ini
#             "avg_daily":         avg_daily,    # ← tambah ini
#             "history_tagihan":   history,
#             "sumber":            "MOCK",       # ← tambah ini
#             "updated_at":        today
#         }
# # =====================================================
# # HELPER — AMBIL ATAU BUAT MOCK PLN
# # =====================================================
# def get_or_create_pln(user_id, tipe):
#     data = mongo.db.pln_data.find_one(
#         {"user_id": user_id, "tipe": tipe},
#         {"_id": 0}
#     )
#     if not data:
#         data = generate_mock_pln(user_id, tipe)
#         mongo.db.pln_data.insert_one(data.copy())
#         data.pop("_id", None)
    
#     # Convert datetime ke string
#     if "updated_at" in data and isinstance(data["updated_at"], datetime):
#         data["updated_at"] = data["updated_at"].strftime("%Y-%m-%d %H:%M")
    
#     return data


# # =====================================================
# # DASHBOARD PRABAYAR
# # =====================================================
# @dashboard_bp.route("/prabayar", methods=["GET"])
# @jwt_required()
# def dashboard_prabayar():
#     try:
#         user_id = get_jwt_identity()

#         # Ambil data PLN mock
#         pln = get_or_create_pln(user_id, "prabayar")

#         # Ambil 7 scan terakhir dari MongoDB
#         scans = list(
#             mongo.db.scan_history
#             .find({"user_id": user_id, "type": "prabayar"}, {"_id": 0})
#             .sort("created_at", -1)
#             .limit(7)
#         )

#         # Buat data grafik 7 hari
#         hari_label = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
#         kwh_data   = []

#         if len(scans) >= 2:
#             # Hitung pemakaian harian dari selisih scan
#             for i in range(min(len(scans) - 1, 7)):
#                 selisih = scans[i + 1]["remaining_kwh"] - scans[i]["remaining_kwh"]
#                 kwh_data.append(round(abs(selisih), 2))
#             # Pad dengan 0 kalau kurang dari 7
#             while len(kwh_data) < 7:
#                 kwh_data.insert(0, 0.0)
#         else:
#             # Belum cukup data scan → pakai estimasi dari PLN
#             daily_est = round(pln["daya"] / 1000 * 8, 2)
#             kwh_data  = [daily_est] * 7

#         # Hitung estimasi harian
#         daily_usage = sum(kwh_data) / len(kwh_data) if kwh_data else 0
#         daily_cost  = int(daily_usage * pln["tarif"])

#         # Sisa kWh dari scan terakhir atau PLN mock
#         sisa_kwh = scans[0]["remaining_kwh"] if scans else pln["sisa_kwh"]

#         # Prediksi hari tersisa
#         days_remaining = round(sisa_kwh / daily_usage, 1) if daily_usage > 0 else 0

#         # Status
#         if days_remaining <= 3:
#             status = "SEGERA BELI TOKEN"
#         elif days_remaining <= 7:
#             status = "PERLU PERHATIAN"
#         else:
#             status = "AMAN"

#         return jsonify({
#             "status":         "success",
#             "sisa_kwh":       sisa_kwh,
#             "days_remaining": days_remaining,
#             "daily_usage":    round(daily_usage, 2),
#             "daily_cost":     daily_cost,
#             "status_token":   status,
#             "daya":           pln["daya"],
#             "tarif":          pln["tarif"],
#             "hari":           hari_label,
#             "kwh_data":       kwh_data,
#             "history_beli":   pln["history_beli"],
#         })

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500


# # =====================================================
# # DASHBOARD PASCABAYAR
# # =====================================================
# @dashboard_bp.route("/pascabayar", methods=["GET"])
# @jwt_required()
# def dashboard_pascabayar():
#     try:
#         user_id = get_jwt_identity()
#         now     = datetime.utcnow()
#         import calendar
#         hari_ini     = now.day
#         total_hari   = calendar.monthrange(now.year, now.month)[1]
#         awal_bulan   = datetime(now.year, now.month, 1)

#         # Ambil semua scan bulan ini
#         scans = list(
#             mongo.db.scan_history.find(
#                 {"user_id": user_id, "type": "pascabayar",
#                  "created_at": {"$gte": awal_bulan}},
#                 {"_id": 0}
#             ).sort("created_at", -1)
#         )

#         # Ambil data PLN sebagai fallback
#         pln = get_or_create_pln(user_id, "pascabayar")

#         if scans:
#             # Ada data scan — pakai data real
#             scan_terbaru   = scans[0]
#             estimasi       = scan_terbaru.get("estimasi_tagihan", 0)
#             tagihan_bjln   = scan_terbaru.get("tagihan_berjalan", 0)
#             kwh_terpakai   = scan_terbaru.get("kwh_terpakai", 0)
#             daily_usage    = scan_terbaru.get("daily_usage", 0)
#             daily_cost     = scan_terbaru.get("daily_cost", 0)
#             status_budget  = scan_terbaru.get("status", "AMAN")
#             budget         = scan_terbaru.get("budget", pln.get("budget", 0))

#             # Grafik dari semua scan bulan ini
#             grafik_hari = []
#             grafik_kwh  = []
#             for i in range(len(scans) - 1, -1, -1):
#                 scan = scans[i]
#                 tgl  = scan.get("created_at", now)
#                 if isinstance(tgl, datetime):
#                     grafik_hari.append(tgl.strftime("%d/%m"))
#                 else:
#                     grafik_hari.append(str(i + 1))
#                 grafik_kwh.append(float(scan.get("daily_usage", 0)))

#             # Pad ke 7 hari kalau kurang
#             while len(grafik_hari) < 7:
#                 grafik_hari.insert(0, "-")
#                 grafik_kwh.insert(0, 0.0)

#             # Ambil 7 terakhir
#             grafik_hari = grafik_hari[-7:]
#             grafik_kwh  = grafik_kwh[-7:]

#         else:
#             # Belum ada scan — pakai PLN mock
#             kwh_bulan    = pln.get("kwh_bulan_ini", 0)
#             avg_daily    = kwh_bulan / 30 if kwh_bulan > 0 else 0
#             daily_usage  = round(avg_daily, 2)
#             daily_cost   = int(daily_usage * pln.get("tarif", 1444))
#             kwh_terpakai = round(avg_daily * hari_ini, 2)
#             tagihan_bjln = int(kwh_terpakai * pln.get("tarif", 1444))
#             estimasi     = int(avg_daily * total_hari * pln.get("tarif", 1444))
#             budget       = pln.get("budget", 0)
#             status_budget = "AMAN"

#             daily_est   = round(pln.get("daya", 1300) / 1000 * 8, 2)
#             grafik_hari = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
#             grafik_kwh  = [daily_est] * 7

#         # Persen perubahan dari bulan lalu
#         history = pln.get("history_tagihan", [])
#         persen  = 0.0
#         if len(history) >= 2:
#             bulan_lalu = history[-2]["tagihan"]
#             if bulan_lalu > 0:
#                 persen = round((estimasi - bulan_lalu) / bulan_lalu * 100, 1)

#         # Progress budget
#         progress = min(tagihan_bjln / budget, 1.0) if budget > 0 else 0.0

#         return jsonify({
#             "status":            "success",
#             "estimasi_tagihan":  estimasi,
#             "persen_perubahan":  persen,
#             "daily_usage":       daily_usage,
#             "daily_cost":        daily_cost,
#             "kwh_berjalan":      kwh_terpakai,
#             "tagihan_berjalan":  tagihan_bjln,
#             "hari_ke":           hari_ini,
#             "total_hari_bulan":  total_hari,
#             "budget":            int(budget),
#             "progress":          round(progress, 2),
#             "status_budget":     status_budget,
#             "daya":              pln.get("daya", 1300),
#             "tarif":             pln.get("tarif", 1444),
#             "hari":              grafik_hari,
#             "kwh_data":          grafik_kwh,
#             "history_tagihan":   history,
#         })

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500