from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_predict_batch():
    payload = {"batch": [
        {"device_id": "LED_001", "W": 25, "V": 220, "A": 0.12, "Temp": 85, "Lux": 950},
        {"device_id": "LED_002", "W": 25, "V": 220, "A": 0.12, "Temp": 45, "Lux": 1000}
    ]}
    response = client.post("/api/v1/ai/predict-anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_samples"] == 2
    assert data["results"][0]["fault_code"] == "F01"
