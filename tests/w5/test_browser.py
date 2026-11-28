"""Optional real browser -> HTTP API -> disposable PostgreSQL smoke test."""

import os
from pathlib import Path
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import uvicorn
from ingestion.worker import Delivery
from ingestion.publish_demo import encode, topic_for
from test_ingestion import store, native


@pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Set RUN_BROWSER=1 and install Playwright/Chromium")
def test_browser_real_api_database(db, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    from staging_api import main
    monkeypatch.setattr(main.dispatcher, "start", lambda: None)
    monkeypatch.setattr(main.dispatcher, "stop", lambda: None)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api_port = sock.getsockname()[1]
    s = store(db)
    p = native()
    p["metrics"]["dimming_pct"] = {"value": 20, "unit": "%", "quality": "measured"}
    s.save_batch([Delivery(topic_for("lighting"), encode(p))])
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=api_port, log_level="warning"))
    api_thread = threading.Thread(target=server.run, daemon=True)
    api_thread.start()
    root = Path(__file__).resolve().parents[2]

    class WebHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root / "dist"), **kwargs)

        def log_message(self, *args):
            pass

        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            request = Request("http://127.0.0.1:" + str(api_port) + self.path, data=body,
                              headers={k: v for k, v in self.headers.items() if k.lower() != "host"}, method=self.command)
            try:
                response = urlopen(request, timeout=15)
            except HTTPError as exc:
                response = exc
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(response.read())

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self.forward()
            super().do_GET()

        do_POST = forward

    http = ThreadingHTTPServer(("127.0.0.1", 0), WebHandler)
    web_thread = threading.Thread(target=http.serve_forever, daemon=True)
    web_thread.start()
    errors = []
    try:
        with sync_playwright() as pw:
            executable = os.getenv("CHROMIUM_PATH")
            browser = pw.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("https://*.tile.openstreetmap.org/**", lambda r: r.abort())
            page.goto("http://127.0.0.1:" + str(http.server_port))
            page.get_by_label("Tài khoản", exact=True).fill("admin")
            page.get_by_label("Mật khẩu", exact=True).fill("test-only-operator-password-for-test-session")
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            expect(page.get_by_role("heading", name="Điều hành hệ thống")).to_be_visible()
            expect(page.get_by_role("cell").filter(has_text="W5_LIGHT_001")).to_be_visible()
            page.get_by_role("button", name="W5_LIGHT_001", exact=True).click()
            page.get_by_role("button", name="Gửi lệnh dimming", exact=True).click()
            expect(page.get_by_text("Đã xếp hàng", exact=False)).to_be_visible()
            assert db.execute("SELECT brightness,state FROM lighting.staging_commands").fetchone() == (50, "queued")
            # Show that clicking did NOT fabricate a new reported value.
            expect(page.locator(".reported")).to_contain_text("20")
            db.execute("UPDATE lighting.staging_commands SET state='sent',sent_at=clock_timestamp()-interval '1 second'")
            p = native(2)
            p["metrics"]["dimming_pct"] = {"value": 50, "unit": "%", "quality": "measured"}
            s.save_batch([Delivery(topic_for("lighting"), encode(p))])
            main.dispatcher.tick()
            expect(page.get_by_text("Telemetry đã xác nhận", exact=False)).to_be_visible(timeout=10000)
            expect(page.locator(".reported")).to_contain_text("50", timeout=10000)
            (root / "artifacts").mkdir(exist_ok=True)
            page.screenshot(path=str(root / "artifacts/frontend-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(root / "artifacts/frontend-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.get_by_label("Phạm vi gửi lệnh").select_option("group")
            page.get_by_role("button", name="Gửi lệnh dimming", exact=True).click()
            expect(page.get_by_text("Gửi tới 2 cột đèn.", exact=False)).to_be_visible()
            expect(page.get_by_text("Đã xếp hàng", exact=False).first).to_be_visible()
            assert db.execute("SELECT count(*) FROM lighting.staging_commands WHERE state='queued'").fetchone()[0] == 2
            page.route("**/api/v1/console/assets", lambda r: r.abort())
            expect(page.get_by_text("Gián đoạn API", exact=True)).to_be_visible(timeout=15000)
            assert not errors, errors
            browser.close()
    finally:
        http.shutdown()
        server.should_exit = True
        api_thread.join(10)
