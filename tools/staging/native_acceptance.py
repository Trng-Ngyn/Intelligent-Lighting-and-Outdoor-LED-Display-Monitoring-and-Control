"""Exercise the same services with real local PostgreSQL/Timescale and Mosquitto.

This is a disposable integration runner, not a persistent VPS deployment.
Requires Timescale installed for the supplied PostgreSQL distribution.
"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src/backend"), str(ROOT)]
from tools.staging.bootstrap import demo_registry, generate  # noqa: E402


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(probe, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if probe():
                return
        except (ConnectionError, OSError, HTTPError):
            pass
        time.sleep(.2)
    raise RuntimeError("Service did not become ready")


@contextmanager
def process(args, env, log):
    with log.open("w") as output:
        child = subprocess.Popen(args, env=env, stdout=output, stderr=subprocess.STDOUT, cwd=ROOT)
        try:
            yield child
        finally:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def browser_smoke(api_base):
    from playwright.sync_api import expect, sync_playwright
    if not (ROOT / "dist/index.html").exists():
        raise RuntimeError("Build the frontend before browser acceptance")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "dist"), **kwargs)

        def log_message(self, *args):
            pass

        def proxy(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            req = Request(api_base + self.path, data=body, method=self.command,
                          headers={k: v for k, v in self.headers.items() if k.lower() != "host"})
            try:
                response = urlopen(req, timeout=15)
            except HTTPError as exc:
                response = exc
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(response.read())

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self.proxy()
            super().do_GET()

        do_POST = proxy

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH"),
                                         headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("https://*.tile.openstreetmap.org/**", lambda route: route.abort())
            page.goto("http://127.0.0.1:" + str(http.server_port))
            page.get_by_label("Tài khoản", exact=True).fill("staging-operator")
            password = (Path(os.environ["STAGING_SECRET_DIR"]) / "operator_password").read_text().strip()
            page.get_by_label("Mật khẩu", exact=True).fill(password)
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            expect(page.get_by_role("heading", name="Điều hành hệ thống")).to_be_visible()
            page.get_by_role("button", name="W5_LIGHT_001", exact=True).click()
            expect(page.locator(".reported")).to_contain_text("65", timeout=10000)
            page.get_by_role("button", name="Gửi lệnh dimming", exact=True).click()
            expect(page.get_by_text("Telemetry đã xác nhận", exact=False)).to_be_visible(timeout=30000)
            expect(page.locator(".reported")).to_contain_text("50", timeout=10000)
            page.get_by_label("Phạm vi gửi lệnh").select_option("group")
            page.get_by_label("Độ sáng yêu cầu", exact=False).press("End")
            page.get_by_role("button", name="Gửi lệnh dimming", exact=True).click()
            expect(page.get_by_text("Telemetry đã xác nhận", exact=False)).to_have_count(2, timeout=30000)
            expect(page.locator(".reported")).to_contain_text("100", timeout=10000)
            assert not errors, errors
            browser.close()
        print(json.dumps({"browser_api_mqtt_timescale": "PASS", "simulated_devices": True}), flush=True)
    finally:
        http.shutdown()
        http.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pg-bin", type=Path, required=True)
    p.add_argument("--mosquitto", type=Path, required=True)
    p.add_argument("--mosquitto-include", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--browser", action="store_true")
    args = p.parse_args()
    for name in ("pg_bin", "mosquitto", "mosquitto_include", "runtime"):
        setattr(args, name, getattr(args, name).resolve())
    args.runtime.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="native-", dir=args.runtime))
    generate("localhost", demo_registry(), runtime / "config", demo=True)
    config = runtime / "config"
    pgport, mqttport, apiport = port(), port(), port()
    pgdata = runtime / "pgdata"
    subprocess.run([str(args.pg_bin / "initdb"), "-D", str(pgdata), "-U", "postgres", "--auth=trust"],
                   check=True, capture_output=True)
    with (pgdata / "postgresql.conf").open("a") as f:
        f.write("\nshared_preload_libraries='timescaledb'\nmax_worker_processes=16\n"
                "timescaledb.max_background_workers=8\ntimescaledb.telemetry_level='off'\ntimezone='UTC'\n")
    env = dict(os.environ, PGHOST="127.0.0.1", PGPORT=str(pgport), PGDATABASE="postgres",
               PGUSER="postgres", PGSSLMODE="disable", STAGING_DEMO="1",
               DEV_USER_ID="00000000-0000-4000-8000-000000000001",
               STAGING_REGISTRY_FILE=str(config / "registry.json"), STAGING_SECRET_DIR=str(config / "secrets"),
               PYTHONPATH=str(ROOT / "src") + ":" + str(ROOT / "src/backend") + ":" + str(ROOT),
               MQTT_HOST="127.0.0.1", MQTT_PORT=str(mqttport),
               API_BASE_URL="http://127.0.0.1:" + str(apiport) + "/api/v1")
    subprocess.run([str(args.pg_bin / "pg_ctl"), "-D", str(pgdata), "-l", str(runtime / "postgres.log"),
                    "-o", "-h 127.0.0.1 -p " + str(pgport) + " -c unix_socket_directories=''", "-w", "start"],
                   check=True, capture_output=True, env=env)
    try:
        subprocess.run([sys.executable, str(ROOT / "tools/staging/migrate.py")], env=env, check=True, cwd=ROOT)
        subprocess.run(["cc", "-fPIC", "-shared", "-O2", "-I" + str(args.mosquitto_include),
                        "-o", str(runtime / "retain.so"), str(ROOT / "deploy/staging/retain_policy.c")], check=True)
        (runtime / "mqtt-data").mkdir()
        broker_config = (ROOT / "deploy/staging/mosquitto.conf").read_text()
        replacements = {
            "/mosquitto/data/": str(runtime / "mqtt-data") + "/",
            "/usr/local/lib/pccom-retain.so": str(runtime / "retain.so"),
            "/run/pki/ca.crt": str(config / "pki/server/ca.crt"),
            "/run/pki/server.crt": str(config / "pki/server/client.crt"),
            "/run/pki/server.key": str(config / "pki/server/client.key"),
            "/run/config/acl": str(config / "acl"),
            "listener 8883": "listener " + str(mqttport) + " 127.0.0.1",
        }
        for before, after in replacements.items():
            broker_config = broker_config.replace(before, after)
        (runtime / "mosquitto.conf").write_text(broker_config)
        with process([str(args.mosquitto), "-c", str(runtime / "mosquitto.conf")], env, runtime / "broker.log"):
            wait_for(lambda: socket.create_connection(("127.0.0.1", mqttport), timeout=1).close() is None)
            listeners = [line for line in (runtime / "broker.log").read_text().splitlines()
                         if "Opening " in line and "listen socket" in line]
            assert listeners and all("port " + str(mqttport) + "." in line for line in listeners), listeners
            ingest = dict(env, PGUSER="pccom_ingestion", PGPASSWORD_FILE=str(config / "secrets/db_ingestion"),
                          SKIP_MIGRATIONS="1", INGESTION_ENFORCE_ROUTES="1",
                          MQTT_TOPICS="telemetry/v1/#,pccom/lighting/+/+/telemetry,pccom/v1/+/+/+/telemetry",
                          MQTT_CA_FILE=str(config / "pki/svc-ingestion/ca.crt"),
                          MQTT_CERT_FILE=str(config / "pki/svc-ingestion/client.crt"),
                          MQTT_KEY_FILE=str(config / "pki/svc-ingestion/client.key"))
            api = dict(env, PGUSER="pccom_api", PGPASSWORD_FILE=str(config / "secrets/db_api"),
                       JWT_SECRET_FILE=str(config / "secrets/jwt"),
                       DEV_PASSWORD_FILE=str(config / "secrets/operator_password"), DEV_USERNAME="staging-operator",
                       SIGNING_SECRET_FILE=str(config / "secrets/signing"),
                       MQTT_CA=str(config / "pki/svc-web-gateway/ca.crt"),
                       MQTT_CERT=str(config / "pki/svc-web-gateway/client.crt"),
                       MQTT_KEY=str(config / "pki/svc-web-gateway/client.key"))
            with process([sys.executable, "-m", "ingestion.worker"], ingest, runtime / "ingestion.log"), \
                 process([sys.executable, "-m", "uvicorn", "staging_api.main:app", "--host", "127.0.0.1", "--port", str(apiport)],
                         api, runtime / "api.log"):
                def api_ready():
                    with urlopen("http://127.0.0.1:" + str(apiport) + "/health", timeout=2) as r:
                        return json.load(r)["mqtt"]
                wait_for(api_ready)
                wait_for(lambda: "MQTT_READY" in (runtime / "ingestion.log").read_text())
                verify_env = dict(env, MQTT_CA_FILE=str(config / "pki/svc-test/ca.crt"),
                                  MQTT_CERT_FILE=str(config / "pki/svc-test/client.crt"),
                                  MQTT_KEY_FILE=str(config / "pki/svc-test/client.key"),
                                  MQTT_HEALTH_CERT=str(config / "pki/svc-health/client.crt"),
                                  MQTT_HEALTH_KEY=str(config / "pki/svc-health/client.key"))
                os.environ.update(verify_env)
                from tools.staging.verify import run
                run((lambda: browser_smoke("http://127.0.0.1:" + str(apiport))) if args.browser else None)
                print(json.dumps({"native_integration": "PASS", "runtime_logs": str(runtime)}), flush=True)
    finally:
        subprocess.run([str(args.pg_bin / "pg_ctl"), "-D", str(pgdata), "-m", "fast", "stop"],
                       capture_output=True, env=env)
        print("NATIVE_LOGS=" + str(runtime), flush=True)


if __name__ == "__main__":
    main()
