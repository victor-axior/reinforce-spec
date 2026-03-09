#!/bin/sh
set -eu

BOOTSTRAP_POLICY_DIR="/app/bootstrap/policies"
DATA_POLICY_DIR="/app/data/policies"

emit_status() {
  stage="$1"
  status="$2"
  message="$3"
  printf 'RS_STATUS:{"stage":"%s","status":"%s","message":"%s"}\n' "$stage" "$status" "$message"
}

emit_status "startup" "in_progress" "initializing container"

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  emit_status "startup" "failed" "missing OPENROUTER_API_KEY"
  echo "OPENROUTER_API_KEY is required" >&2
  exit 1
fi

mkdir -p "$DATA_POLICY_DIR" "/app/data/db"
emit_status "startup" "in_progress" "ensured data directories"

if [ -f "$BOOTSTRAP_POLICY_DIR/registry.json" ] && [ ! -f "$DATA_POLICY_DIR/registry.json" ]; then
  cp -R "$BOOTSTRAP_POLICY_DIR/." "$DATA_POLICY_DIR/"
  emit_status "startup" "in_progress" "seeded bootstrap policy registry"
fi

emit_status "startup" "success" "starting reinforce_spec server"
exec python -m reinforce_spec.server "$@"