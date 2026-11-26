#!/usr/bin/env bash
#
# setup-site.sh: put the dictionary on https://dict.darmok.link, behind
# devauth like every other dev site.
#
#     sudo /home/james/dict/deploy/setup-site.sh
#
# Each step is skipped when already done:
#   1. A Let's Encrypt certificate by DNS-01 through DigitalOcean, with the
#      credentials the existing certificates renew with (same as fitlog and mindlog).
#   2. The nginx site from deploy/nginx-dict, enabled.
#   3. nginx -t (the site removed again if it fails), reload, checks.
#
# The app itself is a user service (systemctl --user status dict), not
# touched here.

set -euo pipefail

DOMAIN=dict.darmok.link
SITE_SRC=/home/james/dict/deploy/nginx-dict
SITE=/etc/nginx/sites-available/dict
SITE_LINK=/etc/nginx/sites-enabled/dict
LINEAGE=/etc/letsencrypt/live/$DOMAIN
REFERENCE_RENEWAL=/etc/letsencrypt/renewal/posture.darmok.link.conf

say()  { printf '\n==> %s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || fail "run with sudo"
[[ -f $SITE_SRC ]] || fail "$SITE_SRC missing"
[[ -f /etc/nginx/snippets/devauth-guard.conf ]] || fail "devauth is not installed"
getent hosts "$DOMAIN" >/dev/null || echo "warning: $DOMAIN does not resolve yet"
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8793/ || true)
[[ $code == 200 ]] || fail "the dict service isn't answering on 127.0.0.1:8793 (systemctl --user status dict)"

# --- 1. certificate ---------------------------------------------------------
say "certificate"
if [[ -f $LINEAGE/fullchain.pem ]]; then
    echo "already have $LINEAGE"
else
    [[ -f $REFERENCE_RENEWAL ]] || fail "no $REFERENCE_RENEWAL to copy the DNS credentials from"
    creds=$(sed -n 's/^dns_digitalocean_credentials *= *//p' "$REFERENCE_RENEWAL" | head -1)
    [[ -n $creds && -f $creds ]] || fail "the existing certificate does not renew by dns-digitalocean"
    propagation=$(sed -n 's/^dns_digitalocean_propagation_seconds *= *//p' "$REFERENCE_RENEWAL" | head -1)
    certbot certonly --non-interactive --agree-tos \
        --authenticator dns-digitalocean \
        --dns-digitalocean-credentials "$creds" \
        --dns-digitalocean-propagation-seconds "${propagation:-60}" \
        --cert-name "$DOMAIN" -d "$DOMAIN" \
        --deploy-hook "systemctl reload nginx"
    [[ -f $LINEAGE/fullchain.pem ]] || fail "certbot did not produce $LINEAGE"
fi

# --- 2. nginx ---------------------------------------------------------------
say "nginx"
install -m 644 -o root -g root "$SITE_SRC" "$SITE"
ln -sfn "$SITE" "$SITE_LINK"
if ! nginx -t; then
    rm -f "$SITE_LINK"
    fail "nginx -t failed; removed the new site"
fi
systemctl reload nginx
echo "enabled $SITE_LINK"

# --- 3. checks --------------------------------------------------------------
say "checks"
code=000
for _ in 1 2 3 4 5; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/about" 2>/dev/null || true)
    # 200 with a devauth session, 401/302 without one: either way nginx and the gate answer.
    [[ $code =~ ^(200|302|401)$ ]] && break
    sleep 1
done
[[ $code =~ ^(200|302|401)$ ]] || fail "https://$DOMAIN/api/about through nginx answered $code"
echo "https://$DOMAIN answers $code through nginx"
sudo -u james /home/james/darmok/gen-status.sh && echo "status.json refreshed"

printf '\nDone. https://%s is up behind the devauth login.\n' "$DOMAIN"
