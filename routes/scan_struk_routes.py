import os
import re
import cv2
import easyocr
import numpy as np
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from bson import ObjectId
from utils.db import mongo
from utils.ocr_reader import reader

scan_struk_bp = Blueprint("scan_struk", __name__)

# ============================================================
# LOAD OCR (sekali saat server start)
# ============================================================

# reader = easyocr.Reader(
#     ['en'],
#     gpu=False
# )

# ============================================================
# TARIF YANG DIDUKUNG
# ============================================================

KNOWN_TARIFFS_VA = [
    450,
    900,
    1300,
    2200,
    3500,
    4400,
    5500
]

OFFICIAL_NOMINALS = [
    20000,
    50000,
    100000,
    250000,
    500000,
    1000000
]

# ============================================================
# IMAGE PREPROCESS
# ===========================================================
def preprocess(image):   
    h, w = image.shape[:2]
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        image = cv2.resize(
            image, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_AREA
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Sekarang resize 2x ini aman, karena base image sudah dibatasi max 1600px
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11
    )

    return gray

# ============================================================
# OCR
# ============================================================

def read_receipt(image):

    processed = preprocess(image)

    result = reader.readtext(
        processed,
        detail=0,
        paragraph=False
    )

    return result

# ============================================================
# PARSE NOMOR METER
# ============================================================

def parse_meter_number(raw_text):

    patterns = [

        r"(?:ID\s*PEL(?:ANGGAN)?)\s*[:\-]?\s*(\d[\d\s]{8,13})",

        r"(?:NO\.?\s*METER)\s*[:\-]?\s*(\d[\d\s]{8,13})",

        r"(?:NOMOR\s*METER)\s*[:\-]?\s*(\d[\d\s]{8,13})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            raw_text,
            re.IGNORECASE
        )

        if match:

            number = re.sub(
                r"\s",
                "",
                match.group(1)
            )

            return number,"high"

    standalone = re.findall(
        r"\b\d{11,12}\b",
        raw_text
    )

    if standalone:

        return standalone[0],"medium"

    return None,"low"

# ============================================================
# PARSE NOMINAL
# ============================================================

def parse_nominal(raw_text):

    text = raw_text.upper()

    # 1. PRIORITAS PALING TINGGI: JUMLAH TAGIHAN
    match = re.search(r"JUMLAH\s+TAGIHAN\s*RP\.?\s*([\d.,]+)", text)
    if match:
        value = int(re.sub(r"[^\d]", "", match.group(1)))
        return value, "high"

    # 2. PLN PRABAYAR (ini biasanya nominal token asli)
    match = re.search(r"PLN\s+PRABAYAR\s+(\d{5,7})", text)
    if match:
        value = int(match.group(1))
        return value, "high"

    # 3. NOMINAL TOKEN
    match = re.search(r"NOMINAL.*?RP\.?\s*([\d.,]+)", text)
    if match:
        value = int(re.sub(r"[^\d]", "", match.group(1)))
        return value, "medium"

    # 4. FALLBACK: pilih RP TERKECIL (hindari admin & total)
    prices = re.findall(r"RP\.?\s*([\d.,]+)", text)

    candidates = []
    for p in prices:
        val = int(re.sub(r"[^\d]", "", p))

        # filter aneh (admin biasanya kecil, total biasanya beda pola)
        if 20000 <= val <= 1000000:
            candidates.append(val)

    if candidates:
        return min(candidates), "low"

    return None, "low"

# ============================================================
# PARSE TARIF
# ============================================================

def parse_tariff(raw_text):

    m=re.search(

        r"(?:TRF/?DAY|TARIF/?DAYA).*?(\d{3,4})\s*VA",

        raw_text,

        re.IGNORECASE

    )

    if m:

        va=int(m.group(1))

        if va in KNOWN_TARIFFS_VA:

            return f"{va} VA","high"

        return f"{va} VA","medium"

    m=re.search(

        r"\b(\d{3,4})\s*VA\b",

        raw_text,

        re.IGNORECASE

    )

    if m:

        va=int(m.group(1))

        if va in KNOWN_TARIFFS_VA:

            return f"{va} VA","medium"

        return f"{va} VA","low"

    return None,"low"

# ============================================================
# VALIDASI APAKAH STRUK LISTRIK
# ============================================================

def looks_like_receipt(raw_text):

    keywords=[

        "PLN",

        "TOKEN",

        "LISTRIK",

        "KWH",

        "IDPEL",

        "METER",

        "PRABAYAR",

        "TRF",

        "VA"

    ]

    upper=raw_text.upper()

    return any(
        k in upper
        for k in keywords
    )
    
# ============================================================
# ENDPOINT SCAN STRUK
# ============================================================

@scan_struk_bp.route("", methods=["POST"])
def scan_struk():

    try:

        # ==========================================
        # VALIDASI FILE
        # ==========================================

        if "image" not in request.files:

            return jsonify({
                "status": "error",
                "message": "File image tidak ditemukan"
            }),400

        file=request.files["image"]

        if file.filename=="":

            return jsonify({
                "status":"error",
                "message":"File kosong"
            }),400

        # ==========================================
        # BACA IMAGE
        # ==========================================

        image_bytes=np.frombuffer(
            file.read(),
            np.uint8
        )

        image=cv2.imdecode(
            image_bytes,
            cv2.IMREAD_COLOR
        )

        if image is None:

            return jsonify({
                "status":"error",
                "message":"Gambar tidak valid"
            }),400

        # ==========================================
        # OCR
        # ==========================================

        ocr_result=read_receipt(image)

        raw_text="\n".join(ocr_result)

        print("="*60)
        print(raw_text)
        print("="*60)

        # ==========================================
        # VALIDASI STRUK LISTRIK
        # ==========================================

        if not looks_like_receipt(raw_text):

            return jsonify({
                "status":"not_found",
                "message":"Bukan struk token listrik"
            })

        # ==========================================
        # PARSING
        # ==========================================

        meter_number,meter_confidence=parse_meter_number(raw_text)

        nominal,nominal_confidence=parse_nominal(raw_text)

        tariff,tariff_confidence=parse_tariff(raw_text)

        # ==========================================
        # SIMPAN HISTORI PEMBELIAN TOKEN
        # ==========================================

        try:

            mongo.db.scan_struk_history.insert_one({

                # Hasil OCR
                "meter_number": meter_number,
                "nominal": nominal,
                "tariff": tariff,

                # Status token
                # belum_dimasukkan = user belum mengisi token ke meter
                # sudah_dimasukkan = user sudah update sisa kWh setelah isi token
                "status": "belum_dimasukkan",

                # Akan diisi nanti ketika user update sisa kWh
                "remaining_kwh_before": None,
                "remaining_kwh_after": None,

                # Dipakai untuk mengetahui kapan token dibeli
                "purchase_date": datetime.now(timezone.utc),

                # Confidence OCR
                "confidence": {
                    "meter": meter_confidence,
                    "nominal": nominal_confidence,
                    "tariff": tariff_confidence
                },

                "created_at": datetime.now(timezone.utc)

            })

        except Exception as e:

            print("Mongo Error :", e)


        # ==========================================
        # TIDAK ADA DATA YANG BERHASIL DIPARSE
        # ==========================================

        if meter_number is None \
        and nominal is None \
        and tariff is None:

            return jsonify({

                "status":"not_found",

                "message":"Tidak ada data yang berhasil dibaca",

                "result":{

                    "meter_number":{
                        "value":None,
                        "confidence":"low"
                    },

                    "nominal":{
                        "value":None,
                        "confidence":"low"
                    },

                    "tariff":{
                        "value":None,
                        "confidence":"low"
                    }

                }

            })


        # ==========================================
        # SUCCESS
        # ==========================================

        return jsonify({

            "status":"success",

            "message":"Struk berhasil dipindai",

            "ocr_text":ocr_result,

            "result":{

                "meter_number":{
                    "value":meter_number,
                    "confidence":meter_confidence
                },

                "nominal":{
                    "value":nominal,
                    "confidence":nominal_confidence
                },

                "tariff":{
                    "value":tariff,
                    "confidence":tariff_confidence
                }

            }

        })

    except Exception as e:

        import traceback

        traceback.print_exc()

        return jsonify({

            "status":"error",

            "message":str(e)

        }),500    