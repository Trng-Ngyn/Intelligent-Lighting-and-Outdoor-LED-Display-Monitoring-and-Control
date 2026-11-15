from pathlib import Path
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "labeled" / "pilot_50_led_labeled.csv"
IF_FILE = ROOT / "data" / "processed" / "isolation_forest_predictions.csv"
AE_FILE = ROOT / "data" / "processed" / "autoencoder_predictions.csv"
REPORT = ROOT / "reports" / "evaluation_report.md"

def metrics(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1-score": f1_score(y_true, y_pred, zero_division=0),
        "FPR": fp / (fp + tn) if (fp + tn) else 0.0,
        "TN": tn, "FP": fp, "FN": fn, "TP": tp
    }

def main():
    truth = pd.read_csv(DATA)[["device_id", "timestamp", "anomaly_label"]]
    rows = []
    for name, path, col in [
        ("Isolation Forest", IF_FILE, "if_prediction"),
        ("Autoencoder", AE_FILE, "ae_prediction")
    ]:
        pred = pd.read_csv(path)
        merged = truth.merge(pred[["device_id", "timestamp", col]],
                             on=["device_id", "timestamp"], how="inner")
        m = metrics(merged["anomaly_label"], merged[col])
        rows.append((name, m))

    lines = [
        "# W3-ML – Evaluation Report",
        "",
        "> Kết quả trên dữ liệu mô phỏng; không đại diện hiệu năng trên thiết bị Pilot thực tế.",
        "",
        "| Model | Precision | Recall | F1-score | FPR | TN | FP | FN | TP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for name, m in rows:
        lines.append(
            f"| {name} | {m['Precision']:.4f} | {m['Recall']:.4f} | "
            f"{m['F1-score']:.4f} | {m['FPR']:.4f} | {m['TN']} | "
            f"{m['FP']} | {m['FN']} | {m['TP']} |"
        )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nDa luu bao cao: {REPORT}")

if __name__ == "__main__":
    main()
