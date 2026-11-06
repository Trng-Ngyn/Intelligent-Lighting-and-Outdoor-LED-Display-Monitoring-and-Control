import json
import time
import paho.mqtt.client as mqtt

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC_TELEMETRY = "pccom/lighting/+/+/telemetry"
TOPIC_RESULT = "pccom/lighting/+/+/result"
TOPIC_COMMAND = "pccom/lighting/SITE_01/LGT_NODE_001/command"

def on_connect(client, userdata, flags, rc):
    print(f"[CLOUD CONNECTED] Connected to MQTT Broker {BROKER}:{PORT} (code: {rc})")
    client.subscribe(TOPIC_TELEMETRY)
    client.subscribe(TOPIC_RESULT)
    print(f"[SUBSCRIBED] Listening to telemetry and results...")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        if "telemetry" in msg.topic:
            metrics = payload.get("metrics", {})
            print(f"\n[TELEMETRY RECEIVED] Node: {payload.get('asset_id')} | Seq: #{payload.get('sequence')}")
            print(f"  -> Công suất: {metrics.get('power_w')}W | Điện áp: {metrics.get('voltage_v')}V | Nhiệt độ: {metrics.get('temperature_c')}°C | Lux: {metrics.get('ambient_lux')}")
        elif "result" in msg.topic:
            print(f"\n[COMMAND RESULT] Command ID: {payload.get('command_id')}")
            print(f"  -> Trạng thái: {payload.get('status')} | Lý do: {payload.get('reason')} | Quan sát: {payload.get('observed_value')}")
    except Exception as e:
        print(f"[ERROR] Decode payload error: {e}")

def send_dimming_command(client, brightness_pct):
    cmd = {
        "command_id": f"CMD_{int(time.time())}",
        "actor": "ProductOwner_Trọng",
        "action": "DIM",
        "requested_value": brightness_pct,
        "policy_version": "v1.0",
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + 60,
        "priority": 1
    }
    client.publish(TOPIC_COMMAND, json.dumps(cmd))
    print(f"\n[COMMAND SENT] Da gui lenh dieu chinh do sang {brightness_pct}% den ESP32 (Topic: {TOPIC_COMMAND})")

if __name__ == "__main__":
    print("="*60)
    print("   PCCOM CLOUD PLATFORM - MOCK INGESTION & CONTROL SERVICE")
    print("="*60)
    client = mqtt.Client(client_id="PCCOM_Cloud_Test_Server")
    client.on_connect = on_connect
    client.on_message = on_message

    print("[*] Dang ket noi broker MQTT...")
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    time.sleep(2)
    # Gui lenh dimming thu nghiem 80%
    send_dimming_command(client, 80)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Dang dung service...")
        client.loop_stop()
        client.disconnect()
