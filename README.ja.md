# **LeRobot ALOHA Package**

[English](README.md) | [日本語](README.ja.md)

ALOHA / ALOHA Stationary ロボット向けの LeRobot プラグインパッケージです。

このリポジトリは、[LeRobot](https://github.com/huggingface/lerobot) のプラグイン規約に従った、個別にインストール可能なパッケージを提供します。  
インストール後は、LeRobot のソースコードを変更しなくても、`lerobot-teleoperate`、`lerobot-record`、`lerobot-demo` がこれらのパッケージを自動的に検出します。

## 前提条件

- Python 3.10+
- ROS2 Humble
- お使いの環境に [LeRobot](https://github.com/huggingface/lerobot) がインストールされていること
- [Interbotix ROS2 Toolboxes](https://github.com/Interbotix/interbotix_ros_toolboxes)
- [ALOHA](https://github.com/tonyzhaozh/aloha) (`aloha.robot_utils`)

## インストール

### 1. ROS2 Humble

利用するプラットフォームに合わせて [ROS2 Humble の公式インストールガイド](https://docs.ros.org/en/humble/Installation.html) に従い、その後セットアップファイルを読み込みます。

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2. Interbotix XSArm

ALOHA ROS2 ワークスペースをクローンし、Interbotix インストーラーを実行します。

```bash
mkdir -p ~/interbotix_ws/src
cd ~/interbotix_ws/src
git clone git@github.com:nii-vla-lab/aloha_ros2_package.git

# Interbotix XSArm インストーラーを実行 (ROS2 Humble, AMD64)
cd ~
chmod +x interbotix_ws/src/aloha/xsarm_amd64_install.sh
./interbotix_ws/src/aloha/xsarm_amd64_install.sh -d humble -n
```

ワークスペースをビルドします。

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

LeRobot の仮想環境を有効にした状態で、すべてのプラグインパッケージをまとめてインストールします。

```bash
cd lerobot_aloha
uv sync
```

または、個別のパッケージをインストールします。

```bash
uv pip install -e lerobot_robot_aloha
uv pip install -e lerobot_robot_aloha_stationary
uv pip install -e lerobot_teleoperator_aloha_leader
uv pip install -e lerobot_teleoperator_aloha_stationary_leader
```

## 使い方

設定ファイルの例は [`configs/`](configs/) ディレクトリにあります。  
使用前にいずれかをコピーし、RealSense のシリアル番号を入力してください。

```text
configs/
├── aloha.yaml             # ALOHA single arm (teleoperate / record)
├── aloha_stationary.yaml  # ALOHA Stationary dual arm (teleoperate / record)
└── demo.yaml              # ALOHA Stationary inference
```

> RealSense のシリアル番号は次のコマンドで確認できます。
> ```bash
> rs-enumerate-devices | grep Serial
> ```

### キャリブレーション

ALOHA および ALOHA Stationary では、LeRobot のキャリブレーションファイルは不要です。関節キャリブレーションは、Interbotix ROS2 と ALOHA の launch 設定によって完全に管理されます。config の `calibration_dir` フィールドは不要で、未設定のままで構いません。

### Step 1 - ROS2 Launch

**テレオペレーション、データ記録、推論の前に必ず実行してください。**  
専用のターミナルで次のコマンドを実行し、セッション中は起動したままにします。

```bash
ros2 launch aloha aloha_bringup.launch.py robot:=aloha_stationary
```

単腕 ALOHA の場合:

```bash
ros2 launch aloha aloha_bringup.launch.py robot:=aloha
```

### Step 2 - テレオペレーション

LeRobot の仮想環境を有効にした新しいターミナルを開きます。

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

### Step 2 - データ記録

LeRobot の仮想環境を有効にした新しいターミナルを開きます。

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

> エピソード制御 (→ 次のエピソード、← 再記録、Esc 停止) には `pynput` **および** 実際の
> ディスプレイ (`DISPLAY` が設定された X または Wayland-with-XWayland セッション) が必要です。
> `pynput` がない場合やディスプレイが利用できない場合、LeRobot は静かに headless mode にフォールバックし、
> キーボードショートカットが反応しなくなります。キー入力が登録されない場合は、
> `python -c "import pynput"` で venv を確認し、bare SSH/tty セッションではなくローカルのグラフィカルセッションから記録を実行してください。

### Step 2 - 推論

LeRobot の仮想環境を有効にした新しいターミナルを開きます。

```bash
lerobot-demo \
    --config_path configs/demo.yaml \
    --policy.path=<POLICY_CHECKPOINT_PATH>
```

## ライセンス

Apache License 2.0
