# Gunakan image Python yang ringan
FROM python:3.11-slim

# Install dependency sistem untuk OpenCV (penting untuk EasyOCR/OpenCV)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set direktori kerja
WORKDIR /app

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file aplikasi
COPY . .

# Jalankan aplikasi dengan Gunicorn (lebih stabil untuk produksi)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:app"]