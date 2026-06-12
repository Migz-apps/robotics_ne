"""List USB cameras and preview one. Run: python -m src.list_cameras"""
from __future__ import annotations

import sys

import cv2

from .camera import correct_frame_from_config, open_camera
from .config import load_config


def main() -> None:
    cfg = load_config()
    print("Scanning camera indices 0-4...")
    found = []
    for i in range(5):
        cap = open_camera(i)
        if cap.isOpened():
            found.append(i)
            cap.release()
            print(f"  Camera {i}: OK")
    if not found:
        print("No cameras found.")
        raise SystemExit(1)

    idx = cfg.camera_index if cfg.camera_index in found else found[0]
    print(f"\nPreview camera {idx} (config camera_index={cfg.camera_index}, rotate={cfg.camera_rotate})")
    print("Press Q to quit.")

    cap = open_camera(idx)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        view = correct_frame_from_config(frame, cfg)
        cv2.putText(view, f"camera {idx}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("list_cameras preview", view)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
