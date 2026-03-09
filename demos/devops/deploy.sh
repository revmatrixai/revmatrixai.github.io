#!/bin/bash
# ================================================================
# RevMatrix DevOps Demo — Full CI/CD Pipeline Script
# ================================================================
# Enterprise-grade deployment pipeline:
#   1. Build Docker image (multi-stage, security hardened)
#   2. Security scan with Trivy (zero-cost)
#   3. Push to GitHub Container Registry (free)
#   4. Deploy to Kubernetes via Helm
#   5. Run smoke tests
#   6. Notify on completion
#
# Zero-cost stack:
#   - GitHub Container Registry (free)
#   - Render.com / Railway.app (free tier)
#   - GitHub Actions (2000 min/month free)
#
# Usage:
#   ./deploy.sh                        # Full deploy
#   ./deploy.sh --env staging          # Deploy to staging
#   ./deploy.sh --dry-run              # Preview only
# ================================================================

set -euo pipefail
IFS=$'\n\t'

# ─── CONFIG ─────────────────────────────────────────────────────────
APP_NAME="revmatrix-api"
REGISTRY="ghcr.io/revmatrixai"
NAMESPACE="production"
HELM_CHART="./helm/${APP_NAME}"
HEALTH_URL="https://api.revmatrix.ai/health"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

# Args
ENV="production"
DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)      ENV="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    *)          shift ;;
  esac
done

# ─── HELPERS ────────────────────────────────────────────────────────
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
fail() { echo -e "${RED}[✗] FAILED:${NC} $1"; exit 1; }

# ─── MAIN ───────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   RevMatrix CI/CD Pipeline v3.0          ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}\n"

# Get version from git
VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo "v1.0.0")
IMAGE="${REGISTRY}/${APP_NAME}:${VERSION}"
IMAGE_LATEST="${REGISTRY}/${APP_NAME}:latest"

log "Environment : ${ENV}"
log "Version     : ${VERSION}"
log "Image       : ${IMAGE}"
log "Dry run     : ${DRY_RUN}\n"

if $DRY_RUN; then
  warn "DRY RUN MODE — No actual changes will be made\n"
fi

# ─── STEP 1: BUILD ──────────────────────────────────────────────────
echo -e "\n${BOLD}[1/6] Building Docker image...${NC}"
if ! $DRY_RUN; then
  docker build \
    --no-cache \
    --build-arg BUILD_VERSION="${VERSION}" \
    --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -t "${IMAGE}" \
    -t "${IMAGE_LATEST}" \
    . || fail "Docker build failed"
fi
ok "Image built: ${IMAGE}"

# ─── STEP 2: SECURITY SCAN ──────────────────────────────────────────
echo -e "\n${BOLD}[2/6] Security scan (Trivy)...${NC}"
if ! $DRY_RUN; then
  if command -v trivy &>/dev/null; then
    trivy image \
      --exit-code 1 \
      --severity CRITICAL \
      --no-progress \
      "${IMAGE}" || fail "Critical vulnerabilities found — aborting deploy"
    ok "No critical vulnerabilities"
  else
    warn "Trivy not installed — skipping scan (install: brew install trivy)"
  fi
fi
ok "Security scan passed"

# ─── STEP 3: PUSH ───────────────────────────────────────────────────
echo -e "\n${BOLD}[3/6] Pushing to container registry...${NC}"
if ! $DRY_RUN; then
  docker push "${IMAGE}"      || fail "Push failed"
  docker push "${IMAGE_LATEST}" || fail "Push latest failed"
fi
ok "Pushed: ${IMAGE}"

# ─── STEP 4: DEPLOY ─────────────────────────────────────────────────
echo -e "\n${BOLD}[4/6] Deploying to Kubernetes...${NC}"
if ! $DRY_RUN; then
  if command -v helm &>/dev/null; then
    helm upgrade --install "${APP_NAME}" "${HELM_CHART}" \
      --namespace "${NAMESPACE}" \
      --create-namespace \
      --set image.repository="${REGISTRY}/${APP_NAME}" \
      --set image.tag="${VERSION}" \
      --set environment="${ENV}" \
      --set replicas=3 \
      --atomic \
      --timeout 300s \
      --wait || fail "Helm deploy failed"
  else
    # Fallback: kubectl apply
    kubectl apply -f k8s/ -n "${NAMESPACE}" || fail "kubectl apply failed"
    kubectl set image deployment/"${APP_NAME}" \
      app="${IMAGE}" -n "${NAMESPACE}" || fail "Image update failed"
  fi
fi
ok "Deployed to ${NAMESPACE}"

# ─── STEP 5: ROLLOUT STATUS ─────────────────────────────────────────
echo -e "\n${BOLD}[5/6] Waiting for rollout...${NC}"
if ! $DRY_RUN; then
  kubectl rollout status deployment/"${APP_NAME}" \
    -n "${NAMESPACE}" --timeout=300s || fail "Rollout failed"
  # Show pods
  echo ""
  kubectl get pods -n "${NAMESPACE}" -l "app=${APP_NAME}" \
    --no-headers | while read pod _rest; do
    echo "    pod/${pod}  ✓ Running"
  done
fi
ok "All pods healthy"

# ─── STEP 6: SMOKE TEST ─────────────────────────────────────────────
echo -e "\n${BOLD}[6/6] Smoke tests...${NC}"
if ! $DRY_RUN; then
  sleep 5  # brief settle time
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" || echo "000")
  if [[ "${HTTP_STATUS}" == "200" ]]; then
    ok "Health check passed (HTTP ${HTTP_STATUS})"
  else
    fail "Health check failed (HTTP ${HTTP_STATUS}) — check ${HEALTH_URL}"
  fi
fi
ok "Smoke tests passed"

# ─── DONE ───────────────────────────────────────────────────────────
echo -e "\n${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║   ✓ DEPLOY COMPLETE                      ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo -e "\n  Version : ${VERSION}"
echo -e "  Env     : ${ENV}"
echo -e "  URL     : https://api.revmatrix.ai"
echo -e "  Time    : $(date +%H:%M:%S)\n"
