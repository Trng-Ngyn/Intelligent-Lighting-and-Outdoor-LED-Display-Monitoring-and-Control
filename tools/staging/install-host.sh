#!/usr/bin/env bash
# Run on the designated Ubuntu/Debian VPS, before deploying the three packages.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo "Run on the VPS with: sudo bash tools/staging/install-host.sh"
  exit 1
fi
. /etc/os-release
case "$ID" in
  ubuntu|debian) ;;
  *) echo "Supported VPS distributions: Ubuntu or Debian"; exit 1 ;;
esac
apt-get update
apt-get install -y ca-certificates curl gnupg python3 python3-venv openssl git
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl --fail --silent --show-error --location "https://download.docker.com/linux/$ID/gpg" \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  cat > /etc/apt/sources.list.d/pccom-docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $VERSION_CODENAME
Components: stable
Architectures: $arch
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker version
docker compose version
echo "Host tools installed. Prepare the device registry and run tools/staging/deploy.sh."
echo "Set the VPS/provider firewall for your SSH access, HTTPS 443 and MQTT mTLS 8883."
echo "Database and monitoring admin ports stay internal or on loopback."
