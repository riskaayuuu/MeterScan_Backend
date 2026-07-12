# INI YANG BARU DIEDIT
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mongo
from datetime import datetime

notifikasi_bp = Blueprint("notifikasi", __name__)


@notifikasi_bp.route("/", methods=["GET"])
@jwt_required()
def get_notifikasi():
    try:
        user_id = get_jwt_identity()
        notif_type = request.args.get("type")  # 'prabayar' / 'pascabayar' / None (semua)
        notifikasi = []

        # =====================================================
        # NOTIFIKASI PRABAYAR
        # =====================================================
        if notif_type is None or notif_type == "prabayar":

            scan_prabayar = mongo.db.scan_history.find_one(
                {"user_id": user_id, "type": "prabayar"},
                sort=[("created_at", -1)]
            )

            if scan_prabayar:
                sisa_kwh       = scan_prabayar.get("remaining_kwh", 0)
                days_remaining = scan_prabayar.get("days_remaining", 0)
                estimasi_ready = scan_prabayar.get("input_type") not in ("token", "token_awal")

                if days_remaining <= 3 and estimasi_ready:
                    notifikasi.append({
                        "type":  "prabayar",
                        "title": "⚠️ Token Hampir Habis!",
                        "desc":  f"Sisa token {sisa_kwh} kWh, diperkirakan habis dalam {round(days_remaining, 1)} hari lagi. Segera beli token!",
                        "icon":  "warning",
                        "color": 0xFFE53935,
                        "time":  datetime.utcnow().strftime("%d %b %Y")
                    })
                elif days_remaining <= 7 and estimasi_ready:
                    notifikasi.append({
                        "type":  "prabayar",
                        "title": "🔔 Sisa Token Menipis",
                        "desc":  f"Sisa token {sisa_kwh} kWh, diperkirakan habis dalam {round(days_remaining, 1)} hari lagi.",
                        "icon":  "info",
                        "color": 0xFFFF9800,
                        "time":  datetime.utcnow().strftime("%d %b %Y")
                    })
                else:
                    notifikasi.append({
                        "type":  "prabayar",
                        "title": "✅ Token Aman",
                        "desc":  f"Sisa token {sisa_kwh} kWh" + (
                            f", cukup untuk {round(days_remaining, 1)} hari lagi."
                            if estimasi_ready else ". Scan lagi untuk estimasi hari."
                        ),
                        "icon":  "check",
                        "color": 0xFF4CAF50,
                        "time":  datetime.utcnow().strftime("%d %b %Y")
                    })

        # =====================================================
        # NOTIFIKASI PASCABAYAR
        # (data dari collection meter_predictions, bukan scan_history)
        # =====================================================
        if notif_type is None or notif_type == "pascabayar":

            terakhir_pasca = mongo.db.meter_predictions.find_one(
                {"user_id": user_id},
                sort=[("created_at", -1)]
            )

            meter_awal = mongo.db.meter_predictions.find_one(
                {"user_id": user_id, "is_first": True}
            )

            if terakhir_pasca and meter_awal:
                estimasi = terakhir_pasca.get("estimasi_tagihan", 0)
                budget   = meter_awal.get("budget", 0)

                if budget > 0:
                    progress = estimasi / budget

                    if progress >= 1.0:
                        notifikasi.append({
                            "type":  "pascabayar",
                            "title": "🚨 Budget Terlampaui!",
                            "desc":  f"Estimasi tagihan bulan ini Rp {int(estimasi):,} melebihi budget Rp {int(budget):,}.",
                            "icon":  "warning",
                            "color": 0xFFE53935,
                            "time":  datetime.utcnow().strftime("%d %b %Y")
                        })
                    elif progress >= 0.8:
                        notifikasi.append({
                            "type":  "pascabayar",
                            "title": "⚠️ Mendekati Batas Budget",
                            "desc":  f"Pemakaian sudah {round(progress*100)}% dari budget. Estimasi tagihan Rp {int(estimasi):,}.",
                            "icon":  "trending_up",
                            "color": 0xFFFF9800,
                            "time":  datetime.utcnow().strftime("%d %b %Y")
                        })
                    else:
                        notifikasi.append({
                            "type":  "pascabayar",
                            "title": "✅ Pemakaian Normal",
                            "desc":  f"Estimasi tagihan bulan ini Rp {int(estimasi):,}. Masih dalam batas budget.",
                            "icon":  "check",
                            "color": 0xFF4CAF50,
                            "time":  datetime.utcnow().strftime("%d %b %Y")
                        })
                else:
                    notifikasi.append({
                        "type":  "pascabayar",
                        "title": "📊 Info Tagihan",
                        "desc":  f"Estimasi tagihan bulan ini Rp {int(estimasi):,}. Set budget bulanan untuk pantau lebih detail.",
                        "icon":  "info",
                        "color": 0xFF2196F3,
                        "time":  datetime.utcnow().strftime("%d %b %Y")
                    })

        # =====================================================
        # KALAU TIDAK ADA DATA SAMA SEKALI
        # =====================================================
        if not notifikasi:
            if notif_type == "pascabayar":
                pesan = "Input meter awal untuk mulai melihat prediksi tagihan."
            else:
                pesan = "Scan meter atau input token untuk mulai monitoring."

            notifikasi.append({
                "type":  notif_type or "info",
                "title": "👋 Mulai Monitoring",
                "desc":  pesan,
                "icon":  "info",
                "color": 0xFF2196F3,
                "time":  datetime.utcnow().strftime("%d %b %Y")
            })

        return jsonify({
            "status": "success",
            "data":   notifikasi
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status":  "error",
            "message": str(e)
        }), 500