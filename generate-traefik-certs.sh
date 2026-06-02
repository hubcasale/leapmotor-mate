#!/bin/sh
set -e

CERT_DIR="./traefik/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/traefik.crt" ] && [ -f "$CERT_DIR/traefik.key" ]; then
  echo "Traefik certificates already exist in $CERT_DIR, skipping generation."
  echo "Delete them and re-run to regenerate."
  exit 0
fi

# Build SAN list: localhost + 127.0.0.1 + all local IPs + any extra args
SAN="DNS:localhost,IP:127.0.0.1"
for ip in $(hostname -I 2>/dev/null); do
  SAN="$SAN,IP:$ip"
done
# Add extra IPs/hostnames passed as arguments
for arg in "$@"; do
  case "$arg" in
    [0-9]*) SAN="$SAN,IP:$arg" ;;
    *)      SAN="$SAN,DNS:$arg" ;;
  esac
done

echo "Generating self-signed certificate for Traefik HTTPS..."
echo "SAN: $SAN"
openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/traefik.key" \
  -out "$CERT_DIR/traefik.crt" \
  -subj "/CN=leapconnect" \
  -addext "subjectAltName=$SAN"

echo "Certificates generated in $CERT_DIR"
