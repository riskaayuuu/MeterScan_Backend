import cv2
import easyocr
import numpy as np

# ==========================================================
# LOAD EASYOCR (sekali saja)
# ==========================================================

reader = easyocr.Reader(['en'], gpu=False)


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

# def read_receipt(image):

#     processed = preprocess_receipt(image)

#     result = reader.readtext(
#         processed,
#         detail=0,
#         paragraph=False
#     )

#     return result

def read_receipt(image):

    processed = preprocess_receipt(image)

    print("Original :", image.shape)
    print("Processed:", processed.shape)

    result = reader.readtext(
        processed,
        detail=0,
        paragraph=False
    )

    print(result)

    return result


# ==========================================================
# OCR -> RAW TEXT
# ==========================================================

def receipt_to_text(image):

    result = read_receipt(image)

    raw_text = "\n".join(result)

    return raw_text