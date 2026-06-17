# **LeRobot ALOHA Package**

LeRobot plugin packages for ALOHA / ALOHA Stationary robots.

This repository provides independently installable packages that follow the [LeRobot](https://github.com/huggingface/lerobot) plugin conventions.  
Once installed, `lerobot-teleoperate`, `lerobot-record`, and `lerobot-demo` will automatically discover these packages — no changes to the LeRobot source code required.

## Packages

| Package | Type | Robot | `type` name |
|---|---|---|---|
| `lerobot_robot_aloha` | Robot (follower) | ALOHA single arm | `aloha` |
| `lerobot_robot_aloha_stationary` | Robot (follower) | ALOHA Stationary dual arm | `aloha_stationary` |
| `lerobot_teleoperator_aloha_leader` | Teleoperator (leader) | ALOHA leader arm | `aloha_leader` |
| `lerobot_teleoperator_aloha_stationary_leader` | Teleoperator (leader) | ALOHA Stationary leader arm | `aloha_stationary_leader` |

## Prerequisites

- Python 3.10+
- [LeRobot](https://github.com/huggingface/lerobot) installed in your environment
- [Interbotix ROS2 Toolboxes](https://github.com/Interbotix/interbotix_ros_toolboxes) (ROS2 Humble)
- [ALOHA](https://github.com/tonyzhaozh/aloha) (`aloha.robot_utils`)

> `interbotix` and `aloha` are only available in a ROS2 environment. Follow each project's installation guide before proceeding.

## Installation

Install all packages at once using [uv](https://github.com/astral-sh/uv):

```bash
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

Make sure the ROS2 bringup for your ALOHA robot is running before executing any command below.

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

### Teleoperation

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

### Data Recording

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

### Inference

```bash
lerobot-demo \
    --config_path configs/demo.yaml \
    --policy.path=<POLICY_CHECKPOINT_PATH>
```

## Repository Structure

```
lerobot_aloha/
├── pyproject.toml                          # uv workspace root (meta-package)
├── lerobot_robot_aloha/
│   ├── pyproject.toml
│   └── src/lerobot_robot_aloha/
│       ├── __init__.py
│       ├── config_aloha.py
│       └── aloha.py
├── lerobot_robot_aloha_stationary/
│   ├── pyproject.toml
│   └── src/lerobot_robot_aloha_stationary/
│       ├── __init__.py
│       ├── config_aloha_stationary.py
│       └── aloha_stationary.py
├── lerobot_teleoperator_aloha_leader/
│   ├── pyproject.toml
│   └── src/lerobot_teleoperator_aloha_leader/
│       ├── __init__.py
│       ├── config_aloha_leader.py
│       └── aloha_leader.py
└── lerobot_teleoperator_aloha_stationary_leader/
    ├── pyproject.toml
    └── src/lerobot_teleoperator_aloha_stationary_leader/
        ├── __init__.py
        ├── config_aloha_stationary_leader.py
        └── aloha_stationary_leader.py
```

## License

Apache License 2.0
