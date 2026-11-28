import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_batch_50_latency():
    batch = [
        {"device_id": f"LED_{i:03d}", "W": 25, "V": 220, "A": 0.12,
         "Temp": 45, "Lux": 1000}
        for i in range(50)
    ]
    start = time.perf_counter()
    response = client.post("/api/v1/ai/predict-anomaly", json={"batch": batch})
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert response.status_code == 200
    print(f"50-sample request latency: {elapsed_ms:.2f} ms")
