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

from dataclasses import dataclass, field
from typing import Dict, List

from lerobot.cameras import CameraConfig
from lerobot.robots import RobotConfig


@RobotConfig.register_subclass("aloha")
@dataclass
class AlohaConfig(RobotConfig):
    """
    Configuration for the ALOHA robot.

    Attributes:
        name (str): Robot instance name (default: "follower_right").
        robot (str): Robot model identifier (default: "aloha_vx300s").
        cameras (Dict[str, CameraConfig]): Camera configurations.
        start_arm_pose (List[float]): Initial arm joint positions
            [waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate].
    """

    name: str = "follower_right"
    robot: str = "aloha_vx300s"
    start_arm_pose: List[float] = field(
        default_factory=lambda: [0.0, -0.96, 1.16, 0.0, -0.3, 0.0]
    )
    cameras: Dict[str, CameraConfig] = field(default_factory=dict)
    reset_arm_pose: bool = True
    shutdown_on: bool = False
