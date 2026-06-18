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
from typing import Dict, List

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
    move_arms,
    move_grippers,
    LEADER_GRIPPER_JOINT_CLOSE,
    LEADER_GRIPPER_JOINT_NORMALIZE_FN,
)

from lerobot.teleoperators import Teleoperator
from lerobot.utils.errors import DeviceNotConnectedError

from .config_aloha_stationary_leader import AlohaStationaryLeaderConfig

logger = logging.getLogger(__name__)


class AlohaStationaryLeader(Teleoperator):
    """Stationary ALOHA Leader robot interface for dual-arm teleoperation."""

    config_class = AlohaStationaryLeaderConfig
    name = "aloha_stationary_leader"

    def __init__(self, config: AlohaStationaryLeaderConfig):
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

        self.bot_right = self.robots[0]
        self.bot_left = self.robots[1]

        self.gripper_command = JointSingleCommand(name="gripper")
        self.dt = 1.0 / 50.0
        self.start_arm_pose = self.config.start_arm_pose
        self.JOINT_NAMES = [
            "waist",
            "shoulder",
            "elbow",
            "forearm_roll",
            "wrist_angle",
            "wrist_rotate",
            "gripper",
        ]
        self.reset_arm_pose = self.config.reset_arm_pose

    def _get_or_create_interbotix_node(self, node_name: str):
        try:
            return get_interbotix_global_node()
        except Exception:
            return create_interbotix_global_node(node_name)

    def _make_motor_features(self, suffix: str) -> Dict[str, type]:
        return {f"{suffix}_{motor}.pos": float for motor in self.JOINT_NAMES}

    @property
    def _motors_right_ft(self) -> Dict[str, type]:
        return self._make_motor_features("right")

    @property
    def _motors_left_ft(self) -> Dict[str, type]:
        return self._make_motor_features("left")

    @cached_property
    def action_features(self) -> Dict[str, type]:
        return {**self._motors_right_ft, **self._motors_left_ft}

    @cached_property
    def feedback_features(self) -> Dict[str, type]:
        return {**self.action_features}

    @property
    def is_connected(self) -> bool:
        return True

    def connect(self, calibrate: bool = True) -> None:
        if not getattr(robot_mod, "_startup_requested", False):
            robot_startup(self.node)
            robot_mod._startup_requested = True

        for bot in self.robots:
            bot.core.robot_set_operating_modes("group", "arm", "position")
            bot.core.robot_set_operating_modes("single", "gripper", "position")

        # lerobot's teleoperate() never calls reset(), so run the opening
        # ceremony (move to start pose) and then release torque here. Without
        # this the leader stays torque-ON in position mode and cannot be
        # back-driven by the operator.
        self.reset()
        for bot in self.robots:
            torque_off(bot)

        logger.info("%s connected.", self)

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        pass

    def leader_feedback(self, bot: InterbotixManipulatorXS) -> np.ndarray:
        arm_qpos = bot.arm.get_joint_positions()
        gripper_qpos = [
            LEADER_GRIPPER_JOINT_NORMALIZE_FN(bot.gripper.get_gripper_position())
        ]
        return np.concatenate([arm_qpos, gripper_qpos])

    def get_action(self) -> Dict[str, float]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        action: Dict[str, float] = {}
        for bot, suffix in zip(self.robots, ["right", "left"]):
            start = time.perf_counter()
            qpos = self.leader_feedback(bot)
            action.update({f"{suffix}_{motor}.pos": val for motor, val in zip(self.JOINT_NAMES, qpos)})
            logger.debug("%s read %s arm action: %.1fms", self, suffix, (time.perf_counter() - start) * 1e3)
        return action

    def send_feedback(self, feedback: Dict[str, float]) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        try:
            robot_shutdown(self.node)
        except RuntimeError:
            pass
        logger.info("%s disconnected.", self)

    def reset(self) -> None:
        if self.reset_arm_pose:
            torque_on(self.robots[0])
            torque_on(self.robots[1])
            move_arms(
                bot_list=self.robots,
                target_pose_list=[self.start_arm_pose] * 2,
                moving_time=4.0,
                dt=self.dt,
            )
            move_grippers(self.robots, [LEADER_GRIPPER_JOINT_CLOSE] * 2, moving_time=0.5, dt=self.dt)
            torque_off(self.robots[0])
            torque_off(self.robots[1])
        logger.info("%s reset position.", self)
