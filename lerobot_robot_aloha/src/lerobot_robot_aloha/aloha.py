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
from typing import Any, Dict

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

from .config_aloha import AlohaConfig

logger = logging.getLogger(__name__)


class Aloha(Robot):
    """ALOHA robot wrapper for single-arm follower teleoperation."""

    config_class = AlohaConfig
    name = "aloha"

    def __init__(self, config: AlohaConfig):
        super().__init__(config)
        self.config = config

        self.node = self._get_or_create_interbotix_node("aloha")

        self.bot = InterbotixManipulatorXS(
            robot_name=self.config.name,
            robot_model=self.config.robot,
            group_name="arm",
            gripper_name="gripper",
            node=self.node,
            iterative_update_fk=False,
        )

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

    @property
    def _motors_ft(self) -> Dict[str, type]:
        return {f"{motor}.pos": float for motor in self.joint_names}

    @property
    def _cameras_ft(self) -> Dict[str, tuple]:
        return {
            cam: (
                self.config.cameras[cam].height,
                self.config.cameras[cam].width,
                3,
            )
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> Dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> Dict[str, type]:
        return {**self._motors_ft}

    @property
    def is_connected(self) -> bool:
        return True

    def connect(self, calibrate: bool = True) -> None:
        if not getattr(robot_mod, "_startup_requested", False):
            robot_startup(self.node)
            robot_mod._startup_requested = True

        self.bot.core.robot_reboot_motors("single", "gripper", True)
        self.bot.core.robot_set_operating_modes("group", "arm", "position")
        self.bot.core.robot_set_operating_modes("single", "gripper", "current_based_position")
        self.bot.core.robot_set_motor_registers("single", "gripper", "current_limit", 300)
        torque_on(self.bot)

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

    def follower_feedback(self) -> np.ndarray:
        arm_qpos = self.bot.arm.get_joint_positions()
        gripper_qpos = [
            FOLLOWER_GRIPPER_POSITION_NORMALIZE_FN(
                self.bot.gripper.get_gripper_position()
            )
        ]
        return np.concatenate([arm_qpos, gripper_qpos])

    def get_observation(self) -> Dict[str, Any]:
        obs_dict: Dict[str, Any] = {}

        start = time.perf_counter()
        qpos = self.follower_feedback()
        obs_dict.update({f"{motor}.pos": val for motor, val in zip(self.joint_names, qpos)})
        logger.debug("%s read state: %.1fms", self, (time.perf_counter() - start) * 1e3)

        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.async_read()
            logger.debug("%s read %s: %.1fms", self, cam_key, (time.perf_counter() - start) * 1e3)

        return obs_dict

    def send_action_gripper(self, action_gripper: float) -> None:
        self.gripper_command.cmd = LEADER2FOLLOWER_JOINT_FN(action_gripper)
        self.bot.gripper.core.pub_single.publish(self.gripper_command)

    def send_action(self, action: Dict[str, float]) -> Dict[str, float]:
        arm_positions = [
            float(action[f"{motor}.pos"])
            for motor in self.joint_names
            if motor != "gripper"
        ]
        self.bot.arm.set_joint_positions(arm_positions, blocking=False)
        self.send_action_gripper(float(LEADER_GRIPPER_JOINT_UNNORMALIZE_FN(action["gripper.pos"])))

        qpos = self.follower_feedback()
        return {f"{motor}.pos": val for motor, val in zip(self.joint_names, qpos)}

    def disconnect(self) -> None:
        move_arms(
            bot_list=[self.bot],
            target_pose_list=[[0.0, -0.96, 1.16, 0.0, -0.3, 0.0]],
            moving_time=4.0,
            dt=self.dt,
        )
        move_grippers([self.bot], [FOLLOWER_GRIPPER_JOINT_OPEN], moving_time=0.5, dt=self.dt)

        if self.shutdown_on:
            move_arms(
                bot_list=[self.bot],
                target_pose_list=[self.bot.arm.group_info.joint_sleep_positions],
                moving_time=4.0,
                dt=self.dt,
            )
            torque_off(self.bot)

        try:
            robot_shutdown(self.node)
        except RuntimeError:
            pass

        for cam in self.cameras.values():
            cam.disconnect()
        logger.info("%s disconnected.", self)

    def reset(self) -> None:
        if self.reset_arm_pose:
            move_grippers([self.bot], [FOLLOWER_GRIPPER_JOINT_OPEN], moving_time=0.5, dt=self.dt)
            move_arms(
                bot_list=[self.bot],
                target_pose_list=[self.start_arm_pose],
                moving_time=4.0,
                dt=self.dt,
            )
            move_grippers([self.bot], [FOLLOWER_GRIPPER_JOINT_CLOSE], moving_time=0.5, dt=self.dt)
        logger.info("%s reset position.", self)
