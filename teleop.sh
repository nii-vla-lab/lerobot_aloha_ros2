#!/bin/bash
ROBOT_TYPE="aloha_stationary" # aloha or aloha_stationary, so101
DISPLAY_DATA=false
CONFIG_PATH=.local/configs/$ROBOT_TYPE.yaml

# Start teleoperating robot episodes using the control script
lerobot-teleoperate \
    --config_path=${CONFIG_PATH} \
    --teleop.type=aloha_stationary_leader \
    --display_data=${DISPLAY_DATA}