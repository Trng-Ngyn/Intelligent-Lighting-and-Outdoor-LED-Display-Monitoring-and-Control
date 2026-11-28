"""Payload mẫu do code sinh ra để audit S4 (không cần bo).

Trường/giá trị khớp `main/pccom_telemetry.c`. Dùng chung hàm ký của dự án
(`iot_protocol.headers.build_headers`) nên bản tin sinh ra phải qua đồng thời
`jsonschema` (docs/data_contracts/schemas.json) và `verify_envelope`.
"""


from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.headers import build_headers  # noqa: E402
from iot_protocol.signing import derive_device_key  # noqa: E402

SITE = "SITE_01"
DEVICE_TYPE = "light"
DEVICE_ID = "LGT_NODE_001"
TOPIC = f"telemetry/v1/{SITE}/{DEVICE_TYPE}/{DEVICE_ID}"
MASTER = "audit-master-secret"
CORRELATION_ID = "00000000-0000-4000-8000-000000000007"


def sample_message(
    sequence: int = 7,
    ts_ms: int = 1794660440618,
    *,
    master: str = MASTER,
) -> tuple[dict, dict[str, str]]:
    """Trả (payload, user_properties) đã ký đúng canonical của dự án."""
    payload = {
        "schema_version": "1.0.0",
        "message_id": CORRELATION_ID,
        "asset_id": DEVICE_ID,
        "sequence": sequence,
        "source_time": ts_ms // 1000,
        "metrics": {
            "power_w": 48.1,
            "energy_wh": 125.47,
            "voltage_v": 220.1,
            "current_a": 0.218,
            "power_factor": 0.95,
            "temperature_c": 47.0,
            "ambient_lux": 300.0,
        },
        "brightness_pct": 50,
        "relay_state": True,
        "quality": "GOOD",
    }
    import json
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    key = derive_device_key(master, SITE, DEVICE_TYPE, DEVICE_ID)
    props, _, _ = build_headers(
        key, TOPIC, text, correlation_id=CORRELATION_ID, ts_ms=ts_ms
    )
    return payload, props


if __name__ == "__main__":
    import json
    body, props = sample_message()
    print(json.dumps({"payload": body, "props": props}, ensure_ascii=False))
