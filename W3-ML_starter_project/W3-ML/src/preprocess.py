from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "pilot_50_led_synthetic.csv"
OUT = ROOT / "data" / "labeled" / "pilot_50_led_labeled.csv"

def label_row(row):
    codes = []
    if row["driver_temp_c"] > 80 or row["led_temp_c"] > 80:
        codes.append("F01")

    current_ratio = row["current_a"] / max(row["current_baseline_a"], 1e-6)
    power_drift = abs(row["power_w"] - row["power_baseline_w"]) / max(row["power_baseline_w"], 1e-6)
    if current_ratio > 1.25 or power_drift > 0.20:
        codes.append("F02")

    if row["lumen_pct"] < 80:
        codes.append("F03")

    if row["display_sync_ok"] == 0 or row["sync_error_count"] > 0:
        codes.append("F04")

    priority = ["F01", "F02", "F03", "F04"]
    ordered = [code for code in priority if code in codes]
    return pd.Series({
        "fault_codes": ";".join(ordered) if ordered else "NORMAL",
        "fault_code": ordered[0] if ordered else "NORMAL",
        "anomaly_label": int(bool(ordered))
    })

def main():
    df = pd.read_csv(RAW, parse_dates=["timestamp"])
    labels = df.apply(label_row, axis=1)
    df = pd.concat([df, labels], axis=1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("Da gan nhan xong.")
    print(df["fault_code"].value_counts().to_string())
    print(f"File: {OUT}")

if __name__ == "__main__":
    main()
