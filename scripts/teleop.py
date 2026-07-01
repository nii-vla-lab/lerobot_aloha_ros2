#!/usr/bin/env python3
"""ALOHA teleoperation script.

lerobot_teleoperate.py をベースに ALOHA 用にカスタマイズ。
設定はすべて teleop.sh に記述し、このスクリプトは引数として受け取る。

Usage (teleop.sh から呼ばれる):
    python scripts/teleop.py \\
        --config_path=.local/configs/aloha_stationary.yaml \\
        --teleop_type=aloha_stationary_leader
"""

import argparse
import logging
import time
from dataclasses import asdict, dataclass
from pprint import pformat

# ---------------------------------------------------------------------------
# lerobot imports
# ---------------------------------------------------------------------------
from lerobot.cameras.realsense import RealSenseCameraConfig  # noqa: F401 (registers CameraConfig "intelrealsense" choice for draccus)
from lerobot.processor import RobotProcessorPipeline, make_default_processors
from lerobot.robots import Robot, RobotConfig, make_robot_from_config
from lerobot.teleoperators import Teleoperator, TeleoperatorConfig, make_teleoperator_from_config
from lerobot.utils.import_utils import register_third_party_plugins
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import init_logging, move_cursor_up
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data, shutdown_rerun


# ---------------------------------------------------------------------------
# TeleoperateConfig  (lerobot_teleoperate.py と同一)
# ---------------------------------------------------------------------------
@dataclass
class TeleoperateConfig:
    teleop: TeleoperatorConfig
    robot: RobotConfig
    fps: int = 60
    teleop_time_s: float = None
    display_data: bool = False
    display_ip: str = None
    display_port: int = None
    display_compressed_images: bool = False


# ---------------------------------------------------------------------------
# teleop_loop  (lerobot_teleoperate.py から変更なし)
# ---------------------------------------------------------------------------
def teleop_loop(
    teleop: Teleoperator,
    robot: Robot,
    fps: int,
    teleop_action_processor: RobotProcessorPipeline,
    robot_action_processor: RobotProcessorPipeline,
    robot_observation_processor: RobotProcessorPipeline,
    display_data: bool = False,
    duration: float = None,
    display_compressed_images: bool = False,
):
    display_len = max(len(key) for key in robot.action_features)
    start = time.perf_counter()

    while True:
        loop_start = time.perf_counter()

        obs = robot.get_observation()
        raw_action = teleop.get_action()
        teleop_action = teleop_action_processor((raw_action, obs))
        robot_action_to_send = robot_action_processor((teleop_action, obs))
        robot.send_action(robot_action_to_send)

        if display_data:
            obs_transition = robot_observation_processor(obs)
            log_rerun_data(
                observation=obs_transition,
                action=teleop_action,
                compress_images=display_compressed_images,
            )
            print("\n" + "-" * (display_len + 10))
            print(f"{'NAME':<{display_len}} | {'NORM':>7}")
            for motor, value in robot_action_to_send.items():
                print(f"{motor:<{display_len}} | {value:>7.2f}")
            move_cursor_up(len(robot_action_to_send) + 3)

        dt_s = time.perf_counter() - loop_start
        precise_sleep(max(1 / fps - dt_s, 0.0))
        loop_s = time.perf_counter() - loop_start
        print(f"Teleop loop time: {loop_s * 1e3:.2f}ms ({1 / loop_s:.0f} Hz)")
        move_cursor_up(1)

        if duration is not None and time.perf_counter() - start >= duration:
            return


# ---------------------------------------------------------------------------
# teleoperate  (lerobot_teleoperate.py から @parser.wrap() を除去して移植)
# ---------------------------------------------------------------------------
def teleoperate(cfg: TeleoperateConfig) -> None:
    init_logging()
    logging.info(pformat(asdict(cfg)))

    if cfg.display_data:
        init_rerun(session_name="teleoperation", ip=cfg.display_ip, port=cfg.display_port)

    display_compressed_images = (
        True
        if (cfg.display_data and cfg.display_ip is not None and cfg.display_port is not None)
        else cfg.display_compressed_images
    )

    teleop = make_teleoperator_from_config(cfg.teleop)
    robot = make_robot_from_config(cfg.robot)
    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    # follower を先に connect して start pose へ移動させてから leader を connect する
    robot.connect()
    teleop.connect()

    try:
        teleop_loop(
            teleop=teleop,
            robot=robot,
            fps=cfg.fps,
            display_data=cfg.display_data,
            duration=cfg.teleop_time_s,
            teleop_action_processor=teleop_action_processor,
            robot_action_processor=robot_action_processor,
            robot_observation_processor=robot_observation_processor,
            display_compressed_images=display_compressed_images,
        )
    except KeyboardInterrupt:
        pass
    finally:
        if cfg.display_data:
            shutdown_rerun()
        teleop.disconnect()
        robot.disconnect()


# ---------------------------------------------------------------------------
# main — teleop.sh から渡された引数で config を組み立て teleoperate() を呼ぶ
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config_path", required=True,
                   help="ロボット設定 YAML (.local/configs/aloha_stationary.yaml 等)")
    p.add_argument("--teleop_type", required=True,
                   help="teleop タイプ (例: aloha_stationary_leader)")
    p.add_argument("--fps",          type=int,   default=60)
    p.add_argument("--display_data", action="store_true", default=False)
    args = p.parse_args()

    register_third_party_plugins()

    # YAML からロボット・カメラ config を読み込む（draccus 経由）
    import draccus

    @dataclass
    class _HardwareConfig:
        robot: RobotConfig
        teleop: TeleoperatorConfig = None

    hw = draccus.parse(
        _HardwareConfig,
        config_path=args.config_path,
        args=[f"--teleop.type={args.teleop_type}"],
    )

    cfg = TeleoperateConfig(
        robot=hw.robot,
        teleop=hw.teleop,
        fps=args.fps,
        display_data=args.display_data,
    )

    teleoperate(cfg)


if __name__ == "__main__":
    main()
