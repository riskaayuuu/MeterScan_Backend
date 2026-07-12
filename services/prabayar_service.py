# from datetime import datetime

# def calculate_prabayar(remaining_kwh, power, last_scan=None):

#     # =====================================================
#     # HITUNG PEMAKAIAN HARIAN
#     # =====================================================
#     daily_usage = 0

#     if last_scan and "remaining_kwh" in last_scan:
#         prev_kwh  = last_scan["remaining_kwh"]
#         prev_time = last_scan["created_at"]
#         now       = datetime.utcnow()

#         # Selisih hari antara scan terakhir dan sekarang
#         diff_days = max((now - prev_time).days, 1)

#         used = prev_kwh - remaining_kwh

#         if used > 0:
#             daily_usage = round(used / diff_days, 2)

#     # Kalau belum ada riwayat, estimasi dari daya
#     if daily_usage == 0:
#         daily_usage = round((power / 1000) * 8, 2)  # asumsi 8 jam/hari

#     # =====================================================
#     # PREDIKSI SISA HARI
#     # =====================================================
#     if daily_usage > 0:
#         days_remaining = round(remaining_kwh / daily_usage, 1)
#     else:
#         days_remaining = 0

#     # =====================================================
#     # STATUS
#     # =====================================================
#     if days_remaining <= 3:
#         status = "SEGERA BELI TOKEN"
#     elif days_remaining <= 7:
#         status = "PERLU PERHATIAN"
#     else:
#         status = "AMAN"

#     return {
#         "remaining_kwh":  remaining_kwh,
#         "daily_usage":    daily_usage,
#         "days_remaining": days_remaining,
#         "status":         status
#     }
# from datetime import datetime

# def calculate_prabayar(remaining_kwh, power, last_scan=None):
#     # 1. Pastikan daily_usage punya nilai default berdasarkan daya (Profil Rumah)
#     # Gunakan standar yang sudah kita sepakati sebelumnya
#     def get_default_usage(p):
#         if p <= 450: return 2.0
#         if p <= 900: return 3.5
#         if p <= 1300: return 5.2
#         return 8.5
    
#     daily_usage = get_default_usage(power)

#     # 2. Hitung berdasarkan riwayat jika ada
#     if last_scan and "remaining_kwh" in last_scan:
#         prev_kwh  = float(last_scan.get("remaining_kwh", 0))
#         prev_time = last_scan.get("created_at")
        
#         # Konversi jika prev_time masih dalam bentuk string
#         if isinstance(prev_time, str):
#             try: prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")
#             except: prev_time = datetime.utcnow()
            
#         now = datetime.utcnow()
#         # Gunakan total_seconds agar lebih akurat (bukan cuma .days)
#         diff_days = max((now - prev_time).total_seconds() / 86400, 0.1)

#         used = prev_kwh - remaining_kwh
#         # Hanya hitung jika pemakaian masuk akal (> 0)
#         if used > 0:
#             daily_usage = round(used / diff_days, 2)

#     # 3. Prediksi sisa hari
#     days_remaining = round(remaining_kwh / daily_usage, 1) if daily_usage > 0 else 0

#     # 4. Status
#     if days_remaining <= 3:
#         status = "SEGERA BELI TOKEN"
#     elif days_remaining <= 7:
#         status = "PERLU PERHATIAN"
#     else:
#         status = "AMAN"

#     return {
#         "daily_usage":    daily_usage,
#         "days_remaining": days_remaining,
#         "status":         status
#     }

# from datetime import datetime

# def calculate_prabayar(remaining_kwh, power, last_scan=None):
#     """
#     Hitung prediksi prabayar.
#     - Scan pertama: daily_usage dari estimasi daya
#     - Scan kedua+: daily_usage dari selisih scan aktual
#     """

#     def get_default_usage(p):
#         if p <= 450:  return 2.0
#         if p <= 900:  return 3.5
#         if p <= 1300: return 5.2
#         if p <= 2200: return 8.5
#         if p <= 3500: return 13.0
#         if p <= 4400: return 16.5
#         return 21.0

#     daily_usage    = get_default_usage(power)
#     estimasi_ready = False

#     if last_scan and "remaining_kwh" in last_scan:
#         # Jangan hitung dari scan yang merupakan input token
#         if last_scan.get("input_type") not in ("token", "token_awal"):
#             prev_kwh  = float(last_scan.get("remaining_kwh", 0))
#             prev_time = last_scan.get("created_at")

#             if isinstance(prev_time, str):
#                 try:
#                     prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")
#                 except:
#                     prev_time = datetime.now()

#             now       = datetime.now()
#             # diff_days = max((now - prev_time).total_seconds() / 86400, 0.1)
#             diff_days = 15.0
#             used      = prev_kwh - remaining_kwh

#             # if used > 0 and diff_days >= 0.5:
#             if used > 0:
#                 daily_usage    = round(used / diff_days, 2)
#                 estimasi_ready = True

#     days_remaining = round(remaining_kwh / daily_usage, 1) if daily_usage > 0 else 0

#     if not estimasi_ready:
#         status = "SCAN LAGI UNTUK ESTIMASI"
#     elif days_remaining <= 3:
#         status = "SEGERA BELI TOKEN"
#     elif days_remaining <= 7:
#         status = "PERLU PERHATIAN"
#     else:
#         status = "AMAN"

#     return {
#         "daily_usage":     daily_usage,
#         "days_remaining":  days_remaining,
#         "status":          status,
#         "estimasi_ready":  estimasi_ready,
#     }

# from datetime import datetime, timezone

# def calculate_prabayar(remaining_kwh, power, last_scan=None):

#     def get_default_usage(p):
#         if p <= 450:  return 2.0
#         if p <= 900:  return 3.5
#         if p <= 1300: return 5.2
#         if p <= 2200: return 8.5
#         if p <= 3500: return 13.0
#         if p <= 4400: return 16.5
#         return 21.0

#     daily_usage    = get_default_usage(power)
#     estimasi_ready = False

#     if last_scan and "remaining_kwh" in last_scan:
#         if last_scan.get("input_type") not in ("token", "token_awal"):
#             prev_kwh  = float(last_scan.get("remaining_kwh", 0))
#             prev_time = last_scan.get("created_at")

#             # =====================================================
#             # FIX TIMEZONE — strip timezone info untuk konsistensi
#             # =====================================================
#             if isinstance(prev_time, str):
#                 try:
#                     prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")
#                 except:
#                     prev_time = None

#             if prev_time is not None:
#                 # Hapus timezone info kalau ada
#                 if hasattr(prev_time, 'tzinfo') and prev_time.tzinfo is not None:
#                     prev_time = prev_time.replace(tzinfo=None)

#                 now       = datetime.utcnow()
#                 diff_secs = (now - prev_time).total_seconds()
#                 diff_days = diff_secs / 86400

#                 used = prev_kwh - remaining_kwh

#                 print(f"DEBUG prabayar_service:")
#                 print(f"  prev_kwh={prev_kwh}, remaining={remaining_kwh}")
#                 print(f"  prev_time={prev_time}, now={now}")
#                 print(f"  diff_secs={diff_secs:.1f}, diff_days={diff_days:.4f}")
#                 print(f"  used={used:.2f}")
#                 print(f"  input_type={last_scan.get('input_type')}")

#                 # Minimal 6 jam (0.25 hari) antar scan untuk estimasi valid
#                 MIN_HOURS = 6
#                 if used > 0 and diff_days >= (MIN_HOURS / 24):
#                     daily_usage    = round(used / diff_days, 2)
#                     estimasi_ready = True
#                     print(f"  → estimasi VALID: {daily_usage} kWh/hari")
#                 else:
#                     reason = "kWh naik (isi token)" if used <= 0 else f"jarak cuma {diff_secs/3600:.1f} jam < {MIN_HOURS} jam"
#                     print(f"  → estimasi DITOLAK: {reason}, pakai default {daily_usage}")

#     days_remaining = round(remaining_kwh / daily_usage, 1) if daily_usage > 0 else 0

#     if not estimasi_ready:
#         status = "SCAN LAGI UNTUK ESTIMASI"
#     elif days_remaining <= 3:
#         status = "SEGERA BELI TOKEN"
#     elif days_remaining <= 7:
#         status = "PERLU PERHATIAN"
#     else:
#         status = "AMAN"

#     return {
#         "daily_usage":    daily_usage,
#         "days_remaining": days_remaining,
#         "status":         status,
#         "estimasi_ready": estimasi_ready,
#     }

from datetime import datetime, timezone

def calculate_prabayar(remaining_kwh, power, last_scan=None):

    def get_default_usage(p):
        if p <= 450:  return 2.0
        if p <= 900:  return 3.5
        if p <= 1300: return 5.2
        if p <= 2200: return 8.5
        if p <= 3500: return 13.0
        if p <= 4400: return 16.5
        return 21.0

    daily_usage    = get_default_usage(power)
    estimasi_ready = False

    if last_scan and "remaining_kwh" in last_scan:
        if last_scan.get("input_type") not in ("token", "token_awal"):
            prev_kwh  = float(last_scan.get("remaining_kwh", 0))
            prev_time = last_scan.get("created_at")

            # =====================================================
            # FIX TIMEZONE — strip timezone info untuk konsistensi
            # =====================================================
            if isinstance(prev_time, str):
                try:
                    prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")
                except:
                    prev_time = None

            if prev_time is not None:
                # Hapus timezone info kalau ada
                if prev_time.tzinfo is None:
                    prev_time = prev_time.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                diff_secs = (now - prev_time).total_seconds()
                diff_days = diff_secs / 86400

                used = prev_kwh - remaining_kwh

                print(f"DEBUG prabayar_service:")
                print(f"  prev_kwh={prev_kwh}, remaining={remaining_kwh}")
                print(f"  prev_time={prev_time}, now={now}")
                print(f"  diff_secs={diff_secs:.1f}, diff_days={diff_days:.4f}")
                print(f"  used={used:.2f}")
                print(f"  input_type={last_scan.get('input_type')}")

                # Minimal 6 jam (0.25 hari) antar scan untuk estimasi valid
                MIN_HOURS = 6
                if used > 0 and diff_days >= (MIN_HOURS / 24):
                    daily_usage    = round(used / diff_days, 2)
                    estimasi_ready = True
                    print(f"  → estimasi VALID: {daily_usage} kWh/hari")
                else:
                    reason = "kWh naik (isi token)" if used <= 0 else f"jarak cuma {diff_secs/3600:.1f} jam < {MIN_HOURS} jam"
                    print(f"  → estimasi DITOLAK: {reason}, pakai default {daily_usage}")

    days_remaining = round(remaining_kwh / daily_usage, 1) if daily_usage > 0 else 0

    if not estimasi_ready:
        status = "SCAN LAGI UNTUK ESTIMASI"
    elif days_remaining <= 3:
        status = "SEGERA BELI TOKEN"
    elif days_remaining <= 7:
        status = "PERLU PERHATIAN"
    else:
        status = "AMAN"

    return {
        "daily_usage":    daily_usage,
        "days_remaining": days_remaining,
        "status":         status,
        "estimasi_ready": estimasi_ready,
    }