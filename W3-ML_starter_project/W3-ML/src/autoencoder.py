from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from tensorflow import keras
from tensorflow.keras import layers

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "labeled" / "pilot_50_led_labeled.csv"
OUT = ROOT / "data" / "processed" / "autoencoder_predictions.csv"
MODEL_PATH = ROOT / "reports" / "autoencoder.keras"

FEATURES = [
    "ambient_temp_c", "driver_temp_c", "led_temp_c", "voltage_v",
    "current_a", "power_w", "lumen_pct", "display_sync_ok", "sync_error_count"
]

def main():
    df = pd.read_csv(DATA)
    X_raw = df[FEATURES].to_numpy(dtype=float)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X = scaler.fit_transform(imputer.fit_transform(X_raw))

    # Demo: dùng các dòng được rule gán NORMAL làm tập huấn luyện.
    # Khi có Ground Truth đã xác minh, cần thay nhãn rule bằng nhãn chuyên gia.
    normal_mask = df["anomaly_label"].to_numpy() == 0
    X_train = X[normal_mask]
    if len(X_train) < 20:
        raise ValueError("Khong du dong NORMAL de huan luyen Autoencoder.")

    model = keras.Sequential([
        layers.Input(shape=(X.shape[1],)),
        layers.Dense(16, activation="relu"),
        layers.Dense(6, activation="relu"),
        layers.Dense(16, activation="relu"),
        layers.Dense(X.shape[1], activation="linear")
    ])
    model.compile(optimizer="adam", loss="mse")
    model.fit(X_train, X_train, epochs=20, batch_size=64, validation_split=0.2,
              verbose=0, shuffle=True)

    # Chọn ngưỡng demo từ phân vị 95% reconstruction error trên train-normal.
    train_recon = model.predict(X_train, verbose=0)
    train_error = np.mean(np.square(X_train - train_recon), axis=1)
    threshold = float(np.quantile(train_error, 0.95))

    recon = model.predict(X, verbose=0)
    errors = np.mean(np.square(X - recon), axis=1)
    result = df[["device_id", "timestamp", "fault_code", "anomaly_label"]].copy()
    result["ae_prediction"] = (errors > threshold).astype(int)
    result["ae_anomaly_score"] = errors
    result["ae_threshold"] = threshold

    OUT.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False, encoding="utf-8-sig")
    model.save(MODEL_PATH)
    # Lưu scaler/imputer để tái sử dụng đúng quy trình
    import joblib
    joblib.dump({"imputer": imputer, "scaler": scaler, "features": FEATURES},
                ROOT / "reports" / "autoencoder_preprocessing.joblib")
    print(f"Da luu ket qua: {OUT}")
    print(f"Nguong reconstruction error: {threshold:.6f}")

if __name__ == "__main__":
    main()
