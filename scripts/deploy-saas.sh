#!/usr/bin/env bash
# Rsync this repo's servable assets to aiproxy-saas Caddy /var/www/agentu.
# Used by GitHub Actions on push to github main, and as a local emergency path.
# Does not touch proxy.agentu.ai / POR / DNS.
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-ubuntu@52.21.140.15}"
REMOTE_STAGE="${REMOTE_STAGE:-/tmp/agentu-stage}"
WEB_ROOT="${WEB_ROOT:-/var/www/agentu}"
SITE_URL="${SITE_URL:-https://agentu.ai}"
SSH_OPTS="${SSH_OPTS:--o BatchMode=yes -o IdentitiesOnly=yes}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f "${REPO_DIR}/index.html" ]; then
  echo "✗ ${REPO_DIR}/index.html not found" >&2
  exit 1
fi

RSYNC_SSH="ssh ${SSH_OPTS}"
if [ -n "${DEPLOY_SSH_KEY:-}" ] && [ -f "${DEPLOY_SSH_KEY}" ]; then
  RSYNC_SSH="ssh ${SSH_OPTS} -i ${DEPLOY_SSH_KEY}"
fi

echo "→ Stage to ${REMOTE_HOST}:${REMOTE_STAGE}"
${RSYNC_SSH} "${REMOTE_HOST}" "rm -rf ${REMOTE_STAGE} && mkdir -p ${REMOTE_STAGE}"
rsync -avz -e "${RSYNC_SSH}" \
  --include '*/' \
  --include '*.html' --include '*.css' --include '*.js' --include '*.json' \
  --include '*.png' --include '*.jpg' --include '*.jpeg' \
  --include '*.svg' --include '*.ico' --include '*.webp' --include '*.woff*' \
  --exclude '*' \
  "${REPO_DIR}/" "${REMOTE_HOST}:${REMOTE_STAGE}/"

echo "→ Sync into ${WEB_ROOT} (caddy-owned)"
${RSYNC_SSH} "${REMOTE_HOST}" "sudo mkdir -p ${WEB_ROOT} && \
  sudo rsync -a --delete ${REMOTE_STAGE}/ ${WEB_ROOT}/ && \
  sudo chown -R caddy:caddy ${WEB_ROOT} && \
  sudo find ${WEB_ROOT} -type d -exec chmod 755 {} + && \
  sudo find ${WEB_ROOT} -type f -exec chmod 644 {} + && \
  rm -rf ${REMOTE_STAGE}"

echo "→ Verify"
code=$(curl -sS -o /dev/null -w '%{http_code}' -L "${SITE_URL}/version.json")
echo "  ${SITE_URL}/version.json -> HTTP ${code}"
if [ "${code}" != "200" ]; then
  echo "✗ version.json did not return 200" >&2
  exit 1
fi
echo "✓ Deploy complete: ${SITE_URL}"
