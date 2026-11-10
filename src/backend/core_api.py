import http.server
import socketserver
import json
import time
import os
import paho.mqtt.client as mqtt

PORT = 8080
MQTT_BROKER = "broker.emqx.io"
SITE_ID = "SITE_01"

# Kho luu tru trang thai thiet bi trong RAM (In-memory Asset Cache)
ASSET_STATE = {}
for i in range(1, 51):
    aid = f"LGT_NODE_{i:03d}"
    ASSET_STATE[aid] = {
        "asset_id": aid,
        "site_id": SITE_ID,
        "name": f"Đèn chiếu sáng thông minh #{i}",
        "lat": 10.8505 + (i * 0.0008),
        "lng": 106.7719 + ((i % 5) * 0.001),
        "brightness": 50,
        "relay": True,
        "power_w": 48.5,
        "voltage_v": 220.2,
        "temp_c": 36.5,
        "status": "ONLINE"
    }

# 2 Man hinh LED
LED_DISPLAYS = [
    {
        "id": "DSP_LED_001",
        "name": "Màn hình LED Khu Công Nghệ Cao (Site 01)",
        "lat": 10.8520,
        "lng": 106.7740,
        "resolution": "1920x1080",
        "current_playlist": "Thông điệp an toàn giao thông đô thị",
        "status": "ONLINE",
        "brightness": 80
    },
    {
        "id": "DSP_LED_002",
        "name": "Màn hình LED Trung tâm Điều hành (Site 02)",
        "lat": 10.8560,
        "lng": 106.7780,
        "resolution": "3840x2160",
        "current_playlist": "Bản tin tuyên truyền chuyển đổi số TP.HCM",
        "status": "ONLINE",
        "brightness": 75
    }
]

mqtt_client = mqtt.Client(client_id="PCCOM_Backend_Core_API")

def init_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, 1883, 60)
        mqtt_client.loop_start()
        print(f"[BACKEND API] Da ket noi MQTT Broker {MQTT_BROKER}")
    except Exception as e:
        print(f"[WARN] Khong the ket noi MQTT Broker: {e}")

class CoreApiHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/v1/assets":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            data = {
                "lighting_nodes": list(ASSET_STATE.values()),
                "led_displays": LED_DISPLAYS,
                "total_lights": len(ASSET_STATE),
                "total_leds": len(LED_DISPLAYS),
                "timestamp": int(time.time())
            }
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        elif self.path == "/api/v1/summary":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            total_power = sum(item["power_w"] for item in ASSET_STATE.values())
            data = {
                "total_lights": len(ASSET_STATE),
                "online_lights": len([x for x in ASSET_STATE.values() if x["status"] == "ONLINE"]),
                "total_power_kw": round(total_power / 1000.0, 2),
                "avg_brightness": round(sum(x["brightness"] for x in ASSET_STATE.values()) / len(ASSET_STATE), 1),
                "led_status": "NORMAL",
                "gate_status": "GATE G0 READINESS VERIFIED"
            }
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        else:
            # Serve frontend files if matching
            frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
            if self.path == "/" or self.path == "/index.html":
                filepath = os.path.join(frontend_dir, "index.html")
                if os.path.exists(filepath):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    with open(filepath, "rb") as f:
                        self.wfile.write(f.read())
                    return
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/v1/controls/dim":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req = json.loads(post_data.decode('utf-8'))

            target_id = req.get("asset_id", "ALL")
            brightness = int(req.get("brightness", 50))
            cmd_id = f"CMD_WEB_{int(time.time())}"

            # Cap nhat vao RAM
            targets = [target_id] if target_id in ASSET_STATE else list(ASSET_STATE.keys())
            for t in targets:
                ASSET_STATE[t]["brightness"] = brightness
                ASSET_STATE[t]["power_w"] = round((brightness / 100.0) * 100.0, 1)

            # Gui lenh MQTT xuong Edge Simulator
            topic = f"pccom/lighting/{SITE_ID}/{target_id}/command"
            cmd_payload = {
                "command_id": cmd_id,
                "actor": "WebConsole_Operator",
                "action": "DIM",
                "requested_value": brightness,
                "expires_at": int(time.time()) + 60
            }
            mqtt_client.publish(topic, json.dumps(cmd_payload))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "SUCCESS",
                "command_id": cmd_id,
                "affected_nodes": len(targets),
                "brightness": brightness
            }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    init_mqtt()
    print("="*60)
    print(f"   PCCOM CORE API SERVICE RUNNING ON http://localhost:{PORT}")
    print("   Endpoints:")
    print("     - GET  /api/v1/assets   : Danh sách 50 đèn và 2 màn hình LED")
    print("     - GET  /api/v1/summary  : Chỉ số tiêu thụ điện và trạng thái hệ thống")
    print("     - POST /api/v1/controls/dim : Gửi lệnh điều chỉnh độ sáng")
    print(f"     - Web Console: http://localhost:{PORT}/index.html")
    print("="*60)
    with socketserver.TCPServer(("", PORT), CoreApiHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDung Backend Service...")

