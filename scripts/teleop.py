#!/usr/bin/env python3
"""ALOHA teleoperation — invokes the LeRobot teleoperation pipeline in-process.

Edit the CONFIG section at the top, then run:

    cd ~/lerobot_aloha
    python scripts/teleop.py

CLI overrides are also available:

    python scripts/teleop.py --robot_type aloha --display_data
"""

import argparse
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
ROBOT_TYPE   = "aloha_stationary"   # "aloha" or "aloha_stationary"
DISPLAY_DATA = False
FPS          = 60
# ────────────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Teleoperate ALOHA with LeRobot")
    p.add_argument("--robot_type", default=ROBOT_TYPE,
                   choices=["aloha", "aloha_stationary"])
    p.add_argument("--display_data", action="store_true", default=DISPLAY_DATA)
    p.add_argument("--fps", type=int, default=FPS)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    robot_type  = args.robot_type
    config_path = _REPO_ROOT / ".local/configs" / f"{robot_type}.yaml"
    teleop_type = (
        "aloha_stationary_leader" if robot_type == "aloha_stationary" else "aloha_leader"
    )

    print("Starting teleoperation with LeRobot...")

    lerobot_args = [
        f"--teleop.type={teleop_type}",
        f"--display_data={str(args.display_data).lower()}",
        f"--fps={args.fps}",
    ]

    # lerobot を --help が来た時に import せず、ここで遅延 import する
    import draccus
    from lerobot.scripts.lerobot_teleoperate import TeleoperateConfig, teleoperate
    from lerobot.utils.import_utils import register_third_party_plugins

    register_third_party_plugins()

    # YAML + lerobot_args から TeleoperateConfig を構築（sys.argv 不使用）
    cfg: TeleoperateConfig = draccus.parse(
        config_class=TeleoperateConfig,
        config_path=str(config_path),
        args=lerobot_args,
    )

    # @parser.wrap() は第1引数が TeleoperateConfig 型なら CLI パースをスキップする
    # (lerobot/configs/parser.py L289-291)
    teleoperate(cfg)


if __name__ == "__main__":
    main()
