#!/bin/sh
set -eu

BOOTSTRAP_POLICY_DIR="/app/bootstrap/policies"
DATA_POLICY_DIR="/app/data/policies"

mkdir -p "$DATA_POLICY_DIR" "/app/data/db"

if [ -f "$BOOTSTRAP_POLICY_DIR/registry.json" ] && [ ! -f "$DATA_POLICY_DIR/registry.json" ]; then
  cp -R "$BOOTSTRAP_POLICY_DIR/." "$DATA_POLICY_DIR/"
fi

exec python -m reinforce_spec.server "$@"