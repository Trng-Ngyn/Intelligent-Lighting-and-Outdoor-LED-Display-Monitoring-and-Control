
def classify(sample):
    """
    Phan loai loi F01-F04 theo quy tac baseline.
    Cac nguong can duoc kiem chung bang du lieu thuc te.
    """

    reasons = []
    code = None
    name = "Normal"

    # F01: Qua nhiet Driver hoac LED
    if sample.driver_temp_c > 80 or sample.led_temp_c > 80:
        code = "F01"
        name = "Qua nhiet Driver/LED"

        reasons.append(
            f"Driver={sample.driver_temp_c}°C, "
            f"LED={sample.led_temp_c}°C, vuot nguong 80°C"
        )

    # F02: Bat thuong dien ap hoac dong dien
    elif (
        sample.voltage_v < 198
        or sample.voltage_v > 242
        or sample.current_a > 0.30
    ):
        code = "F02"
        name = "Bat thuong dien nang"

        reasons.append(
            f"Voltage={sample.voltage_v}V, "
            f"Current={sample.current_a}A"
        )

    # F03: Suy giam quang thong
    elif sample.lumen_pct < 80:
        code = "F03"
        name = "Suy giam quang thong"

        reasons.append(
            f"Lumen con {sample.lumen_pct}%"
        )

    # F04: Mat dong bo hien thi
    elif (
        not sample.display_sync_ok
        or sample.sync_error_count > 0
    ):
        code = "F04"
        name = "Mat dong bo hien thi"

        reasons.append(
            f"Display sync={sample.display_sync_ok}, "
            f"Sync errors={sample.sync_error_count}"
        )

    return code, name, reasons
