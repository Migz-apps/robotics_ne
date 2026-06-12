"""Runtime environment checks."""

from __future__ import annotations


def check_python_and_mediapipe(*, exit_on_fail: bool = False) -> list[str]:
    errors: list[str] = []

    try:
        import cv2  # noqa: F401
    except ImportError:
        errors.append("opencv missing — activate: .\\venv\\Scripts\\Activate.ps1")

    try:
        import mediapipe as mp

        if not hasattr(mp, "solutions"):
            from mediapipe.tasks.python import vision  # noqa: F401
    except ImportError:
        errors.append("mediapipe not installed")

    if errors and exit_on_fail:
        print("Environment check failed:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    return errors
