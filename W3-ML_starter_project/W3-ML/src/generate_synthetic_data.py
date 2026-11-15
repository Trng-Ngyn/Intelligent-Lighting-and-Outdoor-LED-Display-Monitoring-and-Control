from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "pilot_50_led_synthetic.csv"

def main():
    rng = np.random.default_rng(20261114)
    rows = []
    start = pd.Timestamp("2026-10-01 00:00:00")
    devices = [f"LED-{i:03d}" for i in range(1, 51)]

    for device_idx, device in enumerate(devices):
        temp_base = rng.normal(56, 3)
        current_base = rng.normal(0.42, 0.035)
        power_base = rng.normal(48, 4)
        voltage_base = rng.normal(220, 3)

        # Mỗi thiết bị có 14 ngày, lấy mẫu mỗi giờ.
        for hour in range(14 * 24):
            ts = start + pd.Timedelta(hours=hour)
            ambient = 29 + 3 * np.sin(2 * np.pi * (hour % 24) / 24)
            driver_temp = temp_base + 0.35 * (ambient - 29) + rng.normal(0, 1.8)
            led_temp = driver_temp + rng.normal(4, 1.2)
            voltage = voltage_base + rng.normal(0, 1.5)
            current = current_base + rng.normal(0, 0.012)
            power = voltage * current * 0.50 + rng.normal(0, 1.0)
            lumen = max(60, 100 - 0.025 * hour + rng.normal(0, 1.0))
            sync_ok = 1
            sync_errors = 0

            # Cấy các sự kiện lỗi có chủ đích để kiểm thử pipeline.
            event = hour % 168
            if 30 <= event <= 34 and device_idx % 7 == 0:       # F01
                driver_temp += 27
                led_temp += 25
            if 60 <= event <= 63 and device_idx % 6 == 1:       # F02
                current *= 1.45
                power *= 1.35
            if 90 <= event <= 95 and device_idx % 5 == 2:       # F03
                lumen *= 0.72
            if 120 <= event <= 123 and device_idx % 8 == 3:     # F04
                sync_ok = 0
                sync_errors = int(rng.integers(1, 5))

            rows.append({
                "device_id": device,
                "timestamp": ts.isoformat(),
                "ambient_temp_c": round(ambient, 2),
                "driver_temp_c": round(driver_temp, 2),
                "led_temp_c": round(led_temp, 2),
                "voltage_v": round(voltage, 2),
                "current_a": round(current, 4),
                "power_w": round(power, 2),
                "current_baseline_a": round(current_base, 4),
                "power_baseline_w": round(power_base, 2),
                "lumen_pct": round(lumen, 2),
                "display_sync_ok": sync_ok,
                "sync_error_count": sync_errors,
                "is_synthetic": 1
            })

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Da tao {len(df):,} dong du lieu mo phong: {OUT}")

if __name__ == "__main__":
    main()
