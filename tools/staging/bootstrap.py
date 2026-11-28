"""Generate local-only secrets, Internal PKI and ACL. Never overwrite a live PKI."""

import argparse
import ipaddress
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ingestion.registry import validate_registry  # noqa: E402
from ingestion.fixtures import demo_registry  # noqa: E402


def run(*args):
    subprocess.run(["openssl", *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def generate(host, registry, directory, demo=False):
    validate_registry(registry)
    if directory.exists():
        raise ValueError("Runtime directory already exists; refusing to rotate secrets or delete database data")
    if not host or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:" for c in host):
        raise ValueError("Use a bare hostname or IP address, without scheme/port")
    directory.mkdir(mode=0o700, parents=True)
    os.chmod(directory, 0o700)
    for child in ("pki", "ca", "secrets"):
        (directory / child).mkdir(mode=0o700)
    (directory / "registry.json").write_text(json.dumps(registry, indent=2))
    for name in ("db_admin", "db_api", "db_ingestion", "jwt", "operator_password", "signing", "grafana_password"):
        p = directory / "secrets" / name
        p.write_text(secrets.token_urlsafe(36))
        # Parent 0700 protects the host; individual bind-mounts must be readable
        # by container UIDs 1883, 10001 and Grafana. No CA key is ever mounted.
        os.chmod(p, 0o444)
    ca = directory / "ca"
    run("req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "3650", "-sha256",
        "-subj", "/CN=PCCOM Staging Internal CA", "-keyout", str(ca / "ca.key"), "-out", str(ca / "ca.crt"),
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    os.chmod(ca / "ca.key", 0o600)

    def certificate(identity, server=False):
        folder = directory / "pki" / identity
        folder.mkdir(mode=0o755)
        run("req", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256", "-subj", "/CN=" + identity,
            "-keyout", str(folder / "client.key"), "-out", str(folder / "request.csr"))
        extensions = "basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\n"
        extensions += "extendedKeyUsage=" + ("serverAuth" if server else "clientAuth") + "\n"
        if server:
            try:
                ipaddress.ip_address(host)
                target = "IP:" + host
            except ValueError:
                target = "DNS:" + host
            extensions += "subjectAltName=DNS:mosquitto,DNS:localhost,IP:127.0.0.1," + target + "\n"
        ext = folder / "extensions.cnf"
        ext.write_text(extensions)
        run("x509", "-req", "-in", str(folder / "request.csr"), "-CA", str(ca / "ca.crt"),
            "-CAkey", str(ca / "ca.key"), "-set_serial", str(secrets.randbits(128)), "-days", "365", "-sha256",
            "-extfile", str(ext), "-out", str(folder / "client.crt"))
        (folder / "ca.crt").write_bytes((ca / "ca.crt").read_bytes())
        (folder / "request.csr").unlink()
        ext.unlink()
        for p in folder.iterdir():
            os.chmod(p, 0o444)

    certificate("server", True)
    for identity in ("svc-ingestion", "svc-web-gateway", "svc-health"):
        certificate(identity)
    acl = [
        "user svc-ingestion", "topic read telemetry/v1/#", "topic read pccom/lighting/+/+/telemetry",
        "topic read pccom/v1/+/+/+/telemetry", "topic write dlq/v1/telemetry", "",
        "user svc-health", "topic readwrite staging/health", "",
        "user svc-web-gateway", "topic read commands/v1/+/+/+/dim/result",
        "topic read pccom/lighting/+/+/result", "topic read pccom/v1/+/+/+/ack",
    ]
    for a in registry["assets"]:
        dtype = "light" if a["kind"] == "lighting" else "led_display"
        base = a["field_site"] + "/" + dtype + "/" + a["device_code"]
        legacy = "pccom/lighting/" + a["field_site"] + "/" + a["device_code"]
        north = "pccom/v1/" + a["tenant_code"] + "/" + a["cloud_site"] + "/" + a["gateway_code"]
        acl += ["topic write commands/v1/" + base + "/dim", "topic write " + legacy + "/command", "topic write " + north + "/command"]
    gateways = set()
    certificate_map = []
    for a in registry["assets"]:
        identity = "esp32-" + a["device_id"]
        certificate(identity)
        certificate_map.append({"device_code": a["device_code"], "field_site": a["field_site"],
                                "identity": identity, "directory": "pki/" + identity})
        dtype = "light" if a["kind"] == "lighting" else "led_display"
        base = a["field_site"] + "/" + dtype + "/" + a["device_code"]
        legacy = "pccom/lighting/" + a["field_site"] + "/" + a["device_code"]
        acl += ["", "user " + identity, "topic write telemetry/v1/" + base,
                "topic write " + legacy + "/telemetry", "topic read " + legacy + "/command",
                "topic write " + legacy + "/result", "topic read commands/v1/" + base + "/dim",
                "topic write commands/v1/" + base + "/dim/result"]
        gateways.add((a["tenant_code"], a["cloud_site"], a["gateway_code"]))
    for tenant, site, gateway in gateways:
        identity = "gateway-" + hashlib.sha256((tenant + "/" + site + "/" + gateway).encode()).hexdigest()[:24]
        certificate(identity)
        certificate_map.append({"tenant_code": tenant, "cloud_site": site, "gateway_code": gateway,
                                "identity": identity, "directory": "pki/" + identity})
        north = "pccom/v1/" + tenant + "/" + site + "/" + gateway
        acl += ["", "user " + identity, "topic write " + north + "/telemetry", "topic write " + north + "/ack", "topic read " + north + "/command"]
    if demo:
        certificate("svc-test")
        acl += ["", "user svc-test", "topic readwrite telemetry/v1/W5_DEMO/#",
                "topic readwrite commands/v1/W5_DEMO/#", "topic read dlq/v1/telemetry"]
    (directory / "acl").write_text("\n".join(acl) + "\n")
    (directory / "certificates.json").write_text(json.dumps(certificate_map, indent=2))
    os.chmod(directory / "acl", 0o444)
    (directory / "compose.env").write_text(
        "STAGING_HOST=" + host + "\nSTAGING_DEMO=" + ("1" if demo else "0") + "\n")
    os.chmod(directory / "compose.env", 0o600)
    print("Generated runtime files in " + str(directory) + ". Keep .staging out of Git.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--registry", type=Path)
    group.add_argument("--demo", action="store_true")
    p.add_argument("--directory", type=Path, default=ROOT / ".staging")
    args = p.parse_args()
    document = demo_registry() if args.demo else json.loads(args.registry.read_text())
    if not args.demo and any(a.get("is_demo", False) for a in document["assets"]):
        p.error("Use --demo for synthetic assets; production registry must contain real identities")
    generate(args.host, document, args.directory, args.demo)
