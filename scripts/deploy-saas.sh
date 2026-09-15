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

# Build stamp is GENERATED here, never read from the committed version.json.
# A hand-edited stamp goes stale silently and then names a build that is not
# what is on disk -- which is worse than no stamp, because version.json is the
# surface people check to confirm a deploy landed.
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
GIT_DIRTY=""
git diff --quiet HEAD -- 2>/dev/null || GIT_DIRTY="-dirty"
BUILD="$(date -u +%Y%m%d-%H%M%S)-${GIT_SHA}${GIT_DIRTY}"
VERSION_JSON="$(printf '{"build":"%s","commit":"%s","deployed_at":"%s"}' \
  "${BUILD}" "${GIT_SHA}${GIT_DIRTY}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
echo "→ Build ${BUILD}"

if [ ! -f "${REPO_DIR}/index.html" ]; then
  echo "✗ ${REPO_DIR}/index.html not found" >&2
  exit 1
fi

stage_payload() {
  local dest="$1"
  rsync -a --delete \
    --exclude '.git/' --exclude '.github/' --exclude 'scripts/' \
    --exclude '.gitignore' --exclude 'CLAUDE.md' --exclude '.DS_Store' \
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
  printf '%s\n' "${VERSION_JSON}" > "${REMOTE_STAGE}/version.json"
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
    --exclude '.git/' --exclude '.github/' --exclude 'scripts/' \
    --exclude '.gitignore' --exclude 'CLAUDE.md' --exclude '.DS_Store' \
    --include '*/' \
    --include '*.html' --include '*.css' --include '*.js' --include '*.json' \
    --include '*.png' --include '*.jpg' --include '*.jpeg' \
    --include '*.svg' --include '*.ico' --include '*.webp' --include '*.woff*' \
    --exclude '*' \
    "${REPO_DIR}/" "${REMOTE_HOST}:${REMOTE_STAGE}/"
  ${RSYNC_SSH} "${REMOTE_HOST}" "printf '%s\\n' '${VERSION_JSON}' > ${REMOTE_STAGE}/version.json"
  echo "→ Sync into ${WEB_ROOT} (caddy-owned)"
  ${RSYNC_SSH} "${REMOTE_HOST}" "sudo mkdir -p ${WEB_ROOT} && \
    sudo rsync -a --delete ${REMOTE_STAGE}/ ${WEB_ROOT}/ && \
    sudo chown -R caddy:caddy ${WEB_ROOT} && \
    sudo find ${WEB_ROOT} -type d -exec chmod 755 {} + && \
    sudo find ${WEB_ROOT} -type f -exec chmod 644 {} + && \
    rm -rf ${REMOTE_STAGE}"
fi

echo "→ Verify"
# Cache-buster: a cached version.json would confirm the PREVIOUS deploy.
served="$(curl -sS -L -H 'Cache-Control: no-cache' "${SITE_URL}/version.json?cb=${BUILD}" || true)"
echo "  ${SITE_URL}/version.json -> ${served:-<empty>}"
case "${served}" in
  *"\"${BUILD}\""*) ;;
  *)
    echo "✗ served version.json does not carry build ${BUILD}" >&2
    echo "  the rsync did not land, or something is serving a stale copy" >&2
    exit 1
    ;;
esac
echo "✓ Deploy complete: ${SITE_URL} (build ${BUILD})"
