import time
import json
import random
import threading
import paho.mqtt.client as mqtt

BROKER = "broker.emqx.io"
PORT = 1883
SITE_ID = "SITE_01"
NUM_NODES = 50

class VirtualLightingNetwork:
    """
    Bộ mô phỏng mạng lưới 50 điểm đèn thông minh và 2 màn hình LED ngoài trời
    Cho phép phát triển và kiểm thử toàn bộ hệ thống phần mềm (Web Console, Cloud API, AI)
    mà chưa cần lắp đặt bo mạch phần cứng ESP32 thực tế.
    """
    def __init__(self):
        self.nodes = {}
        # Khởi tạo 50 điểm đèn với tọa độ GIS giả lập tại TP.HCM (Quận 1 / Khu công nghệ cao)
        base_lat, base_lng = 10.8505, 106.7719
        for i in range(1, NUM_NODES + 1):
            asset_id = f"LGT_NODE_{i:03d}"
            self.nodes[asset_id] = {
                "asset_id": asset_id,
                "lat": base_lat + (i * 0.0008) + random.uniform(-0.0001, 0.0001),
                "lng": base_lng + ((i % 5) * 0.001) + random.uniform(-0.0001, 0.0001),
                "brightness": 50 if i <= 30 else 0, # 50% hoặc tắt
                "relay_state": True,
                "voltage": 220.0,
                "temperature": 35.0 + random.uniform(0, 3.0),
                "cumulative_wh": 100.0 + random.uniform(10, 50),
                "sequence": 0
            }
        
        self.client = mqtt.Client(client_id="Virtual_Edge_Simulator_PCCOM")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        print(f"[SIMULATOR] Ket noi thanh cong MQTT Broker {BROKER}:{PORT}")
        # Dang ky nhan lenh dieu khien cho tat ca cac node
        topic_sub = f"pccom/lighting/{SITE_ID}/+/command"
        client.subscribe(topic_sub)
        print(f"[SIMULATOR] Dang lang nghe lenh tren: {topic_sub}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            topic_parts = msg.topic.split('/')
            asset_id = topic_parts[3] if len(topic_parts) >= 4 else "ALL"
            action = payload.get("action")
            val = payload.get("requested_value", 0)
            cmd_id = payload.get("command_id", "CMD_SIM")

            print(f"[COMMAND RX] Node {asset_id} -> Action: {action} | Gia tri: {val}")

            targets = [asset_id] if asset_id in self.nodes else list(self.nodes.keys())
            for t in targets:
                node = self.nodes[t]
                if action == "DIM":
                    node["brightness"] = max(0, min(100, int(val)))
                elif action == "SWITCH":
                    node["relay_state"] = bool(val)
                    if not node["relay_state"]:
                        node["brightness"] = 0

                # Gui phan hoi ket qua lenh (Command Result)
                res = {
                    "command_id": cmd_id,
                    "asset_id": t,
                    "device_time": int(time.time()),
                    "status": "EXECUTED",
                    "reason": "Virtual driver updated state",
                    "observed_value": node["brightness"],
                    "evidence_source": "VIRTUAL_PWM_SENSOR"
                }
                res_topic = f"pccom/lighting/{SITE_ID}/{t}/result"
                self.client.publish(res_topic, json.dumps(res))
        except Exception as e:
            print(f"[SIMULATOR ERROR] on_message: {e}")

    def emit_telemetry_loop(self):
        while True:
            # Phat telemetry dinh ky cho 50 node
            ambient_lux = random.uniform(20.0, 450.0)
            for asset_id, node in self.nodes.items():
                node["sequence"] += 1
                v = node["voltage"] + random.uniform(-1.5, 1.5)
                # Cong suat ti le voi do sang (Den 100W max)
                w = (node["brightness"] / 100.0) * 100.0 * random.uniform(0.96, 1.02) if node["relay_state"] else 0.0
                a = w / v if v > 0 else 0.0
                node["cumulative_wh"] += (w * (5.0 / 3600.0)) # cong don
                temp = 32.0 + (node["brightness"] * 0.3) + random.uniform(-0.5, 0.5)

                payload = {
                    "schema_version": "1.0.0",
                    "message_id": f"MSG_{int(time.time())}_{node['sequence']}",
                    "asset_id": asset_id,
                    "sequence": node["sequence"],
                    "source_time": int(time.time()),
                    "metrics": {
                        "power_w": round(w, 2),
                        "energy_wh": round(node["cumulative_wh"], 2),
                        "voltage_v": round(v, 1),
                        "current_a": round(a, 3),
                        "power_factor": 0.95,
                        "temperature_c": round(temp, 1),
                        "ambient_lux": round(ambient_lux, 1)
                    },
                    "brightness_pct": node["brightness"],
                    "relay_state": node["relay_state"],
                    "quality": "GOOD"
                }
                topic = f"pccom/lighting/{SITE_ID}/{asset_id}/telemetry"
                self.client.publish(topic, json.dumps(payload))

            print(f"[SIMULATOR] Da phat Telemetry cho {NUM_NODES} den (Lux TB: {ambient_lux:.1f})")
            time.sleep(15) # Chu ky phat 15s cho ban simulator

    def start(self):
        print("="*60)
        print("   PCCOM VIRTUAL IOT EDGE SIMULATOR - 50 LIGHTS & 2 LEDS")
        print("   (Chay mo phong toan bo phan mem khong can phan cung)")
        print("="*60)
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()
        
        t = threading.Thread(target=self.emit_telemetry_loop, daemon=True)
        t.start()

if __name__ == "__main__":
    sim = VirtualLightingNetwork()
    sim.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDung bo mo phong...")

