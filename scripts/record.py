#!/usr/bin/env python3
"""ALOHA dataset recording script.

lerobot_record.py をベースに ALOHA 用にカスタマイズ。
設定はすべて record.sh に記述し、このスクリプトは引数として受け取る。

Usage (record.sh から呼ばれる):
    python scripts/record.py \\
        --config_path=.local/configs/aloha_stationary.yaml \\
        --repo_id=lerobot/aloha_insertcube \\
        --instruction="InsertCube." \\
        --num_episodes=10 \\
        --save_dir=/path/to/save
"""

import argparse
import logging
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from pprint import pformat

# ---------------------------------------------------------------------------
# lerobot imports
# ---------------------------------------------------------------------------
from lerobot.cameras.realsense import RealSenseCameraConfig  # noqa: F401 (registers CameraConfig "intelrealsense" choice for draccus)
from lerobot.common.control_utils import init_keyboard_listener, is_headless
from lerobot.configs.dataset import DatasetRecordConfig
from lerobot.datasets import (
    LeRobotDataset,
    VideoEncodingManager,
    aggregate_pipeline_dataset_features,
    create_initial_features,
    safe_stop_image_writer,
)
from lerobot.processor import RobotProcessorPipeline, make_default_processors
from lerobot.robots import Robot, RobotConfig, make_robot_from_config
from lerobot.teleoperators import Teleoperator, TeleoperatorConfig, make_teleoperator_from_config
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts
from lerobot.utils.import_utils import register_third_party_plugins
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import init_logging, log_say
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data


# ---------------------------------------------------------------------------
# RecordConfig  (lerobot_record.py と同一)
# ---------------------------------------------------------------------------
@dataclass
class RecordConfig:
    robot: RobotConfig
    dataset: DatasetRecordConfig
    teleop: TeleoperatorConfig = None
    display_data: bool = False
    display_ip: str = None
    display_port: int = None
    display_compressed_images: bool = False
    play_sounds: bool = True
    resume: bool = False

    def __post_init__(self):
        if self.teleop is None:
            raise ValueError("A teleoperator is required for recording.")


# ---------------------------------------------------------------------------
# record_loop  (lerobot_record.py から変更なし)
# ---------------------------------------------------------------------------
@safe_stop_image_writer
def record_loop(
    robot: Robot,
    events: dict,
    fps: int,
    teleop_action_processor: RobotProcessorPipeline,
    robot_action_processor: RobotProcessorPipeline,
    robot_observation_processor: RobotProcessorPipeline,
    dataset: LeRobotDataset = None,
    teleop: Teleoperator = None,
    control_time_s: int = None,
    single_task: str = None,
    display_data: bool = False,
    display_compressed_images: bool = False,
):
    if dataset is not None and dataset.fps != fps:
        raise ValueError(f"Dataset fps mismatch: {dataset.fps} != {fps}")

    control_interval = 1 / fps
    no_action_count = 0
    timestamp = 0
    start_episode_t = time.perf_counter()

    while timestamp < control_time_s:
        start_loop_t = time.perf_counter()

        if events["exit_early"]:
            events["exit_early"] = False
            break

        obs = robot.get_observation()
        obs_processed = robot_observation_processor(obs)

        if dataset is not None:
            observation_frame = build_dataset_frame(dataset.features, obs_processed, prefix=OBS_STR)

        if isinstance(teleop, Teleoperator):
            act = teleop.get_action()
            act_processed_teleop = teleop_action_processor((act, obs))
            action_values = act_processed_teleop
            robot_action_to_send = robot_action_processor((act_processed_teleop, obs))
        else:
            no_action_count += 1
            if no_action_count == 1 or no_action_count % 10 == 0:
                logging.warning("No teleoperator provided, skipping action generation.")
            continue

        robot.send_action(robot_action_to_send)

        if dataset is not None:
            action_frame = build_dataset_frame(dataset.features, action_values, prefix=ACTION)
            frame = {**observation_frame, **action_frame, "task": single_task}
            dataset.add_frame(frame)

        if display_data:
            log_rerun_data(
                observation=obs_processed,
                action=action_values,
                compress_images=display_compressed_images,
            )

        dt_s = time.perf_counter() - start_loop_t
        sleep_time_s = control_interval - dt_s
        if sleep_time_s < 0:
            logging.warning(
                f"Record loop running slower ({1/dt_s:.1f} Hz) than target FPS ({fps} Hz)."
            )
        precise_sleep(max(sleep_time_s, 0.0))
        timestamp = time.perf_counter() - start_episode_t


# ---------------------------------------------------------------------------
# record  (lerobot_record.py から @parser.wrap() を除去して移植)
# ---------------------------------------------------------------------------
def record(cfg: RecordConfig) -> LeRobotDataset:
    init_logging()
    logging.info(pformat(asdict(cfg)))

    if cfg.display_data:
        init_rerun(session_name="recording", ip=cfg.display_ip, port=cfg.display_port)

    display_compressed_images = (
        True
        if (cfg.display_data and cfg.display_ip is not None and cfg.display_port is not None)
        else cfg.display_compressed_images
    )

    robot = make_robot_from_config(cfg.robot)
    teleop = make_teleoperator_from_config(cfg.teleop)
    _t, _r, _o = make_default_processors()

    dataset_features = combine_feature_dicts(
        aggregate_pipeline_dataset_features(
            pipeline=_t,
            initial_features=create_initial_features(action=robot.action_features),
            use_videos=cfg.dataset.video,
        ),
        aggregate_pipeline_dataset_features(
            pipeline=_o,
            initial_features=create_initial_features(observation=robot.observation_features),
            use_videos=cfg.dataset.video,
        ),
    )

    dataset = None
    listener = None

    try:
        repo_name = cfg.dataset.repo_id.split("/", 1)[-1]
        if repo_name.startswith("eval_"):
            raise ValueError("Dataset names starting with 'eval_' are reserved for policy evaluation.")

        cfg.dataset.stamp_repo_id()
        dataset = LeRobotDataset.create(
            cfg.dataset.repo_id,
            cfg.dataset.fps,
            root=cfg.dataset.root,
            robot_type=robot.name,
            features=dataset_features,
            use_videos=cfg.dataset.video,
            image_writer_processes=cfg.dataset.num_image_writer_processes,
            image_writer_threads=cfg.dataset.num_image_writer_threads_per_camera * len(robot.cameras),
            batch_encoding_size=cfg.dataset.video_encoding_batch_size,
            camera_encoder=cfg.dataset.camera_encoder,
            encoder_threads=cfg.dataset.encoder_threads,
            streaming_encoding=cfg.dataset.streaming_encoding,
            encoder_queue_maxsize=cfg.dataset.encoder_queue_maxsize,
        )

        robot.connect()
        teleop.connect()

        listener, events = init_keyboard_listener()

        with VideoEncodingManager(dataset):
            recorded_episodes = 0
            while recorded_episodes < cfg.dataset.num_episodes and not events["stop_recording"]:
                # robot.connect()/teleop.connect() already moved both arms to their
                # start pose, so re-resetting before the first episode would just
                # repeat that same move back-to-back.
                if recorded_episodes > 0:
                    if hasattr(robot, "reset"):
                        robot.reset()
                    if teleop is not None and hasattr(teleop, "reset"):
                        teleop.reset()

                log_say(f"Recording episode {dataset.num_episodes}", cfg.play_sounds)
                record_loop(
                    robot=robot,
                    events=events,
                    fps=cfg.dataset.fps,
                    teleop_action_processor=_t,
                    robot_action_processor=_r,
                    robot_observation_processor=_o,
                    teleop=teleop,
                    dataset=dataset,
                    control_time_s=cfg.dataset.episode_time_s,
                    single_task=cfg.dataset.single_task,
                    display_data=cfg.display_data,
                    display_compressed_images=display_compressed_images,
                )

                if not events["stop_recording"] and (
                    (recorded_episodes < cfg.dataset.num_episodes - 1) or events["rerecord_episode"]
                ):
                    log_say("Reset the environment", cfg.play_sounds)
                    record_loop(
                        robot=robot,
                        events=events,
                        fps=cfg.dataset.fps,
                        teleop_action_processor=_t,
                        robot_action_processor=_r,
                        robot_observation_processor=_o,
                        teleop=teleop,
                        control_time_s=cfg.dataset.reset_time_s,
                        single_task=cfg.dataset.single_task,
                        display_data=cfg.display_data,
                    )

                if events["rerecord_episode"]:
                    log_say("Re-record episode", cfg.play_sounds)
                    events["rerecord_episode"] = False
                    events["exit_early"] = False
                    dataset.clear_episode_buffer()
                    continue

                # Esc sets both stop_recording and exit_early, so it can break
                # record_loop before any frame was captured (e.g. pressed right at
                # the start of an episode). save_episode() requires >=1 frame.
                if dataset.episode_buffer["size"] == 0:
                    dataset.clear_episode_buffer()
                    break

                dataset.save_episode()
                recorded_episodes += 1

    finally:
        log_say("Stop recording", cfg.play_sounds, blocking=True)
        if dataset:
            dataset.finalize()
        if robot.is_connected:
            robot.disconnect()
        if teleop and teleop.is_connected:
            teleop.disconnect()
        if not is_headless() and listener:
            listener.stop()
        if cfg.dataset.push_to_hub:
            if dataset and dataset.num_episodes > 0:
                dataset.push_to_hub(tags=cfg.dataset.tags, private=cfg.dataset.private)
            else:
                logging.warning("No episodes saved — skipping push to hub")
        log_say("Exiting", cfg.play_sounds)

    return dataset


# ---------------------------------------------------------------------------
# main — record.sh から渡された引数で config を組み立て record() を呼ぶ
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config_path", required=True,
                   help="ロボット設定 YAML (.local/configs/aloha_stationary.yaml 等)")
    p.add_argument("--teleop_type", required=True,
                   help="teleop タイプ (例: aloha_stationary_leader)")
    p.add_argument("--repo_id", required=True,
                   help="HuggingFace dataset repo_id (例: lerobot/aloha_insertcube)")
    p.add_argument("--instruction", required=True)
    p.add_argument("--save_dir", required=True)
    p.add_argument("--num_episodes",   type=int,   default=10)
    p.add_argument("--episode_time_s", type=int,   default=120)
    p.add_argument("--reset_time_s",   type=int,   default=5)
    p.add_argument("--fps",            type=int,   default=30)
    p.add_argument("--display_data",   action="store_true", default=False)
    p.add_argument("--push_to_hub",    action="store_true", default=False)
    p.add_argument("--no_remove",      action="store_true",
                   help="既存 save_dir を削除しない")
    p.add_argument("--num_image_writer_processes",          type=int, default=2)
    p.add_argument("--num_image_writer_threads_per_camera", type=int, default=4)
    args = p.parse_args()

    save_dir = Path(args.save_dir)
    if not args.no_remove and save_dir.exists():
        print(f"Removing existing dataset directory: {save_dir}")
        shutil.rmtree(save_dir)

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

    dataset_cfg = DatasetRecordConfig(
        repo_id=args.repo_id,
        num_episodes=args.num_episodes,
        single_task=args.instruction,
        root=save_dir,
        push_to_hub=args.push_to_hub,
        private=True,
        episode_time_s=args.episode_time_s,
        reset_time_s=args.reset_time_s,
        fps=args.fps,
        num_image_writer_processes=args.num_image_writer_processes,
        num_image_writer_threads_per_camera=args.num_image_writer_threads_per_camera,
    )

    cfg = RecordConfig(
        robot=hw.robot,
        dataset=dataset_cfg,
        teleop=hw.teleop,
        display_data=args.display_data,
    )

    record(cfg)


if __name__ == "__main__":
    main()
