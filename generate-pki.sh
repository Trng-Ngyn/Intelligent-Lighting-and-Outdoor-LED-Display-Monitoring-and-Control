#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

output=generated
if [[ -e "$output" || -L "$output" ]]; then
  printf '%s\n' "generated/ already exists. Move the lab directory aside to create a fresh PKI." >&2
  exit 1
fi
temporary="$(mktemp -d .pki.XXXXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT
cd "$temporary"

make_ca() {
  local name=$1
  mkdir -p "ca/$name/newcerts"
  touch "ca/$name/index"
  printf '1000\n' > "ca/$name/serial"
  printf '1000\n' > "ca/$name/crlnumber"
  openssl req -new -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -noenc \
    -sha256 -days 30 -subj "/CN=PCCOM dev $name CA" \
    -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' \
    -addext 'keyUsage=critical,keyCertSign,cRLSign' \
    -addext 'subjectKeyIdentifier=hash' \
    -keyout "ca/$name/ca.key" -out "ca/$name/ca.crt"
  cat > "ca/$name/ca.cnf" <<CONFIG
[ca]
default_ca = issuer
[issuer]
database = ca/$name/index
new_certs_dir = ca/$name/newcerts
certificate = ca/$name/ca.crt
private_key = ca/$name/ca.key
serial = ca/$name/serial
crlnumber = ca/$name/crlnumber
default_md = sha256
default_days = 7
default_crl_days = 14
policy = subject_policy
copy_extensions = none
unique_subject = no
[subject_policy]
commonName = supplied
CONFIG
}

issue() {
  local ca_name=$1 target=$2 identity=$3 ek_use=$4 san=$5
  mkdir -p "$(dirname -- "$target")"
  openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -noenc \
    -subj "/CN=$identity" -keyout "$target.key" -out "$target.csr"
  cat > "$target.ext" <<EXTENSIONS
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=$ek_use
subjectAltName=$san
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EXTENSIONS
  openssl ca -batch -config "ca/$ca_name/ca.cnf" -extfile "$target.ext" \
    -notext -in "$target.csr" -out "$target.crt"
  rm -- "$target.csr" "$target.ext"
}

make_ca server
make_ca device
make_ca service
issue server mqtt/mqtt mqtt.dev.pccom.test serverAuth DNS:mqtt.dev.pccom.test
issue server edge-api/edge-api edge-api.dev.pccom.test serverAuth DNS:edge-api.dev.pccom.test
issue device test-clients/gw-001 gw-001 clientAuth URI:urn:pccom:dev:t1:s01:gw-001
issue device test-clients/gw-002 gw-002 clientAuth URI:urn:pccom:dev:t1:s02:gw-002
# Bridge identity riêng cho gateway-level per-device authorization.
issue device test-clients/bridge-s01 bridge-s01 clientAuth URI:urn:pccom:dev:t1:s01:bridge-s01
issue device test-clients/bridge-s02 bridge-s02 clientAuth URI:urn:pccom:dev:t1:s02:bridge-s02
issue device test-clients/unknown gw-unknown clientAuth URI:urn:pccom:dev:t1:s01:gw-unknown
issue device test-clients/revoked gw-revoked clientAuth URI:urn:pccom:dev:t1:s01:gw-revoked
issue service test-clients/dispatcher dispatcher clientAuth URI:urn:pccom:dev:service:dispatcher

openssl ca -config ca/device/ca.cnf -revoke test-clients/revoked.crt
openssl ca -config ca/device/ca.cnf -gencrl -out mqtt/device-ca.crl
cp mqtt/device-ca.crl edge-api/
cp ca/device/ca.crt mqtt/device-ca.crt
cp ca/device/ca.crt edge-api/device-ca.crt
cp ca/service/ca.crt mqtt/service-ca.crt
cp ca/server/ca.crt test-clients/server-ca.crt
for identity in gw-001 gw-002; do
  serial="$(openssl x509 -in "test-clients/$identity.crt" -noout -serial)"
  printf 'SUCCESS:%s %s;\n' "${serial#serial=}" "$identity"
done > edge-api/enrolled.map

cd ..
mv -- "$temporary" "$output"
printf 'LAB_UID=%s\nLAB_GID=%s\n' "$(id -u)" "$(id -g)" > compose.env
