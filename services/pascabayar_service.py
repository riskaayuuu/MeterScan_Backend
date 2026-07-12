from datetime import datetime
import calendar


# ==========================================================
# TARIF PLN
# ==========================================================

def get_tariff(power):

    tariffs = {
        450: 415,
        900: 1352,
        1300: 1444.70,
        2200: 1444.70,
        3500: 1699.53,
        4400: 1699.53,
        5500: 1699.53,
    }

    return tariffs.get(power, 1444.70)


# ==========================================================
# FILTER DATA BULAN INI
# ==========================================================

def get_month_readings(readings):

    now = datetime.now()

    data = []

    for item in readings:

        tanggal = item["created_at"]

        if isinstance(tanggal, str):
            tanggal = datetime.fromisoformat(tanggal)

        if tanggal.month == now.month and tanggal.year == now.year:

            item["created_at"] = tanggal
            data.append(item)

    data.sort(key=lambda x: x["created_at"])

    return data


# ==========================================================
# PERHITUNGAN PASCABAYAR
# ==========================================================

def calculate_pascabayar(

        current_meter,
        power,
        monthly_budget,
        readings

):

    now = datetime.now()

    tariff = get_tariff(power)

    month_data = get_month_readings(readings)

    # =====================================================
    # SCAN PERTAMA BULAN
    # =====================================================

    if len(month_data) == 0:

        first_meter = current_meter
        previous_meter = current_meter

        days_used = max(1, now.day)

    else:

        first_meter = month_data[0]["current_meter"]

        previous_meter = month_data[-1]["current_meter"]

        first_date = month_data[0]["created_at"]

        days_used = max(
            1,
            (now - first_date).days
        )

    # =====================================================
    # PEMAKAIAN
    # =====================================================

    usage_today = max(
        0,
        current_meter - previous_meter
    )

    kwh_month = max(
        0,
        current_meter - first_meter
    )

    avg_daily = kwh_month / max(days_used, 1)

    # =====================================================
    # ESTIMASI BULAN
    # =====================================================

    total_day = calendar.monthrange(
        now.year,
        now.month
    )[1]

    remain_day = total_day - now.day

    estimate_kwh = kwh_month + (avg_daily * remain_day)

    estimate_bill = int(
        estimate_kwh * tariff
    )

    running_bill = int(
        kwh_month * tariff
    )

    daily_cost = int(
        usage_today * tariff
    )

    # =====================================================
    # PROGRESS BUDGET
    # =====================================================

    if monthly_budget > 0:

        progress = min(
            estimate_bill / monthly_budget,
            1
        )

    else:

        progress = 0

    # =====================================================
    # STATUS
    # =====================================================

    if monthly_budget <= 0:

        status = "BELUM ADA BUDGET"

    elif estimate_bill >= monthly_budget:

        status = "MELEBIHI BUDGET"

    elif estimate_bill >= monthly_budget * 0.8:

        status = "HAMPIR LIMIT"

    else:

        status = "AMAN"

    # =====================================================
    # DATA GRAFIK
    # =====================================================

    grafik_hari = []

    grafik_kwh = []

    if len(month_data) >= 2:

        for i in range(1, len(month_data)):

            prev = month_data[i - 1]

            curr = month_data[i]

            pakai = max(
                0,
                curr["current_meter"] - prev["current_meter"]
            )

            grafik_hari.append(
                curr["created_at"].strftime("%d/%m")
            )

            grafik_kwh.append(
                round(pakai, 2)
            )

    elif len(month_data) == 1:

        grafik_hari.append(
            now.strftime("%d/%m")
        )

        grafik_kwh.append(
            round(kwh_month, 2)
        )

    # =====================================================
    # RETURN
    # =====================================================

    return {

        "previous_meter": round(previous_meter, 2),

        "current_meter": round(current_meter, 2),

        "daily_usage": round(usage_today, 2),

        "daily_cost": daily_cost,

        "avg_daily_usage": round(avg_daily, 2),

        "monthly_kwh": round(kwh_month,2),

        "kwh_terpakai": round(kwh_month, 2),

        "tagihan_berjalan": running_bill,

        "estimasi_kwh": round(estimate_kwh, 2),

        "estimasi_tagihan": estimate_bill,

        "hari_ke": now.day,

        "total_hari": total_day,

        "sisa_hari": remain_day,

        "progress": round(progress, 2),

        "status": status,

        "grafik_hari": grafik_hari,

        "grafik_kwh": grafik_kwh

    }