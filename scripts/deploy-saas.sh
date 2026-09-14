#!/usr/bin/env bash
# Rsync this repo's servable assets to aiproxy-saas Caddy /var/www/agentu.
# GitHub Actions (self-hosted on saas): DEPLOY_LOCAL=1
# Mac emergency: Host awsgit / ubuntu@52.21.140.15 (SG-allowlisted IPs only)
# Does not touch proxy.agentu.ai / POR / DNS.
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-ubuntu@52.21.140.15}"
REMOTE_STAGE="${REMOTE_STAGE:-/tmp/agentu-stage}"
WEB_ROOT="${WEB_ROOT:-/var/www/agentu}"
SITE_URL="${SITE_URL:-https://agentu.ai}"
SSH_OPTS="${SSH_OPTS:--o BatchMode=yes -o IdentitiesOnly=yes}"
DEPLOY_LOCAL="${DEPLOY_LOCAL:-0}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f "${REPO_DIR}/index.html" ]; then
  echo "✗ ${REPO_DIR}/index.html not found" >&2
  exit 1
fi

stage_payload() {
  local dest="$1"
  rsync -a --delete \
    --include '*/' \
    --include '*.html' --include '*.css' --include '*.js' --include '*.json' \
    --include '*.png' --include '*.jpg' --include '*.jpeg' \
    --include '*.svg' --include '*.ico' --include '*.webp' --include '*.woff*' \
    --exclude '*' \
    "${REPO_DIR}/" "${dest}/"
}

install_web_root() {
  local src="$1"
  sudo mkdir -p "${WEB_ROOT}"
  sudo rsync -a --delete "${src}/" "${WEB_ROOT}/"
  sudo chown -R caddy:caddy "${WEB_ROOT}"
  sudo find "${WEB_ROOT}" -type d -exec chmod 755 {} +
  sudo find "${WEB_ROOT}" -type f -exec chmod 644 {} +
}

if [ "${DEPLOY_LOCAL}" = "1" ]; then
  echo "→ Local stage ${REMOTE_STAGE}"
  rm -rf "${REMOTE_STAGE}" && mkdir -p "${REMOTE_STAGE}"
  stage_payload "${REMOTE_STAGE}"
  echo "→ Sync into ${WEB_ROOT} (caddy-owned)"
  install_web_root "${REMOTE_STAGE}"
  rm -rf "${REMOTE_STAGE}"
else
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
fi

echo "→ Verify"
code=$(curl -sS -o /dev/null -w '%{http_code}' -L "${SITE_URL}/version.json")
echo "  ${SITE_URL}/version.json -> HTTP ${code}"
if [ "${code}" != "200" ]; then
  echo "✗ version.json did not return 200" >&2
  exit 1
fi
echo "✓ Deploy complete: ${SITE_URL}"
