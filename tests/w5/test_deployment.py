import json
from pathlib import Path
import subprocess
import yaml
import pytest
from tools.staging.bootstrap import demo_registry, generate

ROOT = Path(__file__).resolve().parents[2]


def test_internal_pki_purposes_permissions_and_no_overwrite(tmp_path):
    target = tmp_path / "runtime"
    generate("staging.example.test", demo_registry(), target, demo=True)
    ca = target / "ca/ca.crt"
    for purpose, path in [("sslserver", target / "pki/server/client.crt"),
                          ("sslclient", target / "pki/svc-web-gateway/client.crt")]:
        r = subprocess.run(["openssl", "verify", "-CAfile", str(ca), "-purpose", purpose, str(path)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    verify_host = subprocess.run(["openssl", "x509", "-in", str(target / "pki/server/client.crt"),
                                 "-noout", "-checkhost", "staging.example.test"], capture_output=True)
    assert verify_host.returncode == 0
    assert target.stat().st_mode & 0o777 == 0o700
    assert (target / "ca/ca.key").stat().st_mode & 0o777 == 0o600
    assert (target / "secrets/jwt").stat().st_mode & 0o777 == 0o444
    assert len(json.loads((target / "certificates.json").read_text())) == 4
    acl = (target / "acl").read_text()
    assert "user svc-test" in acl and "topic readwrite #" not in acl
    with pytest.raises(ValueError, match="already exists"):
        generate("another.test", demo_registry(), target, demo=True)


def test_compose_paths_and_public_ports():
    compose = yaml.safe_load((ROOT / "docker-compose.staging.yml").read_text())
    assert len(compose["services"]) == 13
    assert not compose["services"]["timescaledb"].get("ports")
    assert not compose["services"]["api"].get("ports")
    assert compose["services"]["mosquitto"]["ports"] == ["8883:8883"]
    for name, service in compose["services"].items():
        for port in service.get("ports", []):
            if name not in ("mosquitto", "web"):
                assert port.startswith("127.0.0.1:")
        if "build" in service:
            assert (ROOT / service["build"]["dockerfile"]).is_file()
        for volume in service.get("volumes", []):
            source = volume.split(":")[0]
            if source.startswith("./") and not source.startswith("./.staging/"):
                assert (ROOT / source).exists(), source
    assert compose["services"]["socket-proxy"]["environment"]["POST"] == "0"
    assert ".staging/pki/server" not in str(compose["services"]["api"]["volumes"])
