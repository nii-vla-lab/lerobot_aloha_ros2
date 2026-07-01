# **LeRobot ALOHA Package**

LeRobot plugin packages for ALOHA / ALOHA Stationary robots.

This repository provides independently installable packages that follow the [LeRobot](https://github.com/huggingface/lerobot) plugin conventions.  
Once installed, `lerobot-teleoperate`, `lerobot-record`, and `lerobot-demo` will automatically discover these packages — no changes to the LeRobot source code required.

## Prerequisites

- Python 3.10+
- ROS2 Humble
- [LeRobot](https://github.com/huggingface/lerobot) installed in your environment
- [Interbotix ROS2 Toolboxes](https://github.com/Interbotix/interbotix_ros_toolboxes)
- [ALOHA](https://github.com/tonyzhaozh/aloha) (`aloha.robot_utils`)

## Installation

### 1. ROS2 Humble

Follow the [official ROS2 Humble installation guide](https://docs.ros.org/en/humble/Installation.html) for your platform, then source the setup file:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2. Interbotix XSArm

Clone the ALOHA ROS2 workspace and run the Interbotix installer:

```bash
mkdir -p ~/interbotix_ws/src
cd ~/interbotix_ws/src
git clone <ALOHA_ROS2_REPO_URL>

# Run the Interbotix XSArm installer (ROS2 Humble, AMD64)
cd ~
chmod +x interbotix_ws/src/aloha/xsarm_amd64_install.sh
./interbotix_ws/src/aloha/xsarm_amd64_install.sh -d humble -n
```

Build the workspace:

```bash
cd ~/interbotix_ws
colcon build --symlink-install --cmake-args -DPYTHON_EXECUTABLE=/usr/bin/python3.10
source ~/interbotix_ws/install/setup.bash
```

### 3. LeRobot

```bash
git clone https://github.com/huggingface/lerobot.git && cd lerobot

uv venv --python python3.10
source .venv/bin/activate

uv pip install -e .
uv pip install -e ".[intelrealsense]"
uv pip install -e ".[viz]"
uv pip install -e ".[dataset]"
uv pip install transforms3d
uv pip install modern_robotics
uv pip install pyserial
uv pip install pynput
uv pip install "numpy<2"
```

### 4. lerobot_aloha

With the LeRobot virtual environment active, install all plugin packages at once:

```bash
cd lerobot_aloha
uv sync
```

Or install individual packages:

```bash
uv pip install -e lerobot_robot_aloha
uv pip install -e lerobot_robot_aloha_stationary
uv pip install -e lerobot_teleoperator_aloha_leader
uv pip install -e lerobot_teleoperator_aloha_stationary_leader
```

## Usage

Example config files are provided in the [`configs/`](configs/) directory.  
Copy one and fill in your RealSense serial numbers before use.

```
configs/
├── aloha.yaml             # ALOHA single arm (teleoperate / record)
├── aloha_stationary.yaml  # ALOHA Stationary dual arm (teleoperate / record)
└── demo.yaml              # ALOHA Stationary inference
```

> Find your RealSense serial numbers with:
> ```bash
> rs-enumerate-devices | grep Serial
> ```

### Calibration

ALOHA and ALOHA Stationary do **not** require LeRobot calibration files. Joint calibration is managed entirely by Interbotix ROS2 and the ALOHA launch configuration. The `calibration_dir` field in the config is not needed and can be left unset.

### Step 1 — ROS2 Launch

**Required before teleoperation, data recording, and inference.**  
Run the following in a dedicated terminal. Keep it running throughout the session.

```bash
ros2 launch aloha aloha_bringup.launch.py robot:=aloha_stationary
```

For single-arm ALOHA:

```bash
ros2 launch aloha aloha_bringup.launch.py robot:=aloha
```

### Step 2 — Teleoperation

Open a new terminal with the LeRobot virtual environment active.

```bash
# ALOHA Stationary (dual arm)
lerobot-teleoperate \
    --config_path configs/aloha_stationary.yaml \
    --teleop.type=aloha_stationary_leader

# ALOHA (single arm)
lerobot-teleoperate \
    --config_path configs/aloha.yaml \
    --teleop.type=aloha_leader
```

### Step 2 — Data Recording

Open a new terminal with the LeRobot virtual environment active.

```bash
lerobot-record \
    --config_path configs/aloha_stationary.yaml \
    --teleop.type=aloha_stationary_leader \
    --dataset.repo_id=<HF_USER>/<DATASET_NAME> \
    --dataset.num_episodes=10 \
    --dataset.single_task="<TASK_DESCRIPTION>" \
    --dataset.root=$HOME/.cache/<HF_USER>/<DATASET_NAME> \
    --dataset.push_to_hub=false \
    --dataset.episode_time_s=120 \
    --dataset.reset_time_s=5 \
    --dataset.fps=30
```

> Episode control (→ next episode, ← re-record, Esc stop) needs `pynput` **and** a real
> display (`DISPLAY` set / an X or Wayland-with-XWayland session). If `pynput` is missing
> or no display is available, LeRobot silently falls back to headless mode and the
> keyboard shortcuts stop responding — check the venv with
> `python -c "import pynput"` and run recording from a local graphical session, not a
> bare SSH/tty session, if key presses aren't registering.

### Step 2 — Inference

Open a new terminal with the LeRobot virtual environment active.

```bash
lerobot-demo \
    --config_path configs/demo.yaml \
    --policy.path=<POLICY_CHECKPOINT_PATH>
```

## License

Apache License 2.0
