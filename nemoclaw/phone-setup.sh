#!/usr/bin/env bash
# Phone line for the dealer agents: public HTTPS for /twilio/* only, in front of the private backend.
# Run on the droplet as root:  bash /root/dealer/nemoclaw/phone-setup.sh
# Needs in /root/.dealer.env first: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_ALLOWED_CALLER (your phone, +1...).
# Optional: NVIDIA_API_KEY (Parakeet + Magpie voice; without it Twilio's own speech is used).
set -euo pipefail

ENV_FILE=/root/.dealer.env
BACKEND=10.120.0.2:8000
IP=$(curl -s -4 https://ifconfig.me)
HOST="${IP//./-}.sslip.io"   # free hostname that resolves to this IP, so Caddy can get a real TLS certificate
URL="https://$HOST"

for k in TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_ALLOWED_CALLER; do
  grep -qE "^$k=.+" "$ENV_FILE" || { echo "Missing $k in $ENV_FILE. Add it, then run this again."; exit 1; }
done

# 1. Caddy (HTTPS reverse proxy). Only /twilio/* is exposed; the rest of the API stays private.
if ! command -v caddy >/dev/null; then
  apt-get update -qq && apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi
cat > /etc/caddy/Caddyfile <<EOF
$HOST {
    handle /twilio/* {
        reverse_proxy $BACKEND
    }
    handle {
        respond "not found" 404
    }
}
EOF
systemctl reload caddy || systemctl restart caddy

# 2. Tell the backend its public address (Twilio signs requests with it), then restart the backend.
sed -i '/^PUBLIC_BASE_URL=/d' "$ENV_FILE"
echo "PUBLIC_BASE_URL=$URL" >> "$ENV_FILE"
systemctl restart dealer-backend
sleep 4

# 3. Check.
echo
curl -s "http://$BACKEND/twilio/status"; echo
echo
echo "In the Twilio console: Phone Numbers > your number > Voice > 'A call comes in':"
echo "  Webhook  $URL/twilio/voice   (HTTP POST)"
echo "Then call the number from the phone in TWILIO_ALLOWED_CALLER."
