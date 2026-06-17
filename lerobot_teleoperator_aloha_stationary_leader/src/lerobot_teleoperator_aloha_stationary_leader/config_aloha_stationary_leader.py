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
from typing import List

from lerobot.teleoperators import TeleoperatorConfig


@TeleoperatorConfig.register_subclass("aloha_stationary_leader")
@dataclass
class AlohaStationaryLeaderConfig(TeleoperatorConfig):
    """
    Configuration for the Stationary ALOHA Leader robot (dual arm).

    Attributes:
        name (str): Robot instance name (default: "leader").
        robot (str): Robot model identifier (default: "aloha_wx250s").
        start_arm_pose (List[float]): Initial arm joint positions for each arm
            [waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate].
    """

    name: str = "leader"
    robot: str = "aloha_wx250s"
    start_arm_pose: List[float] = field(
        default_factory=lambda: [0.0, -0.96, 1.16, 0.0, -0.3, 0.0]
    )
    reset_arm_pose: bool = True
