"""
Recognize -> Track -> Command pipeline helpers.
Converts horizontal face position into motor commands with deadband and smoothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class MotorCommand(str, Enum):
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    STOPPED = "STOPPED"
    CENTERED = "CENTERED"
    SCAN = "SCAN"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    NO_FACE = "NO_FACE"

    @classmethod
    def aliases(cls, cmd: "MotorCommand") -> Tuple[str, ...]:
        """Assessment brief uses several names; ESP accepts all aliases."""
        mapping = {
            cls.MOVE_LEFT: ("MOVE_LEFT", "MOVED_LEFT", "LEFT"),
            cls.MOVE_RIGHT: ("MOVE_RIGHT", "MOVED_RIGHT", "RIGHT"),
            cls.STOPPED: ("STOPPED", "STOP", "CENTERED"),
            cls.CENTERED: ("CENTERED", "STOPPED", "STOP"),
            cls.SCAN: ("SCAN",),
            cls.OUT_OF_FRAME: ("OUT_OF_FRAME",),
            cls.NO_FACE: ("NO_FACE",),
        }
        return mapping.get(cmd, (cmd.value,))


@dataclass
class TrackingState:
    locked: bool
    searching: bool
    lost_frames: int
    faces_in_frame: int
    confidence: float


class MotionCommandGenerator:
    def __init__(
        self,
        deadband_left: float = 0.4,
        deadband_right: float = 0.6,
        smooth_alpha: float = 0.35,
        lost_frames_before_unlock: int = 10,
        out_of_frame_frames: int = 30,
    ):
        self.deadband_left = deadband_left
        self.deadband_right = deadband_right
        self.smooth_alpha = smooth_alpha
        self.lost_frames_before_unlock = lost_frames_before_unlock
        self.out_of_frame_frames = out_of_frame_frames
        self._smooth_cx: Optional[float] = None
        self._last_command: MotorCommand = MotorCommand.SCAN

    def reset_smooth(self) -> None:
        self._smooth_cx = None

    def _smooth_center(self, cx_norm: float) -> float:
        if self._smooth_cx is None:
            self._smooth_cx = cx_norm
        else:
            a = self.smooth_alpha
            self._smooth_cx = a * cx_norm + (1.0 - a) * self._smooth_cx
        return self._smooth_cx

    def command_for_target(
        self,
        cx_norm: float,
    ) -> MotorCommand:
        cx = self._smooth_center(cx_norm)
        if cx < self.deadband_left:
            cmd = MotorCommand.MOVE_LEFT
        elif cx > self.deadband_right:
            cmd = MotorCommand.MOVE_RIGHT
        else:
            cmd = MotorCommand.STOPPED
        self._last_command = cmd
        return cmd

    def command_without_target(self, tracking: TrackingState) -> MotorCommand:
        if tracking.searching:
            cmd = MotorCommand.SCAN
        elif tracking.lost_frames > 0:
            if tracking.lost_frames >= self.out_of_frame_frames:
                cmd = MotorCommand.OUT_OF_FRAME
            else:
                cmd = MotorCommand.SCAN
        elif tracking.faces_in_frame > 0:
            cmd = MotorCommand.SCAN
        else:
            cmd = MotorCommand.NO_FACE
        self._last_command = cmd
        return cmd
