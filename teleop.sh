#!/bin/bash
# ── CONFIG ───────────────────────────────────────────────────────────────────
ROBOT_TYPE="aloha_stationary"          # aloha or aloha_stationary
TELEOP_TYPE="aloha_stationary_leader"
FPS=60
DISPLAY_DATA=false
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${SCRIPT_DIR}/.local/configs/${ROBOT_TYPE}.yaml"

python "${SCRIPT_DIR}/scripts/teleop.py" \
    --config_path="${CONFIG_PATH}" \
    --teleop_type="${TELEOP_TYPE}" \
    --fps=${FPS} \
    $([ "$DISPLAY_DATA" = true ] && echo "--display_data")
