"""
Pre-flight checks before demo / assessment.
Run: python -m src.validate_system
Does not require camera or MQTT broker to be running.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from .config import load_config
from .env_check import check_python_and_mediapipe

REQUIRED_PACKAGES = [
    ("cv2", "opencv-python"),
    ("numpy", "numpy"),
    ("onnxruntime", "onnxruntime"),
    ("mediapipe", "mediapipe"),
    ("paho.mqtt.client", "paho-mqtt"),
    ("pandas", "pandas"),
]


def check_imports() -> list[str]:
    errors = []
    for module, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(module)
        except ImportError:
            errors.append(f"Missing package: {pip_name} (pip install {pip_name})")
    return errors


def check_files(cfg) -> list[str]:
    errors = []
    model = cfg.resolve(cfg.model_path)
    if not model.exists():
        errors.append(f"ONNX model missing: {model} — see models/README.md")
    db = cfg.resolve(cfg.face_db_path)
    if not db.exists():
        errors.append(f"Face DB missing: {db} — run: python -m src.enroll")
    return errors


def main() -> int:
    cfg = load_config()
    print("=== System validation ===\n")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    env_errors = check_python_and_mediapipe()
    if env_errors:
        print("\nEnvironment:")
        for e in env_errors:
            print(f"  [FAIL] {e}")
    else:
        print("Environment: [OK]")

    import_errors = check_imports()
    if import_errors:
        print("Python packages:")
        for e in import_errors:
            print(f"  [FAIL] {e}")
    else:
        print("Python packages: [OK]")

    file_errors = check_files(cfg)
    if file_errors:
        print("\nProject files:")
        for e in file_errors:
            print(f"  [FAIL] {e}")
    else:
        print("Project files: [OK]")

    print(f"\nConfig: broker={cfg.mqtt_broker}:{cfg.mqtt_port} team={cfg.team_id}")
    print(f"Topics: {cfg.topic_movement}, {cfg.topic_heartbeat}")

    total = len(env_errors) + len(import_errors) + len(file_errors)
    if total:
        print(f"\n{total} issue(s) found. Fix before running the demo.")
        return 1
    print("\nAll checks passed. Ready to run vision node.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
