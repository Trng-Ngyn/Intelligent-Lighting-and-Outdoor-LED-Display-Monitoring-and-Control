
from typing import Optional, List
from pydantic import BaseModel, Field


class SensorSample(BaseModel):
    device_id: str = Field(..., min_length=1)

    ambient_temp_c: float
    driver_temp_c: float
    led_temp_c: float
    voltage_v: float
    current_a: float
    power_w: float
    lumen_pct: float
    display_sync_ok: bool
    sync_error_count: int = Field(..., ge=0)


class PredictRequest(BaseModel):
    batch: List[SensorSample] = Field(
        ..., min_length=1, max_length=500
    )


class Prediction(BaseModel):
    device_id: str
    is_anomaly: bool
    fault_code: Optional[str] = None
    fault_name: str
    anomaly_score: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)


class PredictResponse(BaseModel):
    success: bool
    total_samples: int
    results: List[Prediction]
    model_status: dict
