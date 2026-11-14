from pathlib import Path
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "labeled" / "pilot_50_led_labeled.csv"
OUT = ROOT / "data" / "processed" / "isolation_forest_predictions.csv"
MODEL = ROOT / "reports" / "isolation_forest.joblib"

FEATURES = [
    "ambient_temp_c", "driver_temp_c", "led_temp_c", "voltage_v",
    "current_a", "power_w", "lumen_pct", "display_sync_ok", "sync_error_count"
]

def main():
    df = pd.read_csv(DATA)
    X = df[FEATURES]
    # Baseline demo: fit không dùng nhãn. contamination chỉ là giả định ban đầu.
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", IsolationForest(
            n_estimators=200, contamination=0.05, random_state=42
        ))
    ])
    model.fit(X)
    pred = model.predict(X)
    score = model.decision_function(X)
    result = df[["device_id", "timestamp", "fault_code", "anomaly_label"]].copy()
    result["if_prediction"] = (pred == -1).astype(int)
    result["if_anomaly_score"] = -score
    OUT.parent.mkdir(parents=True, exist_ok=True)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False, encoding="utf-8-sig")
    joblib.dump(model, MODEL)
    print(f"Da luu ket qua: {OUT}")
    print(f"Da luu model: {MODEL}")

if __name__ == "__main__":
    main()
