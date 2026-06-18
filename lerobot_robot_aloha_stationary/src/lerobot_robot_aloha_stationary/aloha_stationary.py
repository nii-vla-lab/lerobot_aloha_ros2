#!/usr/bin/env python

# Copyright 2025 miyoshi-nii. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
from functools import cached_property
from typing import Any, Dict, List

import numpy as np

from interbotix_common_modules.common_robot.robot import (
    create_interbotix_global_node,
    get_interbotix_global_node,
    robot_shutdown,
    robot_startup,
)
import interbotix_common_modules.common_robot.robot as robot_mod
from interbotix_xs_modules.xs_robot.arm import InterbotixManipulatorXS
from interbotix_xs_msgs.msg import JointSingleCommand

from aloha.robot_utils import (
    torque_on,
    torque_off,
    FOLLOWER_GRIPPER_JOINT_CLOSE,
    FOLLOWER_GRIPPER_JOINT_OPEN,
    LEADER2FOLLOWER_JOINT_FN,
    FOLLOWER_GRIPPER_POSITION_NORMALIZE_FN,
    LEADER_GRIPPER_JOINT_UNNORMALIZE_FN,
    move_arms,
    move_grippers,
)

from lerobot.robots import Robot
from lerobot.cameras.utils import make_cameras_from_configs

from .config_aloha_stationary import AlohaStationaryConfig

logger = logging.getLogger(__name__)


class AlohaStationary(Robot):
    """ALOHA Stationary robot wrapper for dual-arm follower teleoperation."""

    config_class = AlohaStationaryConfig
    name = "aloha_stationary"

    def __init__(self, config: AlohaStationaryConfig):
        super().__init__(config)
        self.config = config

        self.node = self._get_or_create_interbotix_node("aloha")

        self.robots: List[InterbotixManipulatorXS] = []
        for suffix in ["right", "left"]:
            bot = InterbotixManipulatorXS(
                robot_name=f"{self.config.name}_{suffix}",
                robot_model=self.config.robot,
                group_name="arm",
                gripper_name="gripper",
                node=self.node,
                iterative_update_fk=False,
            )
            self.robots.append(bot)

        self.gripper_command = JointSingleCommand(name="gripper")
        self.dt = 1.0 / 50.0
        self.start_arm_pose = self.config.start_arm_pose
        self.joint_names = [
            "waist",
            "shoulder",
            "elbow",
            "forearm_roll",
            "wrist_angle",
            "wrist_rotate",
            "gripper",
        ]
        self.cameras = make_cameras_from_configs(config.cameras)
        self.reset_arm_pose = self.config.reset_arm_pose
        self.shutdown_on = self.config.shutdown_on

    def _get_or_create_interbotix_node(self, node_name: str):
        try:
            return get_interbotix_global_node()
        except Exception:
            return create_interbotix_global_node(node_name)

    def _make_motor_features(self, suffix: str) -> Dict[str, type]:
        return {f"{suffix}_{motor}.pos": float for motor in self.joint_names}

    @property
    def _motors_right_ft(self) -> Dict[str, type]:
        return self._make_motor_features("right")

    @property
    def _motors_left_ft(self) -> Dict[str, type]:
        return self._make_motor_features("left")

    @property
    def _cameras_ft(self) -> Dict[str, tuple]:
        return {cam: (cfg.height, cfg.width, 3) for cam, cfg in self.config.cameras.items()}

    @cached_property
    def observation_features(self) -> Dict[str, type | tuple]:
        return {**self._motors_right_ft, **self._motors_left_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> Dict[str, type]:
        return {**self._motors_right_ft, **self._motors_left_ft}

    @property
    def is_connected(self) -> bool:
        return True

    def connect(self, calibrate: bool = True) -> None:
        if not getattr(robot_mod, "_startup_requested", False):
            robot_startup(self.node)
            robot_mod._startup_requested = True

        for bot in self.robots:
            bot.core.robot_reboot_motors("single", "gripper", True)
            bot.core.robot_set_operating_modes("group", "arm", "position")
            bot.core.robot_set_operating_modes("single", "gripper", "current_based_position")
            bot.core.robot_set_motor_registers("single", "gripper", "current_limit", 300)
            torque_on(bot)

        # Move the follower to its start pose at connect time, mirroring the
        # leader's opening ceremony. robot.connect() runs before teleop.connect()
        # in lerobot-record/teleoperate, so the follower reaches start_pose
        # first instead of being skipped while the leader resets.
        self.reset()

        for cam in self.cameras.values():
            cam.connect()

        logger.info("%s connected.", self)

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        pass

    def follower_feedback(self, bot: InterbotixManipulatorXS) -> np.ndarray:
        arm_qpos = bot.arm.get_joint_positions()
        gripper_qpos = [
            FOLLOWER_GRIPPER_POSITION_NORMALIZE_FN(bot.gripper.get_gripper_position())
        ]
        return np.concatenate([arm_qpos, gripper_qpos])

    def get_observation(self) -> Dict[str, Any]:
        obs_dict: Dict[str, Any] = {}

        for bot, suffix in zip(self.robots, ["right", "left"]):
            start = time.perf_counter()
            qpos = self.follower_feedback(bot)
            obs_dict.update({f"{suffix}_{motor}.pos": val for motor, val in zip(self.joint_names, qpos)})
            logger.debug("%s read %s arm: %.1fms", self, suffix, (time.perf_counter() - start) * 1e3)

        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.async_read()
            logger.debug("%s read camera %s: %.1fms", self, cam_key, (time.perf_counter() - start) * 1e3)

        return obs_dict

    def send_action_gripper(self, bot: InterbotixManipulatorXS, action_gripper: float) -> None:
        self.gripper_command.cmd = LEADER2FOLLOWER_JOINT_FN(action_gripper)
        bot.gripper.core.pub_single.publish(self.gripper_command)

    def send_action(self, action: Dict[str, float]) -> Dict[str, float]:
        for bot, suffix in zip(self.robots, ["right", "left"]):
            arm_positions = [
                float(action[f"{suffix}_{motor}.pos"])
                for motor in self.joint_names
                if motor != "gripper"
            ]
            bot.arm.set_joint_positions(arm_positions, blocking=False)
            self.send_action_gripper(
                bot,
                float(LEADER_GRIPPER_JOINT_UNNORMALIZE_FN(action[f"{suffix}_gripper.pos"])),
            )

        obs = {}
        for bot, suffix in zip(self.robots, ["right", "left"]):
            qpos = self.follower_feedback(bot)
            obs.update({f"{suffix}_{motor}.pos": val for motor, val in zip(self.joint_names, qpos)})
        return obs

    def disconnect(self) -> None:
        move_arms(
            bot_list=self.robots,
            target_pose_list=[[0.0, -0.96, 1.16, 0.0, -0.3, 0.0]] * 2,
            moving_time=4.0,
            dt=self.dt,
        )
        move_grippers(self.robots, [FOLLOWER_GRIPPER_JOINT_OPEN] * 2, moving_time=0.5, dt=self.dt)

        if self.shutdown_on:
            move_arms(
                bot_list=self.robots,
                target_pose_list=[bot.arm.group_info.joint_sleep_positions for bot in self.robots],
                moving_time=4.0,
                dt=self.dt,
            )
            torque_off(self.robots[0])
            torque_off(self.robots[1])

        try:
            robot_shutdown(self.node)
        except RuntimeError:
            pass

        for cam in self.cameras.values():
            cam.disconnect()
        logger.info("%s disconnected.", self)

    def reset(self) -> None:
        if self.reset_arm_pose:
            move_grippers(self.robots, [FOLLOWER_GRIPPER_JOINT_OPEN] * 2, moving_time=0.5, dt=self.dt)
            move_arms(
                bot_list=self.robots,
                target_pose_list=[self.start_arm_pose] * 2,
                moving_time=4.0,
                dt=self.dt,
            )
            move_grippers(self.robots, [FOLLOWER_GRIPPER_JOINT_CLOSE] * 2, moving_time=0.5, dt=self.dt)
        logger.info("%s reset position.", self)
