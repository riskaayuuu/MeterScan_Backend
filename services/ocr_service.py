import cv2
import re
import time
import numpy as np
import pytesseract
from utils.ocr_reader import reader

# ============================================================
# BLUR CHECK
# ============================================================
def is_image_sharp(image, threshold=100.0):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var >= threshold, laplacian_var

# ============================================================
# AUTO CROP LCD
# ============================================================
def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0], [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def find_lcd_candidates(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    img_h, img_w = image.shape[0], image.shape[1]
    img_area = img_h * img_w
    all_candidates = []
    canny_configs = [
        (30, 150, 5, 2),
        (15, 100, 5, 3),
        (50, 200, 3, 1),
    ]
    seen_boxes = set()
    for (low, high, ksize, iters) in canny_configs:
        edged = cv2.Canny(blur, low, high)
        kernel = np.ones((ksize, ksize), np.uint8)
        edged = cv2.dilate(edged, kernel, iterations=iters)
        edged = cv2.erode(edged, kernel, iterations=max(1, iters - 1))
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < img_area * 0.015 or area > img_area * 0.5:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h == 0:
                continue
            box_key = (x // 10, y // 10, w // 10, h // 10)
            if box_key in seen_boxes:
                continue
            aspect = w / float(h)
            if not (1.2 < aspect < 6.5):
                continue
            pad_x = int(w * 0.08)
            pad_y = int(h * 0.08)
            inner = gray[y + pad_y: y + h - pad_y, x + pad_x: x + w - pad_x]
            if inner.size == 0:
                continue
            white_ratio = np.count_nonzero(inner > 170) / float(inner.size)
            black_ratio = np.count_nonzero(inner < 70) / float(inner.size)
            dominant_ratio = max(white_ratio, black_ratio)
            polarity = "terang" if white_ratio >= black_ratio else "gelap"
            if dominant_ratio < 0.45:
                continue
            center_y_norm = (y + h / 2.0) / float(img_h)
            dominance_score = dominant_ratio
            aspect_score = 1.0 - min(abs(aspect - 3.0) / 3.0, 1.0)
            position_score = 1.0 - center_y_norm
            score = (dominance_score * 0.55) + (position_score * 0.30) + (aspect_score * 0.15)
            seen_boxes.add(box_key)
            all_candidates.append({
                "score": score, "contour": c,
                "x": x, "y": y, "w": w, "h": h,
                "dominant_ratio": dominant_ratio, "polarity": polarity,
            })
    all_candidates.sort(key=lambda d: d["score"], reverse=True)
    return all_candidates

def _verify_candidate_has_digits(image, cand, min_boxes=2):
    x, y, w, h = cand["x"], cand["y"], cand["w"], cand["h"]
    crop = image[y:y + h, x:x + w]
    if crop.size == 0:
        return False
    try:
        gray_c = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        target_w = 500
        scale = target_w / float(w) if w > 0 else 1.0
        scale = max(0.3, min(scale, 4.0))
        gray_c = cv2.resize(gray_c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        blur_c = cv2.GaussianBlur(gray_c, (5, 5), 0)
        for mode in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
            _, th = cv2.threshold(blur_c, 0, 255, mode + cv2.THRESH_OTSU)
            kernel = np.ones((3, 3), np.uint8)
            th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
            boxes = _find_digit_boxes(th)
            if len(boxes) >= min_boxes:
                return True
        return False
    except Exception:
        return False

def find_lcd_contour(image):
    candidates = find_lcd_candidates(image)
    if not candidates:
        return None
    for cand in candidates[:8]:
        if _verify_candidate_has_digits(image, cand):
            x, y, w, h = cand["x"], cand["y"], cand["w"], cand["h"]
            peri = cv2.arcLength(cand["contour"], True)
            approx = cv2.approxPolyDP(cand["contour"], 0.02 * peri, True)
            if len(approx) == 4:
                return approx.reshape(4, 2)
            return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])
    best = candidates[0]
    x, y, w, h = best["x"], best["y"], best["w"], best["h"]
    peri = cv2.arcLength(best["contour"], True)
    approx = cv2.approxPolyDP(best["contour"], 0.02 * peri, True)
    if len(approx) == 4:
        return approx.reshape(4, 2)
    return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])

def auto_crop_lcd(image, padding=10):
    pts = find_lcd_contour(image)
    if pts is None:
        return image
    warped = four_point_transform(image, pts.astype("float32"))
    h, w = warped.shape[:2]
    if padding > 0 and h > padding * 2 and w > padding * 2:
        warped = warped[padding:h - padding, padding:w - padding]
    return warped

# ============================================================
# SEVEN-SEGMENT DECODER
# ============================================================
SEVEN_SEG_LOOKUP = {
    (1, 1, 1, 0, 1, 1, 1): '0',
    (0, 0, 1, 0, 0, 1, 0): '1',
    (1, 0, 1, 1, 1, 0, 1): '2',
    (1, 0, 1, 1, 0, 1, 1): '3',
    (0, 1, 1, 1, 0, 1, 0): '4',
    (1, 1, 0, 1, 0, 1, 1): '5',
    (1, 1, 0, 1, 1, 1, 1): '6',
    (1, 0, 1, 0, 0, 1, 0): '7',
    (1, 1, 1, 1, 1, 1, 1): '8',
    (1, 1, 1, 1, 0, 1, 1): '9',
}

def _find_digit_boxes(thresh_img):
    contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_h, img_w = thresh_img.shape[:2]
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h < img_h * 0.35:
            continue
        if w < 4 or h < 10:
            continue
        if w > h * 1.3:
            continue
        boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: b[0])
    return boxes

def _decode_single_digit(roi):
    h, w = roi.shape[:2]
    def region_on(y0, y1, x0, x1):
        y0, y1 = int(y0 * h), int(y1 * h)
        x0, x1 = int(x0 * w), int(x1 * w)
        area = roi[y0:y1, x0:x1]
        if area.size == 0:
            return 0
        white_ratio = np.count_nonzero(area) / float(area.size)
        return 1 if white_ratio > 0.45 else 0
    top          = region_on(0.00, 0.18, 0.20, 0.80)
    top_left     = region_on(0.12, 0.50, 0.00, 0.30)
    top_right    = region_on(0.12, 0.50, 0.70, 1.00)
    middle       = region_on(0.42, 0.58, 0.15, 0.85)
    bottom_left  = region_on(0.50, 0.88, 0.00, 0.30)
    bottom_right = region_on(0.50, 0.88, 0.70, 1.00)
    bottom       = region_on(0.82, 1.00, 0.20, 0.80)
    pattern = (top, top_left, top_right, middle, bottom_left, bottom_right, bottom)
    return SEVEN_SEG_LOOKUP.get(pattern, None)

def decode_seven_segment(lcd_image):
    try:
        h0, w0 = lcd_image.shape[:2]
        target_width = 700
        scale = target_width / float(w0)
        scale = max(0.3, min(scale, 3.0))
        gray = cv2.cvtColor(lcd_image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh_dark_on_light = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        _, thresh_light_on_dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        best_result = ""
        best_count = 0
        for thresh in (thresh_dark_on_light, thresh_light_on_dark):
            kernel = np.ones((3, 3), np.uint8)
            thresh_clean = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            boxes = _find_digit_boxes(thresh_clean)
            if len(boxes) < 2:
                continue
            digits = []
            for (x, y, w, h) in boxes:
                roi = thresh_clean[y:y + h, x:x + w]
                roi = cv2.resize(roi, (60, 100), interpolation=cv2.INTER_NEAREST)
                d = _decode_single_digit(roi)
                digits.append(d if d is not None else '?')
            result = "".join(digits)
            confident_digit_count = sum(1 for d in digits if d != '?')
            if confident_digit_count > best_count:
                best_count = confident_digit_count
                best_result = result
        return best_result, best_count
    except Exception as e:
        print(f"[SEVEN-SEG] ERROR internal. Detail: {e}")
        return "", 0

# ============================================================
# EASYOCR FALLBACK PREPROCESS (dipertahankan, tapi tidak dipakai kalau reader=None)
# ============================================================
def get_preprocess_variants(image):
    variants = []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    target_width = 1000
    scale = target_width / float(w)
    scale = max(0.5, min(scale, 4.0))
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)
    smooth = cv2.bilateralFilter(gray_clahe, 5, 50, 50)
    variants.append(smooth)
    median = cv2.medianBlur(gray_clahe, 3)
    thresh_adapt = cv2.adaptiveThreshold(median, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5)
    kernel = np.ones((2, 2), np.uint8)
    thresh_adapt = cv2.morphologyEx(thresh_adapt, cv2.MORPH_CLOSE, kernel)
    variants.append(thresh_adapt)
    _, thresh_otsu = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(thresh_otsu)
    return variants

def is_plausible_kwh(value):
    if value is None:
        return False
    if value < 0:
        return False
    if value > 99999:
        return False
    return True

def extract_meter_value(text, has_decimal=True):
    text = text.replace(" ", "")
    if len(text) > 15:
        return None, None
    if has_decimal:
        match = re.findall(r"\d{1,5}\.\d{2}", text)
        if match:
            return float(match[0]), 0
        match = re.findall(r"\d{1,5},\d{2}", text)
        if match:
            return float(match[0].replace(",", ".")), 0
        raw_digit_runs = re.findall(r"\d+", text)
        if any(len(run) > 7 for run in raw_digit_runs):
            return None, None
        match = re.findall(r"\d{4,7}", text)
        if match:
            number = match[0]
            integer = number[:-2]
            decimal = number[-2:]
            return float(f"{integer}.{decimal}"), 1
        return None, None
    else:
        clean = text.replace(".", "").replace(",", "")
        raw_digit_runs = re.findall(r"\d+", clean)
        if any(len(run) > 8 for run in raw_digit_runs):
            return None, None
        match = re.findall(r"\d{3,7}", clean)
        if match:
            number = match[0]
            return float(number), 0
        return None, None

def run_ocr(image_variant):
    results = reader.readtext(
        image_variant, allowlist="0123456789.,",
        detail=1, paragraph=False, decoder="greedy"
    )
    if not results:
        return "", 0.0, []
    results_by_pos = sorted(results, key=lambda r: r[0][0][0])
    combined_text = "".join(text for _, text, _ in results_by_pos)
    avg_conf = sum(c for _, _, c in results_by_pos) / len(results_by_pos)
    return combined_text, avg_conf, results

def scan_meter_image(image, has_decimal=True):
    t_start = time.time()
    if image is None:
        raise ValueError("Image kosong")

    is_sharp, sharpness_score = is_image_sharp(image)
    if not is_sharp:
        return None

    h0, w0 = image.shape[:2]
    max_dim = 1600
    if max(h0, w0) > max_dim:
        scale0 = max_dim / float(max(h0, w0))
        image = cv2.resize(image, None, fx=scale0, fy=scale0, interpolation=cv2.INTER_AREA)

    cropped = auto_crop_lcd(image)
    raw_digits, confident_count = decode_seven_segment(cropped)

    if confident_count >= 3 and '?' not in raw_digits:
        if has_decimal:
            if len(raw_digits) >= 3:
                integer_part = raw_digits[:-2]
                decimal_part = raw_digits[-2:]
                value = float(f"{integer_part}.{decimal_part}")
                if is_plausible_kwh(value):
                    return round(value, 2)
        else:
            value = float(raw_digits)
            if is_plausible_kwh(value):
                return round(value, 2)

    if reader is None:
        print("[INFO] EasyOCR dinonaktifkan (RAM terbatas), skip fallback.")
        return None

    variants = get_preprocess_variants(cropped)
    candidates = []
    EARLY_EXIT_CONF = 0.5
    for i, v in enumerate(variants):
        combined_text, avg_conf, raw_results = run_ocr(v)
        if not combined_text:
            continue
        value, reliability = extract_meter_value(combined_text, has_decimal=has_decimal)
        if is_plausible_kwh(value):
            candidates.append((value, reliability, avg_conf, combined_text))
        for _, text, conf in raw_results:
            frag_value, frag_reliability = extract_meter_value(text, has_decimal=has_decimal)
            if is_plausible_kwh(frag_value):
                candidates.append((frag_value, frag_reliability, conf, text))
        if candidates:
            best_so_far = sorted(candidates, key=lambda c: (c[1], -c[2]))[0]
            if best_so_far[1] == 0 and best_so_far[2] >= EARLY_EXIT_CONF:
                break

    if candidates:
        best = sorted(candidates, key=lambda c: (c[1], -c[2]))[0]
        return round(best[0], 2)

    return None

# ============================================================
# OCR STRUK (Tesseract)
# ============================================================
def preprocess_receipt(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    return gray

def read_receipt(image):
    processed = preprocess_receipt(image)
    raw_text = pytesseract.image_to_string(processed, lang='ind')
    result = [line.strip() for line in raw_text.split('\n') if line.strip()]
    return result

def receipt_to_text(image):
    result = read_receipt(image)
    raw_text = "\n".join(result)
    return raw_text
