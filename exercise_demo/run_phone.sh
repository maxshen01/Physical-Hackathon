#!/bin/sh
# Usage: ./exercise_demo/run_phone.sh 192.168.1.42
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PHONE_HOST=${1:-$(ipconfig getifaddr en0 2>/dev/null || true)}
if [ -z "$PHONE_HOST" ]; then
  echo 'Pass the laptop Wi-Fi IPv4 address: ./exercise_demo/run_phone.sh 192.168.1.42' >&2
  exit 1
fi
# Only IPv4 addresses are accepted so the certificate configuration stays literal.
case "$PHONE_HOST" in *[!0-9.]*|.*|*..*|*.) echo 'Use the laptop Wi-Fi IPv4 address.' >&2; exit 1;; esac
if ! command -v openssl >/dev/null 2>&1; then
  echo 'OpenSSL is required to create local HTTPS certificates.' >&2
  exit 1
fi
PHONE_PORT=${PHONE_PORT:-8443}
umask 077
TLS_DIR="$ROOT/.cache/tls"
mkdir -p "$TLS_DIR"
chmod 700 "$TLS_DIR"
if [ ! -f "$TLS_DIR/demo-ca-key.pem" ] || [ ! -f "$TLS_DIR/demo-ca.pem" ]; then
  cat > "$TLS_DIR/ca.conf" <<'CONFIG'
[req]
prompt = no
distinguished_name = dn
x509_extensions = ca_ext
[dn]
CN = Move Local Demo CA
[ca_ext]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
CONFIG
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -sha256 -config "$TLS_DIR/ca.conf" -keyout "$TLS_DIR/demo-ca-key.pem" -out "$TLS_DIR/demo-ca.pem"
fi
# DER certificate for AirDrop/profile installation; contains no private key.
openssl x509 -in "$TLS_DIR/demo-ca.pem" -outform DER -out "$TLS_DIR/move-demo-ca.cer"
cat > "$TLS_DIR/server.conf" <<CONFIG
[req]
prompt = no
distinguished_name = dn
[dn]
CN = $PHONE_HOST
[server_ext]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @names
[names]
IP.1 = $PHONE_HOST
IP.2 = 127.0.0.1
DNS.1 = localhost
CONFIG
openssl req -newkey rsa:2048 -nodes -sha256 -config "$TLS_DIR/server.conf" -keyout "$TLS_DIR/phone-key.pem" -out "$TLS_DIR/phone.csr"
openssl x509 -req -in "$TLS_DIR/phone.csr" -CA "$TLS_DIR/demo-ca.pem" -CAkey "$TLS_DIR/demo-ca-key.pem" -CAcreateserial -days 14 -sha256 -extfile "$TLS_DIR/server.conf" -extensions server_ext -out "$TLS_DIR/phone.pem"
chmod 600 "$TLS_DIR/"*
echo "Transfer and trust ONLY: $TLS_DIR/move-demo-ca.cer"
echo "Never transfer files containing 'key'."
echo "Open https://$PHONE_HOST:$PHONE_PORT on your phone (same Wi-Fi)."
if [ "${PHONE_CERT_ONLY:-0}" = 1 ]; then exit 0; fi
cd "$ROOT/exercise_demo"
exec "$ROOT/.venv/bin/python" -m uvicorn server:app --host 0.0.0.0 --port "$PHONE_PORT" --ssl-certfile "$TLS_DIR/phone.pem" --ssl-keyfile "$TLS_DIR/phone-key.pem"
