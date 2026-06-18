#!/bin/bash
# Hugging Face username and dataset configuration
ROBOT_TYPE="aloha_stationary" # aloha or aloha_stationary, so101
HF_USER="lerobot"
# aloha_pickstrawberry
REPO_ID="aloha_insertcube" # "aloha_foldtowel"
NUM_EPISODES="10"
# Pick up a strawberry.
# "TransferCube.", "InsertCube."
INSTRUCTION="InsertCube." # "Fold the towel."
DISPLAY_DATA=false
# Path to the robot configuration file (YAML)
HOST=$(hostname)
echo "$HOST" # "liat400" or "liat401"
CONFIG_PATH=.local/configs/$ROBOT_TYPE.yaml

# Directory where the recorded dataset will be saved
SAVE_DIR="$HOME/.cache/huggingface/$HF_USER/$REPO_ID/999"

# Whether to remove any existing data before starting
REMOVE=true
if [ "$REMOVE" = true ]; then
    echo "Removing existing dataset directory: ${SAVE_DIR}"
    rm -rf "${SAVE_DIR}"
fi

echo "Starting data recording with LeRobot..."

# Start teleoperating robot episodes using the control script
lerobot-record \
    --config_path=${CONFIG_PATH} \
    --teleop.type=aloha_stationary_leader \
    --dataset.repo_id=${HF_USER}/${REPO_ID} \
    --dataset.num_episodes=${NUM_EPISODES} \
    --dataset.single_task="${INSTRUCTION}" \
    --dataset.root=${SAVE_DIR} \
    --dataset.push_to_hub=false \
    --dataset.private=true \
    --dataset.episode_time_s=120 \
    --dataset.reset_time_s=5 \
    --dataset.fps=30 \
    --dataset.num_image_writer_processes=2 \
    --dataset.num_image_writer_threads_per_camera=4 \
    --display_data=${DISPLAY_DATA}

echo "LeRobot data recording completed."
echo "Saved dataset directory: ${SAVE_DIR}"