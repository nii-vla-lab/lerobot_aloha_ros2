#!/usr/bin/env python3
"""Re-apply the lerobot core patches required to run the latest lerobot on
Python 3.10 + numpy<2 alongside ROS2 Humble (ALOHA).

lerobot's `sync_upstream.sh` overwrites these files back to their upstream
(Python 3.12 / numpy>=2) form, so run this script after every sync:

    python ~/lerobot_aloha/scripts/patch_lerobot_py310.py

It is idempotent: already-patched files are detected and skipped. The lerobot
checkout location defaults to ~/lerobot and can be overridden:

    python patch_lerobot_py310.py /path/to/lerobot      # positional
    LEROBOT_DIR=/path/to/lerobot python patch_lerobot_py310.py

What it does:
  * PEP 695 back-port (`type X = ...`, `class C[T]`, `def f[T]`) -> 3.10 syntax
  * `Unpack` import: typing -> typing_extensions (added to typing only in 3.11)
  * pyproject.toml: requires-python>=3.10, numpy floor lowered to allow numpy<2
  * lerobot-record: reset robot/teleop to start pose at the top of each episode
  * lerobot-teleoperate: connect robot (follower) before teleop (leader)
"""

import os
import re
import sys

ROOT = os.path.abspath(
    sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LEROBOT_DIR", os.path.expanduser("~/lerobot"))
)
SRC = os.path.join(ROOT, "src")

# (relative path, old upstream snippet, new patched snippet)
REPLACEMENTS = [
    # --- PEP 695: motors_bus.py ---
    (
        "src/lerobot/motors/motors_bus.py",
        "from typing import TYPE_CHECKING, Protocol\n",
        "from typing import TYPE_CHECKING, Protocol, TypeAlias\n",
    ),
    (
        "src/lerobot/motors/motors_bus.py",
        "type NameOrID = str | int\ntype Value = int | float\n",
        "NameOrID: TypeAlias = str | int\nValue: TypeAlias = int | float\n",
    ),
    # --- PEP 695: streaming_dataset.py ---
    (
        "src/lerobot/datasets/streaming_dataset.py",
        "from collections import deque\n"
        "from collections.abc import Callable, Generator, Iterable, Iterator\n"
        "from pathlib import Path\n",
        "from collections import deque\n"
        "from collections.abc import Callable, Generator, Iterable, Iterator\n"
        "from pathlib import Path\n"
        "from typing import Generic, TypeVar\n",
    ),
    (
        "src/lerobot/datasets/streaming_dataset.py",
        "class Backtrackable[T]:\n",
        'T = TypeVar("T")\n\n\nclass Backtrackable(Generic[T]):\n',
    ),
    # --- PEP 695: processor/pipeline.py ---
    (
        "src/lerobot/processor/pipeline.py",
        "from typing import Any, TypedDict, TypeVar, cast\n",
        "from typing import Any, Generic, TypedDict, TypeVar, cast\n",
    ),
    (
        "src/lerobot/processor/pipeline.py",
        "class DataProcessorPipeline[TInput, TOutput](HubMixin):\n",
        "class DataProcessorPipeline(Generic[TInput, TOutput], HubMixin):\n",
    ),
    # --- PEP 695: utils/io_utils.py ---
    (
        "src/lerobot/utils/io_utils.py",
        "from typing import Any\n",
        "from typing import Any, TypeVar\n",
    ),
    (
        "src/lerobot/utils/io_utils.py",
        'JsonLike = str | int | float | bool | None | list["JsonLike"] | dict[str, "JsonLike"] | tuple["JsonLike", ...]\n',
        'JsonLike = str | int | float | bool | None | list["JsonLike"] | dict[str, "JsonLike"] | tuple["JsonLike", ...]\n'
        'T = TypeVar("T", bound=JsonLike)\n',
    ),
    (
        "src/lerobot/utils/io_utils.py",
        "def deserialize_json_into_object[T: JsonLike](fpath: Path, obj: T) -> T:\n",
        "def deserialize_json_into_object(fpath: Path, obj: T) -> T:\n",
    ),
    # --- pyproject.toml: python + numpy ---
    (
        "pyproject.toml",
        'requires-python = ">=3.12"\n',
        'requires-python = ">=3.10"\n',
    ),
    (
        "pyproject.toml",
        '"numpy>=2.0.0,<2.3.0"',
        '"numpy>=1.24.0,<2.3.0"',
    ),
    # --- lerobot-record: reset at episode loop top ---
    (
        "src/lerobot/scripts/lerobot_record.py",
        '            while recorded_episodes < cfg.dataset.num_episodes and not events["stop_recording"]:\n'
        "                log_say(f\"Recording episode {dataset.num_episodes}\", cfg.play_sounds)\n",
        '            while recorded_episodes < cfg.dataset.num_episodes and not events["stop_recording"]:\n'
        "                # Restore the robot to its initial pose and clear any internal state\n"
        '                if hasattr(robot, "reset"):\n'
        "                    robot.reset()\n"
        "                # Reinitialize the teleoperation controller (e.g., clear commands, reset timers)\n"
        '                if teleop is not None and hasattr(teleop, "reset"):\n'
        "                    teleop.reset()\n"
        "\n"
        "                log_say(f\"Recording episode {dataset.num_episodes}\", cfg.play_sounds)\n",
    ),
    # --- pyav_utils: int.is_integer() fix (int has no .is_integer(), only float does) ---
    (
        "src/lerobot/datasets/pyav_utils.py",
        "        if type_name in FFMPEG_INTEGER_OPTION_TYPES and not num_val.is_integer():\n",
        "        if type_name in FFMPEG_INTEGER_OPTION_TYPES and isinstance(num_val, float) and not num_val.is_integer():\n",
    ),
    # --- lerobot-teleoperate: connect follower before leader ---
    (
        "src/lerobot/scripts/lerobot_teleoperate.py",
        "    teleop.connect()\n    robot.connect()\n",
        "    # Connect the robot (follower) before the teleoperator (leader) so the\n"
        "    # follower reaches its start pose first. ALOHA's connect() runs an opening\n"
        "    # ceremony that moves the arm to start_pose; the default leader-first order\n"
        "    # made the leader reset before the follower.\n"
        "    robot.connect()\n    teleop.connect()\n",
    ),
]

# Files whose `from typing import ... Unpack ...` must move to typing_extensions.
UNPACK_FILES = [
    "src/lerobot/policies/pretrained.py",
    "src/lerobot/policies/pi0_fast/modeling_pi0_fast.py",
    "src/lerobot/policies/pi0/modeling_pi0.py",
    "src/lerobot/policies/factory.py",
    "src/lerobot/policies/smolvla/modeling_smolvla.py",
    "src/lerobot/policies/pi05/modeling_pi05.py",
]

UNPACK_IMPORT = "from typing_extensions import Unpack  # py3.10: Unpack added to typing in 3.11\n"

applied = skipped = missing = 0


def patch_replacement(relpath, old, new):
    global applied, skipped, missing
    path = os.path.join(ROOT, relpath)
    if not os.path.isfile(path):
        print(f"  MISSING FILE  {relpath}")
        missing += 1
        return
    text = open(path, encoding="utf-8").read()
    if new in text:
        print(f"  already       {relpath}")
        skipped += 1
    elif old in text:
        open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
        print(f"  PATCHED       {relpath}")
        applied += 1
    else:
        print(f"  !! pattern not found (upstream drift?)  {relpath}")
        missing += 1


def patch_unpack(relpath):
    global applied, skipped, missing
    path = os.path.join(ROOT, relpath)
    if not os.path.isfile(path):
        print(f"  MISSING FILE  {relpath}")
        missing += 1
        return
    lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
    if any("from typing_extensions import Unpack" in ln for ln in lines):
        print(f"  already       {relpath} (Unpack)")
        skipped += 1
        return
    out, done = [], False
    for ln in lines:
        m = re.match(r"^(\s*)from typing import (.+)$", ln)
        if m and not done and re.search(r"\bUnpack\b", ln):
            indent = m.group(1)
            names = [p.strip() for p in m.group(2).split(",") if p.strip() != "Unpack"]
            out.append(f"{indent}from typing import {', '.join(names)}\n")
            out.append(f"{indent}{UNPACK_IMPORT}")
            done = True
        else:
            out.append(ln)
    if done:
        open(path, "w", encoding="utf-8").writelines(out)
        print(f"  PATCHED       {relpath} (Unpack)")
        applied += 1
    else:
        print(f"  !! Unpack import not found (upstream drift?)  {relpath}")
        missing += 1


def main():
    if not os.path.isdir(SRC):
        sys.exit(f"lerobot src not found at {SRC} (set LEROBOT_DIR or pass the path as arg 1)")
    print(f"Patching lerobot at {ROOT}\n")
    for relpath, old, new in REPLACEMENTS:
        patch_replacement(relpath, old, new)
    for relpath in UNPACK_FILES:
        patch_unpack(relpath)
    print(f"\nDone: {applied} patched, {skipped} already applied, {missing} missing/not-found.")
    if missing:
        print("WARNING: some patterns were not found. Upstream may have changed; review manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
