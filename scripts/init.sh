#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "scripts/init.sh is deprecated; use scripts/onboard.py from the Agent onboarding playbook." >&2
exec python3 "$SCRIPT_DIR/onboard.py" "$@"
