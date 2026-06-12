"""
Follow / search / stop motion planner.

Behaviour:
- Speaker visible + centered  -> STOPPED (hold on face)
- Speaker visible + off-center -> MOVE_LEFT / MOVE_RIGHT (follow)
- Locked but face lost          -> SCAN (servo sweeps until re-acquire)
- Initial search (no lock yet)  -> SCAN
- No faces at all               -> NO_FACE
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from src.tracking_commands import MotorCommand, MotionCommandGenerator, TrackingState


class LockPhase(str, Enum):
    SEARCHING = "SEARCHING"
    LOCKED = "LOCKED"
    REACQUIRING = "REACQUIRING"


class FollowMotionPlanner:
    """Wraps MotionCommandGenerator with lock-state-aware re-acquire logic."""

    def __init__(
        self,
        deadband_left: float = 0.4,
        deadband_right: float = 0.6,
        smooth_alpha: float = 0.35,
        lost_frames_before_unlock: int = 10,
        out_of_frame_frames: int = 30,
    ):
        self._core = MotionCommandGenerator(
            deadband_left=deadband_left,
            deadband_right=deadband_right,
            smooth_alpha=smooth_alpha,
            lost_frames_before_unlock=lost_frames_before_unlock,
            out_of_frame_frames=out_of_frame_frames,
        )
        self._last_cx: Optional[float] = None
        self._phase = LockPhase.SEARCHING

    def reset_smooth(self) -> None:
        self._core.reset_smooth()
        self._last_cx = None

    @property
    def phase(self) -> LockPhase:
        return self._phase

    def _phase_from_inputs(
        self,
        *,
        has_target: bool,
        system_searching: bool,
        lost_frames: int,
    ) -> LockPhase:
        if has_target:
            return LockPhase.LOCKED
        if not system_searching and lost_frames > 0:
            return LockPhase.REACQUIRING
        if system_searching:
            return LockPhase.SEARCHING
        return LockPhase.SEARCHING

    def command(
        self,
        *,
        cx_norm: Optional[float],
        system_searching: bool,
        lost_frames: int,
        faces_in_frame: int,
        confidence: float,
    ) -> MotorCommand:
        has_target = cx_norm is not None
        self._phase = self._phase_from_inputs(
            has_target=has_target,
            system_searching=system_searching,
            lost_frames=lost_frames,
        )

        if has_target:
            self._last_cx = cx_norm
            return self._core.command_for_target(cx_norm)

        # Face lost while we had a lock — keep scanning (do not drop to NO_FACE too early)
        if self._phase == LockPhase.REACQUIRING:
            if lost_frames >= self._core.out_of_frame_frames:
                return MotorCommand.OUT_OF_FRAME
            return MotorCommand.SCAN

        tracking = TrackingState(
            locked=False,
            searching=system_searching,
            lost_frames=lost_frames,
            faces_in_frame=faces_in_frame,
            confidence=confidence,
        )
        return self._core.command_without_target(tracking)
