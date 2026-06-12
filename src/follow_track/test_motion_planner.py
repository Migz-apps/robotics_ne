"""Logic tests for FollowMotionPlanner (no camera). Run: python -m src.follow_track.test_motion_planner"""

from src.follow_track.motion_planner import FollowMotionPlanner, LockPhase
from src.tracking_commands import MotorCommand


def test_follow_center_stops():
    m = FollowMotionPlanner()
    cmd = m.command(cx_norm=0.5, system_searching=False, lost_frames=0, faces_in_frame=1, confidence=0.9)
    assert cmd == MotorCommand.STOPPED
    assert m.phase == LockPhase.LOCKED


def test_follow_left():
    m = FollowMotionPlanner()
    cmd = m.command(cx_norm=0.2, system_searching=False, lost_frames=0, faces_in_frame=1, confidence=0.9)
    assert cmd == MotorCommand.MOVE_LEFT


def test_reacquire_scans():
    m = FollowMotionPlanner()
    cmd = m.command(cx_norm=None, system_searching=False, lost_frames=3, faces_in_frame=0, confidence=0.0)
    assert cmd == MotorCommand.SCAN
    assert m.phase == LockPhase.REACQUIRING


def test_initial_search_scans():
    m = FollowMotionPlanner()
    cmd = m.command(cx_norm=None, system_searching=True, lost_frames=0, faces_in_frame=0, confidence=0.0)
    assert cmd == MotorCommand.SCAN
    assert m.phase == LockPhase.SEARCHING


if __name__ == "__main__":
    test_follow_center_stops()
    test_follow_left()
    test_reacquire_scans()
    test_initial_search_scans()
    print("All follow_track motion planner tests passed.")
