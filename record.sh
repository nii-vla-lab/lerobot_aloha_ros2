#!/bin/bash
# ── CONFIG ───────────────────────────────────────────────────────────────────
ROBOT_TYPE="aloha_stationary"          # aloha or aloha_stationary
TELEOP_TYPE="aloha_stationary_leader"
HF_USER="lerobot"
REPO_ID="aloha_insertcube"             # e.g. aloha_foldtowel
INSTRUCTION="InsertCube."              # e.g. "Fold the towel."
NUM_EPISODES=10
EPISODE_TIME_S=120
RESET_TIME_S=5
FPS=30
DISPLAY_DATA=false
NUM_IMAGE_WRITER_PROCESSES=2
NUM_IMAGE_WRITER_THREADS_PER_CAMERA=4
REMOVE=true
# ─────────────────────────────────────────────────────────────────────────────

HOST=$(hostname)
echo "$HOST"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${SCRIPT_DIR}/.local/configs/${ROBOT_TYPE}.yaml"
SAVE_DIR="${HOME}/.cache/huggingface/${HF_USER}/${REPO_ID}/999"

if [ "$REMOVE" = true ]; then
    echo "Removing existing dataset directory: ${SAVE_DIR}"
    rm -rf "${SAVE_DIR}"
fi

python "${SCRIPT_DIR}/scripts/record.py" \
    --config_path="${CONFIG_PATH}" \
    --teleop_type="${TELEOP_TYPE}" \
    --repo_id="${HF_USER}/${REPO_ID}" \
    --instruction="${INSTRUCTION}" \
    --save_dir="${SAVE_DIR}" \
    --num_episodes=${NUM_EPISODES} \
    --episode_time_s=${EPISODE_TIME_S} \
    --reset_time_s=${RESET_TIME_S} \
    --fps=${FPS} \
    --num_image_writer_processes=${NUM_IMAGE_WRITER_PROCESSES} \
    --num_image_writer_threads_per_camera=${NUM_IMAGE_WRITER_THREADS_PER_CAMERA} \
    $([ "$DISPLAY_DATA" = true ] && echo "--display_data") \
    --no_remove
