# src/camera.py
"""Camera open + software rotation/flip (no physical remount needed)."""
from __future__ import annotations

import argparse
import sys
from typing import Optional

import cv2
import numpy as np

_ROTATE_CODES = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def open_camera(index: int) -> cv2.VideoCapture:
    """Open webcam by index. On Windows, DirectShow (CAP_DSHOW) is more reliable."""
    if sys.platform == "win32":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index)
    return cap


def correct_frame(
    frame: np.ndarray,
    rotate: int = 0,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
) -> np.ndarray:
    """Apply software rotation/flip so an upside-down or mirrored camera looks upright."""
    out = frame
    if flip_horizontal:
        out = cv2.flip(out, 1)
    if flip_vertical:
        out = cv2.flip(out, 0)
    code = _ROTATE_CODES.get(rotate)
    if code is not None:
        out = cv2.rotate(out, code)
    return out


def correct_frame_from_config(frame: np.ndarray, cfg) -> np.ndarray:
    return correct_frame(
        frame,
        rotate=int(getattr(cfg, "camera_rotate", 0)),
        flip_horizontal=bool(getattr(cfg, "camera_flip_horizontal", False)),
        flip_vertical=bool(getattr(cfg, "camera_flip_vertical", False)),
    )


def preview_loop(
    index: int,
    rotate: int = 180,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
) -> None:
    """Live preview — press 0/9/8/7 to try rotations, h/v flip, q quit."""
    cap = open_camera(index)
    if not cap.isOpened():
        raise RuntimeError(f"Camera {index} not opened.")

    r, fh, fv = rotate, flip_horizontal, flip_vertical
    print(f"Camera {index} | rotate={r} flip_h={fh} flip_v={fv}")
    print("Keys: 0=0deg  9=90deg  8=180deg  7=270deg  h=flip H  v=flip V  q=quit")
    print("When it looks right, copy those values into config.json")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame.")
            break

        view = correct_frame(frame, rotate=r, flip_horizontal=fh, flip_vertical=fv)
        label = f"rotate={r} flip_h={fh} flip_v={fv}"
        cv2.putText(
            view, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )
        cv2.imshow("camera preview (software upright)", view)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("0"):
            r = 0
        elif key == ord("9"):
            r = 90
        elif key == ord("8"):
            r = 180
        elif key == ord("7"):
            r = 270
        elif key == ord("h"):
            fh = not fh
        elif key == ord("v"):
            fv = not fv

        if key in (ord("0"), ord("9"), ord("8"), ord("7"), ord("h"), ord("v")):
            print(f"  camera_rotate={r}, flip_h={fh}, flip_v={fv}")

    cap.release()
    cv2.destroyAllWindows()
    print(f'\nSuggested config.json:\n  "camera_rotate": {r},\n  "camera_flip_horizontal": {str(fh).lower()},\n  "camera_flip_vertical": {str(fv).lower()},')


def main(argv: Optional[list[str]] = None) -> None:
    from .config import load_config

    cfg = load_config()
    p = argparse.ArgumentParser(description="Preview camera with software rotation/flip")
    p.add_argument("--index", type=int, default=cfg.camera_index)
    p.add_argument("--rotate", type=int, default=cfg.camera_rotate, choices=[0, 90, 180, 270])
    p.add_argument("--flip-horizontal", action="store_true", default=cfg.camera_flip_horizontal)
    p.add_argument("--flip-vertical", action="store_true", default=cfg.camera_flip_vertical)
    args = p.parse_args(argv)
    preview_loop(args.index, args.rotate, args.flip_horizontal, args.flip_vertical)


if __name__ == "__main__":
    main()
