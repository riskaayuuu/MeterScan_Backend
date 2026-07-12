import cv2
import pytesseract
import numpy as np

# ==========================================================
# OCR: Tesseract (EasyOCR dinonaktifkan — keterbatasan RAM di free tier)
# ==========================================================

# ==========================================================
# PREPROCESS STRUK
# ==========================================================
def preprocess_receipt(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # perbesar supaya OCR lebih jelas
    gray = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC
    )
    # denoise
    gray = cv2.fastNlMeansDenoising(gray)
    # threshold
    gray = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )
    return gray

# ==========================================================
# OCR STRUK
# ==========================================================
def read_receipt(image):
    processed = preprocess_receipt(image)
    print("Original :", image.shape)
    print("Processed:", processed.shape)

    raw_text = pytesseract.image_to_string(processed, lang='ind')
    result = [line.strip() for line in raw_text.split('\n') if line.strip()]

    print(result)
    return result

# ==========================================================
# OCR -> RAW TEXT
# ==========================================================
def receipt_to_text(image):
    result = read_receipt(image)
    raw_text = "\n".join(result)
    return raw_text
    
# import cv2
# import re
# import time
# import numpy as np
# from utils.ocr_reader import reader

# def is_image_sharp(image, threshold=100.0):
#     """
#     Deteksi apakah gambar cukup tajam (tidak blur) menggunakan
#     variance of Laplacian. Semakin rendah nilainya, semakin blur.
#     """
#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#     laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
#     return laplacian_var >= threshold, laplacian_var

# # ============================================================
# # AUTO CROP LCD
# # ============================================================

# def order_points(pts):
#     """Urutkan 4 titik: top-left, top-right, bottom-right, bottom-left"""
#     rect = np.zeros((4, 2), dtype="float32")
#     s = pts.sum(axis=1)
#     rect[0] = pts[np.argmin(s)]
#     rect[2] = pts[np.argmax(s)]

#     diff = np.diff(pts, axis=1)
#     rect[1] = pts[np.argmin(diff)]
#     rect[3] = pts[np.argmax(diff)]

#     return rect


# def four_point_transform(image, pts):
#     """Perspective transform supaya LCD jadi lurus (tidak miring)"""
#     rect = order_points(pts)
#     (tl, tr, br, bl) = rect

#     widthA = np.linalg.norm(br - bl)
#     widthB = np.linalg.norm(tr - tl)
#     maxWidth = max(int(widthA), int(widthB))

#     heightA = np.linalg.norm(tr - br)
#     heightB = np.linalg.norm(tl - bl)
#     maxHeight = max(int(heightA), int(heightB))

#     dst = np.array([
#         [0, 0],
#         [maxWidth - 1, 0],
#         [maxWidth - 1, maxHeight - 1],
#         [0, maxHeight - 1]
#     ], dtype="float32")

#     M = cv2.getPerspectiveTransform(rect, dst)
#     warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

#     return warped


# def find_lcd_candidates(image):
#     """
#     Cari SEMUA kandidat kontur yang mungkin LCD, diurutkan dari skor tertinggi.
#     Return list of dict: {score, contour, x, y, w, h, dominant_ratio, polarity}

#     Kenapa return semua (bukan cuma 1): supaya auto_crop_lcd() bisa VERIFIKASI
#     tiap kandidat (cek beneran ada digit di dalamnya atau tidak) sebelum commit,
#     bukan asal percaya skor tertinggi. Ini jauh lebih tahan terhadap variasi
#     jarak foto, sudut, dan model meteran yang beda-beda.
#     """

#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#     blur = cv2.GaussianBlur(gray, (5, 5), 0)

#     img_h, img_w = image.shape[0], image.shape[1]
#     img_area = img_h * img_w

#     all_candidates = []

#     # --- MULTI-PARAMETER Canny ---
#     # Coba beberapa kombinasi threshold Canny + kernel dilasi, karena kontras
#     # tepi LCD bisa beda jauh tergantung jarak foto, pencahayaan, dan glare.
#     # Satu set parameter saja sering gagal di kondisi tertentu.
#     canny_configs = [
#         (30, 150, 5, 2),   # default (jarak sedang, cahaya normal)
#         (15, 100, 5, 3),   # lebih sensitif (kontras rendah/jauh/buram)
#         (50, 200, 3, 1),   # lebih ketat (kontras tinggi/dekat)
#     ]

#     seen_boxes = set()  # hindari duplikat kandidat antar config

#     for (low, high, ksize, iters) in canny_configs:
#         edged = cv2.Canny(blur, low, high)
#         kernel = np.ones((ksize, ksize), np.uint8)
#         edged = cv2.dilate(edged, kernel, iterations=iters)
#         edged = cv2.erode(edged, kernel, iterations=max(1, iters - 1))

#         contours, _ = cv2.findContours(
#             edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
#         )

#         for c in contours:
#             area = cv2.contourArea(c)

#             if area < img_area * 0.015 or area > img_area * 0.5:
#                 continue

#             x, y, w, h = cv2.boundingRect(c)

#             if h == 0:
#                 continue

#             box_key = (x // 10, y // 10, w // 10, h // 10)  # toleransi dedup
#             if box_key in seen_boxes:
#                 continue

#             aspect = w / float(h)

#             if not (1.2 < aspect < 6.5):
#                 continue

#             pad_x = int(w * 0.08)
#             pad_y = int(h * 0.08)
#             inner = gray[y + pad_y: y + h - pad_y, x + pad_x: x + w - pad_x]

#             if inner.size == 0:
#                 continue

#             white_ratio = np.count_nonzero(inner > 170) / float(inner.size)
#             black_ratio = np.count_nonzero(inner < 70) / float(inner.size)
#             dominant_ratio = max(white_ratio, black_ratio)
#             polarity = "terang" if white_ratio >= black_ratio else "gelap"

#             if dominant_ratio < 0.45:
#                 continue

#             center_y_norm = (y + h / 2.0) / float(img_h)

#             dominance_score = dominant_ratio
#             aspect_score = 1.0 - min(abs(aspect - 3.0) / 3.0, 1.0)
#             position_score = 1.0 - center_y_norm

#             score = (dominance_score * 0.55) + (position_score * 0.30) + (aspect_score * 0.15)

#             seen_boxes.add(box_key)
#             all_candidates.append({
#                 "score": score, "contour": c,
#                 "x": x, "y": y, "w": w, "h": h,
#                 "dominant_ratio": dominant_ratio, "polarity": polarity,
#             })

#     all_candidates.sort(key=lambda d: d["score"], reverse=True)
#     return all_candidates


# def _verify_candidate_has_digits(image, cand, min_boxes=2):
#     """
#     VERIFIKASI: crop kandidat ini, cek apakah beneran ada bentuk digit
#     di dalamnya (bukan cuma percaya skor). Return True/False.
#     """
#     x, y, w, h = cand["x"], cand["y"], cand["w"], cand["h"]

#     crop = image[y:y + h, x:x + w]
#     if crop.size == 0:
#         return False

#     try:
#         gray_c = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
#         # samakan skala biar deteksi digit konsisten apapun ukuran kandidat
#         target_w = 500
#         scale = target_w / float(w) if w > 0 else 1.0
#         scale = max(0.3, min(scale, 4.0))
#         gray_c = cv2.resize(gray_c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
#         blur_c = cv2.GaussianBlur(gray_c, (5, 5), 0)

#         for mode in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
#             _, th = cv2.threshold(blur_c, 0, 255, mode + cv2.THRESH_OTSU)
#             kernel = np.ones((3, 3), np.uint8)
#             th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
#             boxes = _find_digit_boxes(th)
#             if len(boxes) >= min_boxes:
#                 return True

#         return False
#     except Exception:
#         return False


# def find_lcd_contour(image):
#     """
#     Wrapper backward-compatible: return kandidat TERBAIK yang LOLOS VERIFIKASI
#     (bukan cuma skor tertinggi tanpa dicek). Kalau tidak ada yang lolos
#     verifikasi, kembalikan kandidat skor tertinggi apa adanya (better than nothing).
#     """
#     candidates = find_lcd_candidates(image)

#     if not candidates:
#         return None

#     # Coba tiap kandidat dari skor tertinggi, VERIFIKASI beneran ada digit
#     for cand in candidates[:8]:  # cukup cek 8 kandidat teratas
#         if _verify_candidate_has_digits(image, cand):
#             x, y, w, h = cand["x"], cand["y"], cand["w"], cand["h"]
#             print(f"[LCD DETECT] TERVERIFIKASI ada digit! score={cand['score']:.3f}, "
#                   f"dominant_ratio={cand['dominant_ratio']:.2f} ({cand['polarity']}), "
#                   f"pos=({x},{y}), size=({w}x{h})")

#             peri = cv2.arcLength(cand["contour"], True)
#             approx = cv2.approxPolyDP(cand["contour"], 0.02 * peri, True)
#             if len(approx) == 4:
#                 return approx.reshape(4, 2)
#             return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])

#     # Tidak ada yang lolos verifikasi -> pakai skor tertinggi apa adanya
#     print("[LCD DETECT] Tidak ada kandidat lolos verifikasi digit, "
#           "pakai skor tertinggi tanpa verifikasi (fallback).")
#     best = candidates[0]
#     x, y, w, h = best["x"], best["y"], best["w"], best["h"]

#     peri = cv2.arcLength(best["contour"], True)
#     approx = cv2.approxPolyDP(best["contour"], 0.02 * peri, True)
#     if len(approx) == 4:
#         return approx.reshape(4, 2)
#     return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])


# def auto_crop_lcd(image, padding=10):
#     """
#     Deteksi & crop area LCD dari foto.
#     Kalau gagal deteksi, return gambar asli (fallback).
#     """

#     pts = find_lcd_contour(image)

#     if pts is None:
#         print("LCD tidak terdeteksi, pakai gambar asli.")
#         cv2.imwrite('debug_crop_fallback.jpg', image)
#         return image

#     warped = four_point_transform(image, pts.astype("float32"))

#     # tambah padding kecil biar digit di pinggir tidak terpotong
#     h, w = warped.shape[:2]
#     if padding > 0 and h > padding * 2 and w > padding * 2:
#         warped = warped[padding:h - padding, padding:w - padding]

#     cv2.imwrite('debug_crop.jpg', warped)
#     return warped


# # ============================================================
# # SEVEN-SEGMENT DECODER (deteksi langsung batang segmen, BUKAN OCR generik)
# # ============================================================
# #
# # Kenapa perlu ini: EasyOCR (dan OCR generik lainnya) dilatih untuk membaca
# # font tulisan biasa (huruf/angka bersambung), BUKAN digit 7-segment yang
# # dibentuk dari batang-batang terpisah. Itu sebabnya OCR generik sering
# # "mengarang" digit acak di layar LCD (segmen tak nyala dikira karakter,
# # celah antar segmen dikira pemisah angka, dst).
# #
# # Pendekatan ini membaca LANGSUNG pola segmen mana yang menyala di tiap
# # digit (mirip cara manusia baca jam digital), lalu dicocokkan ke tabel
# # kombinasi standar 7-segment. Jauh lebih akurat untuk kasus ini.

# # Urutan segmen: (top, top-left, top-right, middle, bottom-left, bottom-right, bottom)
# SEVEN_SEG_LOOKUP = {
#     (1, 1, 1, 0, 1, 1, 1): '0',
#     (0, 0, 1, 0, 0, 1, 0): '1',
#     (1, 0, 1, 1, 1, 0, 1): '2',
#     (1, 0, 1, 1, 0, 1, 1): '3',
#     (0, 1, 1, 1, 0, 1, 0): '4',
#     (1, 1, 0, 1, 0, 1, 1): '5',
#     (1, 1, 0, 1, 1, 1, 1): '6',
#     (1, 0, 1, 0, 0, 1, 0): '7',
#     (1, 1, 1, 1, 1, 1, 1): '8',
#     (1, 1, 1, 1, 0, 1, 1): '9',
# }


# def _find_digit_boxes(thresh_img):
#     """
#     Cari kotak-kotak individual digit dari gambar biner (digit = putih di atas hitam).
#     Return list (x, y, w, h) terurut kiri->kanan.
#     """

#     contours, _ = cv2.findContours(
#         thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
#     )

#     img_h, img_w = thresh_img.shape[:2]

#     boxes = []
#     for c in contours:
#         x, y, w, h = cv2.boundingRect(c)

#         # digit LCD biasanya cukup tinggi relatif ke tinggi crop,
#         # dan tidak terlalu tipis/lebar (buang noise garis atau titik kecil)
#         if h < img_h * 0.35:
#             continue
#         if w < 4 or h < 10:
#             continue
#         if w > h * 1.3:  # terlalu lebar untuk 1 digit (kemungkinan noise gabungan)
#             continue

#         boxes.append((x, y, w, h))

#     boxes.sort(key=lambda b: b[0])  # urut kiri -> kanan
#     return boxes


# def _decode_single_digit(roi):
#     """
#     roi: gambar biner satu digit (putih=nyala di atas hitam), sudah di-resize seragam.
#     Return karakter digit ('0'-'9') atau None kalau tidak match pola manapun.
#     """

#     h, w = roi.shape[:2]

#     # Definisikan 7 area segmen sebagai fraksi dari bounding box digit
#     # (top, top-left, top-right, middle, bottom-left, bottom-right, bottom)
#     def region_on(y0, y1, x0, x1):
#         y0, y1 = int(y0 * h), int(y1 * h)
#         x0, x1 = int(x0 * w), int(x1 * w)
#         area = roi[y0:y1, x0:x1]
#         if area.size == 0:
#             return 0
#         # "nyala" kalau proporsi piksel putih di region itu cukup tinggi
#         white_ratio = np.count_nonzero(area) / float(area.size)
#         return 1 if white_ratio > 0.45 else 0

#     top          = region_on(0.00, 0.18, 0.20, 0.80)
#     top_left     = region_on(0.12, 0.50, 0.00, 0.30)
#     top_right    = region_on(0.12, 0.50, 0.70, 1.00)
#     middle       = region_on(0.42, 0.58, 0.15, 0.85)
#     bottom_left  = region_on(0.50, 0.88, 0.00, 0.30)
#     bottom_right = region_on(0.50, 0.88, 0.70, 1.00)
#     bottom       = region_on(0.82, 1.00, 0.20, 0.80)

#     pattern = (top, top_left, top_right, middle, bottom_left, bottom_right, bottom)

#     return SEVEN_SEG_LOOKUP.get(pattern, None)


# def decode_seven_segment(lcd_image):
#     """
#     Ambil gambar hasil crop LCD (BGR), coba decode langsung sebagai digit 7-segment.
#     Return string angka mentah (misal "7738" atau "" kalau gagal), plus jumlah digit terdeteksi.

#     PENTING: seluruh isi fungsi dibungkus try-except — kalau ada error internal
#     apapun (misal gambar terlalu besar/aneh krn auto-crop gagal), fungsi ini
#     TIDAK BOLEH bikin request crash 500. Cukup return kosong, biar
#     scan_meter_image jatuh ke fallback EasyOCR seperti biasa.
#     """

#     try:
#         h0, w0 = lcd_image.shape[:2]

#         # --- Resize ADAPTIF, bukan selalu x3 ---
#         # Kalau crop LCD gagal (fallback ke gambar asli yang besar),
#         # JANGAN dikali 3 lagi -> bisa jadi raksasa & berat/gagal.
#         # Target: lebar akhir sekitar 600-900px (cukup buat deteksi digit).
#         target_width = 700
#         scale = target_width / float(w0)
#         scale = max(0.3, min(scale, 3.0))  # batasi supaya tidak ekstrem

#         gray = cv2.cvtColor(lcd_image, cv2.COLOR_BGR2GRAY)
#         gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

#         blur = cv2.GaussianBlur(gray, (5, 5), 0)

#         # Otsu threshold, coba dua arah (LCD kadang digit gelap di background terang,
#         # kadang sebaliknya tergantung tipe backlight)
#         _, thresh_dark_on_light = cv2.threshold(
#             blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
#         )
#         _, thresh_light_on_dark = cv2.threshold(
#             blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
#         )

#         best_result = ""
#         best_count = 0

#         for thresh in (thresh_dark_on_light, thresh_light_on_dark):

#             kernel = np.ones((3, 3), np.uint8)
#             thresh_clean = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

#             boxes = _find_digit_boxes(thresh_clean)

#             if len(boxes) < 2:
#                 continue

#             digits = []
#             for (x, y, w, h) in boxes:
#                 roi = thresh_clean[y:y + h, x:x + w]
#                 roi = cv2.resize(roi, (60, 100), interpolation=cv2.INTER_NEAREST)
#                 d = _decode_single_digit(roi)
#                 digits.append(d if d is not None else '?')

#             result = "".join(digits)
#             confident_digit_count = sum(1 for d in digits if d != '?')

#             if confident_digit_count > best_count:
#                 best_count = confident_digit_count
#                 best_result = result

#         return best_result, best_count

#     except Exception as e:
#         # JANGAN biarkan error di sini bikin request 500 -
#         # cukup log & kembalikan kosong, biar fallback ke EasyOCR jalan
#         print(f"[SEVEN-SEG] ERROR internal, fallback ke EasyOCR. Detail: {e}")
#         return "", 0


# # ============================================================
# # PREPROCESS IMAGE (beberapa varian, dipilih yang confidence terbaik)
# # ============================================================

# def get_preprocess_variants(image):
#     """
#     Return list gambar hasil preprocessing dengan beberapa metode berbeda.
#     OCR akan dijalankan ke semua varian, hasil terbaik yang dipakai.
#     """

#     variants = []

#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

#     # --- Resize ADAPTIF ---
#     # Target: lebar akhir sekitar 900-1200px (cukup untuk OCR digit, tidak membebani)
#     # Kalau gambar sudah besar, JANGAN dikali 4 lagi -> justru bikin lambat/OOM
#     h, w = gray.shape[:2]
#     target_width = 1000

#     scale = target_width / float(w)
#     # batasi scale supaya tidak terlalu ekstrem (min 0.5x, max 4x)
#     scale = max(0.5, min(scale, 4.0))

#     gray = cv2.resize(
#         gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
#     )

#     clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
#     gray_clahe = clahe.apply(gray)

#     # Varian 1: grayscale + CLAHE saja (tanpa threshold)
#     smooth = cv2.bilateralFilter(gray_clahe, 5, 50, 50)
#     cv2.imwrite('debug_variant1_clahe.jpg', smooth)
#     variants.append(smooth)

#     # Varian 2: adaptive threshold (versi lama)
#     median = cv2.medianBlur(gray_clahe, 3)
#     thresh_adapt = cv2.adaptiveThreshold(
#         median,
#         255,
#         cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
#         cv2.THRESH_BINARY,
#         31,
#         5
#     )
#     kernel = np.ones((2, 2), np.uint8)
#     thresh_adapt = cv2.morphologyEx(thresh_adapt, cv2.MORPH_CLOSE, kernel)
#     cv2.imwrite('debug_variant2_adaptive.jpg', thresh_adapt)
#     variants.append(thresh_adapt)

#     # Varian 3: otsu threshold
#     _, thresh_otsu = cv2.threshold(
#         gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
#     )
#     cv2.imwrite('debug_variant3_otsu.jpg', thresh_otsu)
#     variants.append(thresh_otsu)

#     return variants


# # ============================================================
# # VALIDASI NILAI METER
# # ============================================================

# def is_plausible_kwh(value):

#     if value is None:
#         return False

#     if value < 0:
#         return False

#     # Meter rumah normal
#     if value > 99999:
#         return False

#     return True


# # ============================================================
# # PARSING OCR
# # ============================================================

# # def extract_meter_value(text):
# #     """
# #     Return tuple (value, reliability) atau (None, None) kalau tidak ketemu.

# #     reliability:
# #       0 = titik/koma desimal terbaca eksplisit oleh OCR (paling reliable)
# #       1 = fallback: angka polos ditebak posisi desimalnya (kurang reliable)
# #     """

# #     text = text.replace(" ", "")

# #     # ------------------------
# #     # GUARD PALING PENTING — JANGAN DIHAPUS LAGI!
# #     # Kalau teks OCR keseluruhan kepanjangan, itu noise/garbage
# #     # (background/tekstur kebaca sebagai digit acak), BUKAN bacaan meter asli.
# #     # Meter kWh normal cuma sekitar 4-8 karakter termasuk titik/koma.
# #     # Tanpa guard ini, string sampah 20-60 karakter bisa "kebetulan"
# #     # mengandung pola X.XX di tengahnya dan lolos sebagai reliability=0.
# #     # ------------------------

# #     if len(text) > 15:
# #         return None, None

# #     # ------------------------
# #     # 1234.56  (titik eksplisit -> reliable)
# #     # ------------------------

# #     match = re.findall(r"\d{1,5}\.\d{2}", text)

# #     if match:
# #         return float(match[0]), 0

# #     # ------------------------
# #     # 1234,56  (koma eksplisit -> reliable)
# #     # ------------------------

# #     match = re.findall(r"\d{1,5},\d{2}", text)

# #     if match:
# #         return float(match[0].replace(",", ".")), 0

# #     # ------------------------
# #     # 123456
# #     # -> 1234.56  (tebakan, kurang reliable)
# #     # ------------------------

# #     # Cek dulu apakah ada run digit yang mencurigakan panjang (>7 digit nyambung)
# #     # -> biasanya tanda noise OCR (digit nyambung acak), bukan angka meter asli
# #     raw_digit_runs = re.findall(r"\d+", text)
# #     if any(len(run) > 7 for run in raw_digit_runs):
# #         return None, None

# #     match = re.findall(r"\d{4,7}", text)

# #     if match:

# #         number = match[0]

# #         integer = number[:-2]

# #         decimal = number[-2:]

# #         return float(f"{integer}.{decimal}"), 1

# #     return None, None

# # INI YANG BARU DIEDIT
# def extract_meter_value(text, has_decimal=True):
#     text = text.replace(" ", "")

#     if len(text) > 15:
#         return None, None

#     if has_decimal:
#         # ------------------------
#         # MODE PRABAYAR: format X.XX (ada desimal)
#         # ------------------------
#         match = re.findall(r"\d{1,5}\.\d{2}", text)
#         if match:
#             return float(match[0]), 0

#         match = re.findall(r"\d{1,5},\d{2}", text)
#         if match:
#             return float(match[0].replace(",", ".")), 0

#         raw_digit_runs = re.findall(r"\d+", text)
#         if any(len(run) > 7 for run in raw_digit_runs):
#             return None, None

#         match = re.findall(r"\d{4,7}", text)
#         if match:
#             number = match[0]
#             integer = number[:-2]
#             decimal = number[-2:]
#             return float(f"{integer}.{decimal}"), 1

#         return None, None

#     else:
#         # ------------------------
#         # MODE PASCABAYAR: angka BULAT, TANPA desimal
#         # ------------------------
#         clean = text.replace(".", "").replace(",", "")

#         raw_digit_runs = re.findall(r"\d+", clean)
#         if any(len(run) > 8 for run in raw_digit_runs):
#             return None, None

#         match = re.findall(r"\d{3,7}", clean)
#         if match:
#             number = match[0]
#             return float(number), 0

#         return None, None
# # ============================================================
# # OCR UTAMA
# # ============================================================

# def run_ocr(image_variant):
#     """Jalankan OCR pada satu varian gambar, return (combined_text, avg_conf, raw_results)"""

#     results = reader.readtext(
#         image_variant,
#         allowlist="0123456789.,",
#         detail=1,
#         paragraph=False,
#         decoder="greedy"  # jauh lebih cepat dari beamsearch, cukup akurat untuk digit
#     )

#     if not results:
#         return "", 0.0, []

#     # Urutkan berdasarkan posisi kiri -> kanan (bukan confidence)
#     # supaya digit yang terpecah bisa digabung sesuai urutan asli di layar
#     results_by_pos = sorted(results, key=lambda r: r[0][0][0])

#     combined_text = "".join(text for _, text, _ in results_by_pos)
#     avg_conf = sum(c for _, _, c in results_by_pos) / len(results_by_pos)

#     return combined_text, avg_conf, results

# def scan_meter_image(image, has_decimal=True):
#     t_start = time.time() 
#     if image is None:
#         raise ValueError("Image kosong")

#     is_sharp, sharpness_score = is_image_sharp(image)
#     print(f"[BLUR CHECK] sharpness_score={sharpness_score:.1f} (min: 100)")
    
#     if not is_sharp:
#         print("[BLUR CHECK] Foto terlalu blur, minta user foto ulang")
#         return None

#     # === STEP 0: Downscale awal kalau gambar terlalu besar ===
#     h0, w0 = image.shape[:2]
#     max_dim = 1600
#     if max(h0, w0) > max_dim:
#         scale0 = max_dim / float(max(h0, w0))
#         image = cv2.resize(
#             image, None, fx=scale0, fy=scale0, interpolation=cv2.INTER_AREA
#         )
#         print(f"Downscale awal: {w0}x{h0} -> {image.shape[1]}x{image.shape[0]}")

#     # === STEP 1: Auto crop area LCD ===
#     cropped = auto_crop_lcd(image)
#     print(f"[TIMING] auto_crop_lcd: {time.time() - t_start:.2f}s")

#     # === STEP 2: METODE UTAMA — segment-based decoder ===
#     raw_digits, confident_count = decode_seven_segment(cropped)
#     print(f"[SEVEN-SEG] raw='{raw_digits}' confident_digits={confident_count}")

#     if confident_count >= 3 and '?' not in raw_digits:
#         if has_decimal:
#             # asumsi 2 digit terakhir adalah desimal (format prabayar: XXX.XX)
#             if len(raw_digits) >= 3:
#                 integer_part = raw_digits[:-2]
#                 decimal_part = raw_digits[-2:]
#                 value = float(f"{integer_part}.{decimal_part}")

#                 if is_plausible_kwh(value):
#                     print(f"[SEVEN-SEG] DIPILIH (metode utama): {value}")
#                     return round(value, 2)
#         else:
#             # pascabayar: angka bulat, TANPA potong 2 digit terakhir
#             value = float(raw_digits)
#             if is_plausible_kwh(value):
#                 print(f"[SEVEN-SEG] DIPILIH (metode utama, tanpa desimal): {value}")
#                 return round(value, 2)

#     print("[SEVEN-SEG] gagal/tidak yakin, fallback ke EasyOCR...")
#     if reader is None:
#         print("[INFO] EasyOCR dinonaktifkan (RAM terbatas), skip fallback.")
#         return None

#     # === STEP 3: FALLBACK — EasyOCR ===
#     variants = get_preprocess_variants(cropped)
#     candidates = []
#     EARLY_EXIT_CONF = 0.5

#     for i, v in enumerate(variants):
#         t_variant = time.time()
#         combined_text, avg_conf, raw_results = run_ocr(v)
#         print(f"[TIMING] variant {i}: {time.time() - t_variant:.2f}s")

#         if not combined_text:
#             continue

#         print("OCR RAW:", combined_text, "| conf:", round(avg_conf, 3))

#         value, reliability = extract_meter_value(combined_text, has_decimal=has_decimal)

#         if is_plausible_kwh(value):
#             candidates.append((value, reliability, avg_conf, combined_text))

#         for _, text, conf in raw_results:
#             frag_value, frag_reliability = extract_meter_value(text, has_decimal=has_decimal)
#             if is_plausible_kwh(frag_value):
#                 candidates.append((frag_value, frag_reliability, conf, text))

#         if candidates:
#             best_so_far = sorted(candidates, key=lambda c: (c[1], -c[2]))[0]
#             if best_so_far[1] == 0 and best_so_far[2] >= EARLY_EXIT_CONF:
#                 print(f"[EARLY EXIT] varian {i} sudah cukup baik, skip sisanya")
#                 break

#     print(f"[TIMING] total sebelum pilih hasil: {time.time() - t_start:.2f}s")

#     if candidates:
#         best = sorted(candidates, key=lambda c: (c[1], -c[2]))[0]
#         print(
#             "DIPILIH (fallback EasyOCR):", best[3],
#             "-> value:", best[0],
#             "| reliability:", best[1],
#             "| conf:", round(best[2], 3)
#         )
#         return round(best[0], 2)

#     return None
