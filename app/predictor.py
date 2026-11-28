
import numpy as np
import pandas as pd

from .classifier import classify


FEATURES = [
    "ambient_temp_c",
    "driver_temp_c",
    "led_temp_c",
    "voltage_v",
    "current_a",
    "power_w",
    "lumen_pct",
    "display_sync_ok",
    "sync_error_count",
]


def predict_batch(samples, models):
    # Chuyển dữ liệu cảm biến thành DataFrame 9 đặc trưng
    rows = [
        [
            s.ambient_temp_c,
            s.driver_temp_c,
            s.led_temp_c,
            s.voltage_v,
            s.current_a,
            s.power_w,
            s.lumen_pct,
            int(s.display_sync_ok),
            s.sync_error_count,
        ]
        for s in samples
    ]

    X = pd.DataFrame(rows, columns=FEATURES, dtype=float)

    if not np.isfinite(X.to_numpy()).all():
        raise ValueError("Du lieu cam bien phai la so huu han")

    # Kiểm tra cấu trúc mô hình
    if models.preprocessor is None:
        raise RuntimeError("Khong tai duoc bo tien xu ly W3-ML")

    prep = models.preprocessor

    if prep.get("features") != FEATURES:
        raise ValueError("Danh sach 9 features khong khop W3-ML")

    # Tiền xử lý giống W3-ML
    X_imputed = prep["imputer"].transform(X)
    X_scaled = prep["scaler"].transform(X_imputed)

    # Isolation Forest
    if_flags = [False] * len(samples)
    if_scores = [None] * len(samples)

    if models.isolation_forest is not None:
        predictions = models.isolation_forest.predict(X)
        raw_scores = models.isolation_forest.decision_function(X)

        if_flags = (predictions == -1).tolist()
        if_scores = [float(-v) for v in raw_scores]

    # Autoencoder
    ae_flags = [False] * len(samples)
    ae_errors = [None] * len(samples)

    if (
        models.autoencoder is not None
        and models.threshold is not None
    ):
        reconstructed = models.autoencoder.predict(
            X_scaled, verbose=0
        )

        errors = np.mean(
            np.square(X_scaled - reconstructed),
            axis=1
        )

        ae_errors = [float(v) for v in errors]
        ae_flags = (errors > models.threshold).tolist()

    results = []

    for i, sample in enumerate(samples):
        code, name, reasons = classify(sample)

        is_anomaly = (
            bool(code)
            or if_flags[i]
            or ae_flags[i]
        )

        if code:
            reasons.append(
                "Phat hien loi theo quy tac F01-F04"
            )

        if if_flags[i]:
            reasons.append(
                "Isolation Forest phat hien bat thuong"
            )

        if ae_flags[i]:
            reasons.append(
                f"Autoencoder reconstruction error "
                f"{ae_errors[i]:.6f} vuot threshold "
                f"{models.threshold:.6f}"
            )

        if not code and is_anomaly:
            code = "ANOMALY"
            name = "Bat thuong chua phan loai"

        # Điểm anomaly_score là reconstruction error
        # khi Autoencoder hoạt động; nếu không, dùng IF score.
        score = (
            ae_errors[i]
            if ae_errors[i] is not None
            else if_scores[i]
        )

        results.append({
            "device_id": sample.device_id,
            "is_anomaly": is_anomaly,
            "fault_code": code,
            "fault_name": name,
            "anomaly_score": score,
            "reasons": reasons,
        })

    return results
