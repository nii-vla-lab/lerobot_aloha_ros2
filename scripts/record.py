#!/usr/bin/env python3
"""ALOHA dataset recording — invokes the LeRobot recording pipeline in-process.

Edit the CONFIG section at the top, then run:

    cd ~/lerobot_aloha
    python scripts/record.py

CLI overrides are also available:

    python scripts/record.py --repo_id aloha_pickstrawberry --num_episodes 20
    python scripts/record.py --no_remove
"""

import argparse
import shutil
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
ROBOT_TYPE     = "aloha_stationary"        # "aloha" or "aloha_stationary"
HF_USER        = "lerobot"
REPO_ID        = "aloha_insertcube"        # e.g. "aloha_foldtowel"
INSTRUCTION    = "InsertCube."             # e.g. "Fold the towel."
NUM_EPISODES   = 10
EPISODE_TIME_S = 120
RESET_TIME_S   = 5
FPS            = 30
DISPLAY_DATA   = False
PUSH_TO_HUB    = False
PRIVATE        = True
NUM_IMAGE_WRITER_PROCESSES          = 2
NUM_IMAGE_WRITER_THREADS_PER_CAMERA = 4
REMOVE_EXISTING = True
# ────────────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record ALOHA dataset with LeRobot")
    p.add_argument("--robot_type", default=ROBOT_TYPE,
                   choices=["aloha", "aloha_stationary"])
    p.add_argument("--hf_user", default=HF_USER)
    p.add_argument("--repo_id", default=REPO_ID)
    p.add_argument("--instruction", default=INSTRUCTION)
    p.add_argument("--num_episodes", type=int, default=NUM_EPISODES)
    p.add_argument("--episode_time_s", type=int, default=EPISODE_TIME_S)
    p.add_argument("--reset_time_s", type=int, default=RESET_TIME_S)
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--display_data", action="store_true", default=DISPLAY_DATA)
    p.add_argument("--no_remove", action="store_true",
                   help="Do not remove the existing dataset directory before recording")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    robot_type  = args.robot_type
    repo_id     = f"{args.hf_user}/{args.repo_id}"
    save_dir    = Path.home() / ".cache/huggingface" / args.hf_user / args.repo_id / "999"
    config_path = _REPO_ROOT / ".local/configs" / f"{robot_type}.yaml"
    teleop_type = (
        "aloha_stationary_leader" if robot_type == "aloha_stationary" else "aloha_leader"
    )

    if not args.no_remove and save_dir.exists():
        print(f"Removing existing dataset directory: {save_dir}")
        shutil.rmtree(save_dir)

    print("Starting data recording with LeRobot...")
    print(f"  repo:     {repo_id}")
    print(f"  save_dir: {save_dir}")
    print(f"  episodes: {args.num_episodes}  |  task: {args.instruction}")

    # lerobot-record CLI 相当の引数リスト。draccus.parse() に直接渡し sys.argv を汚さない。
    lerobot_args = [
        f"--teleop.type={teleop_type}",
        f"--dataset.repo_id={repo_id}",
        f"--dataset.num_episodes={args.num_episodes}",
        f"--dataset.single_task={args.instruction}",
        f"--dataset.root={save_dir}",
        f"--dataset.push_to_hub={str(PUSH_TO_HUB).lower()}",
        f"--dataset.private={str(PRIVATE).lower()}",
        f"--dataset.episode_time_s={args.episode_time_s}",
        f"--dataset.reset_time_s={args.reset_time_s}",
        f"--dataset.fps={args.fps}",
        f"--dataset.num_image_writer_processes={NUM_IMAGE_WRITER_PROCESSES}",
        f"--dataset.num_image_writer_threads_per_camera={NUM_IMAGE_WRITER_THREADS_PER_CAMERA}",
        f"--display_data={str(args.display_data).lower()}",
    ]

    # lerobot を --help が来た時に import せず、ここで遅延 import する
    import draccus
    from lerobot.scripts.lerobot_record import RecordConfig, record
    from lerobot.utils.import_utils import register_third_party_plugins

    register_third_party_plugins()

    # YAML + lerobot_args から RecordConfig を構築（sys.argv 不使用）
    cfg: RecordConfig = draccus.parse(
        config_class=RecordConfig,
        config_path=str(config_path),
        args=lerobot_args,
    )

    # @parser.wrap() は第1引数が RecordConfig 型なら CLI パースをスキップする
    # (lerobot/configs/parser.py L289-291)
    record(cfg)

    print("LeRobot data recording completed.")
    print(f"Saved dataset directory: {save_dir}")


if __name__ == "__main__":
    main()
