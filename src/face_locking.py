"""
face_locking.py — single-speaker lock, re-acquisition, and action history.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

try:
    from .camera import correct_frame_from_config, open_camera
    from .config import load_config
    from .haar_5pt import Haar5ptDetector, align_face_5pt
    from .recognize import ArcFaceEmbedderONNX, FaceDBMatcher, load_db_npz
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    from src.camera import correct_frame_from_config, open_camera
    from src.config import load_config
    from src.haar_5pt import Haar5ptDetector, align_face_5pt
    from src.recognize import ArcFaceEmbedderONNX, FaceDBMatcher, load_db_npz


@dataclass
class FaceAction:
    timestamp: float
    action_type: str
    details: str


@dataclass
class LockResult:
    vis: np.ndarray
    target_face: Optional[object]
    confidence: float
    locked: bool
    searching: bool
    lost_frames: int
    faces_in_frame: int


class FaceActionDetector:
    def __init__(self):
        self.P_LEFT_EYE = [33, 160, 158, 133, 153, 144]
        self.P_RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        self.P_NOSE_TIP = 1
        self.EAR_THRESH = 0.22
        self.last_blink_time = 0.0
        self.blink_cooldown = 0.3

    def _ear(self, lm, idxs):
        v1 = np.linalg.norm(lm[idxs[1]] - lm[idxs[5]])
        v2 = np.linalg.norm(lm[idxs[2]] - lm[idxs[4]])
        h = np.linalg.norm(lm[idxs[0]] - lm[idxs[3]])
        return (v1 + v2) / (2.0 * h + 1e-6)

    def detect(self, mp_landmarks, frame_w, frame_h) -> List[Tuple[str, str]]:
        actions = []
        now = time.time()
        coords = np.array([[p.x, p.y] for p in mp_landmarks])

        left_ear = self._ear(coords, self.P_LEFT_EYE)
        right_ear = self._ear(coords, self.P_RIGHT_EYE)
        avg_ear = (left_ear + right_ear) / 2.0
        if avg_ear < self.EAR_THRESH and (now - self.last_blink_time) > self.blink_cooldown:
            actions.append(("BLINK", f"EAR={avg_ear:.2f}"))
            self.last_blink_time = now

        left_cheek = coords[234]
        right_cheek = coords[454]
        face_width = np.linalg.norm(right_cheek - left_cheek)
        mouth_l = coords[61]
        mouth_r = coords[291]
        mouth_width = np.linalg.norm(mouth_r - mouth_l)
        ratio = mouth_width / (face_width + 1e-6)
        if ratio > 0.45:
            actions.append(("SMILE", f"ratio={ratio:.2f}"))

        nose = coords[self.P_NOSE_TIP]
        if nose[0] < 0.50:
            actions.append(("HEAD_LEFT", f"nose_x={nose[0]:.2f}"))
        elif nose[0] > 0.60:
            actions.append(("HEAD_RIGHT", f"nose_x={nose[0]:.2f}"))

        return actions


class LockState(Enum):
    SEARCHING = 0
    LOCKED = 1


def bbox_center_dist(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    cx1 = (box1[0] + box1[2]) / 2.0
    cy1 = (box1[1] + box1[3]) / 2.0
    cx2 = (box2[0] + box2[2]) / 2.0
    cy2 = (box2[1] + box2[3]) / 2.0
    return float(((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5)


class FaceLockSystem:
    def __init__(
        self,
        target_name: str,
        matcher: FaceDBMatcher,
        detector: Haar5ptDetector,
        max_lost_frames: int = 10,
        logs_dir: Path | None = None,
    ):
        self.target_name = target_name
        self.matcher = matcher
        self.det = detector
        self.state = LockState.SEARCHING
        self.action_det = FaceActionDetector()
        self.history: List[FaceAction] = []
        self.lost_frames = 0
        self.MAX_LOST_FRAMES = max_lost_frames
        self.last_target_box = None
        self.verify_counter = 0
        self.last_confidence = 0.0

        logs_dir = logs_dir or Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in target_name if c.isalnum())
        self.history_file = logs_dir / f"{safe_name}_actions_{ts}.txt"
        print(f"[FaceLock] Target: {target_name} | action log: {self.history_file}")

    def log_action(self, atype: str, details: str) -> None:
        now = time.time()
        if self.history:
            last = self.history[-1]
            if last.action_type == atype and (now - last.timestamp) < 1.0:
                return
        act = FaceAction(timestamp=now, action_type=atype, details=details)
        self.history.append(act)
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))} | {atype} | {details}\n"
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(line)
        print(f">> ACTION: {atype} ({details})")

    def process_frame(self, frame: np.ndarray, embedder: ArcFaceEmbedderONNX) -> LockResult:
        vis = frame.copy()
        h, w = vis.shape[:2]
        faces, mp_res = self.det.detect_with_mesh(frame, max_faces=5)

        target_face = None
        target_sim = self.last_confidence
        tracked_face_idx = -1

        # Proximity-only tracking while lost causes STOPPED instead of SCAN on the servo.
        if self.state == LockState.LOCKED and self.last_target_box is not None and self.lost_frames == 0:
            min_dist = float("inf")
            for i, f in enumerate(faces):
                dist = bbox_center_dist((f.x1, f.y1, f.x2, f.y2), self.last_target_box)
                diag = ((f.x2 - f.x1) ** 2 + (f.y2 - f.y1) ** 2) ** 0.5
                if dist < diag * 0.8 and dist < min_dist:
                    min_dist = dist
                    tracked_face_idx = i

            if tracked_face_idx != -1:
                f = faces[tracked_face_idx]
                target_face = f
                self.verify_counter += 1
                if self.verify_counter >= 15:
                    self.verify_counter = 0
                    aligned, _ = align_face_5pt(frame, f.kps, out_size=(112, 112))
                    emb = embedder.embed(aligned)
                    mr = self.matcher.match(emb)
                    if not mr.accepted or mr.name != self.target_name:
                        self.state = LockState.SEARCHING
                        self.last_target_box = None
                        target_face = None
                        tracked_face_idx = -1
                        self.log_action("LOCK_LOST", "identity_verification_failed")
                    else:
                        target_sim = mr.similarity
                        self.last_confidence = target_sim
                else:
                    target_sim = self.last_confidence

        if target_face is None:
            for i, f in enumerate(faces):
                aligned, _ = align_face_5pt(frame, f.kps, out_size=(112, 112))
                emb = embedder.embed(aligned)
                mr = self.matcher.match(emb)

                if mr.accepted and mr.name == self.target_name:
                    if mr.similarity > target_sim:
                        target_sim = mr.similarity
                        self.last_confidence = target_sim
                        target_face = f
                        tracked_face_idx = i
                elif mr.accepted:
                    cv2.rectangle(vis, (f.x1, f.y1), (f.x2, f.y2), (255, 200, 0), 2)
                    cv2.putText(
                        vis,
                        f"ignored:{mr.name}",
                        (f.x1, max(0, f.y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 200, 0),
                        2,
                    )
                else:
                    cv2.rectangle(vis, (f.x1, f.y1), (f.x2, f.y2), (100, 100, 100), 1)
        else:
            for i, f in enumerate(faces):
                if i != tracked_face_idx:
                    cv2.rectangle(vis, (f.x1, f.y1), (f.x2, f.y2), (100, 100, 100), 1)

        if self.state == LockState.SEARCHING:
            cv2.putText(
                vis,
                f"SCAN: {self.target_name}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 165, 255),
                2,
            )
            if target_face is not None:
                self.state = LockState.LOCKED
                self.lost_frames = 0
                self.verify_counter = 0
                self.last_target_box = (
                    target_face.x1,
                    target_face.y1,
                    target_face.x2,
                    target_face.y2,
                )
                self.log_action("LOCK_ACQUIRED", f"sim={target_sim:.3f}")

        if self.state == LockState.LOCKED:
            if target_face is not None:
                self.lost_frames = 0
                f = target_face
                cv2.rectangle(vis, (f.x1, f.y1), (f.x2, f.y2), (0, 255, 0), 3)
                cv2.putText(
                    vis,
                    f"SPEAKER: {self.target_name} ({target_sim:.2f})",
                    (f.x1, max(0, f.y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                self.last_target_box = (f.x1, f.y1, f.x2, f.y2)

                if mp_res and mp_res.multi_face_landmarks:
                    fw_x = (f.x1 + f.x2) / 2
                    fw_y = (f.y1 + f.y2) / 2
                    best_lm = None
                    min_dist = float("inf")
                    for lm_list in mp_res.multi_face_landmarks:
                        nose = lm_list.landmark[1]
                        nx, ny = nose.x * w, nose.y * h
                        dist = ((nx - fw_x) ** 2 + (ny - fw_y) ** 2) ** 0.5
                        if dist < min_dist:
                            min_dist = dist
                            best_lm = lm_list.landmark
                    if best_lm and min_dist < max(f.x2 - f.x1, f.y2 - f.y1):
                        for atype, desc in self.action_det.detect(best_lm, w, h):
                            self.log_action(atype, desc)
            else:
                self.lost_frames += 1
                cv2.putText(
                    vis,
                    f"LOCKED: {self.target_name} | LOST {self.lost_frames}/{self.MAX_LOST_FRAMES}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )
                if self.lost_frames > self.MAX_LOST_FRAMES:
                    self.state = LockState.SEARCHING
                    self.last_target_box = None
                    self.log_action("LOCK_LOST", "target_disappeared")

        return LockResult(
            vis=vis,
            target_face=target_face,
            confidence=float(target_sim if target_face else 0.0),
            locked=self.state == LockState.LOCKED and target_face is not None,
            searching=self.state == LockState.SEARCHING,
            lost_frames=self.lost_frames,
            faces_in_frame=len(faces),
        )


def main() -> None:
    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, required=True, help="Enrolled speaker to lock onto")
    args = parser.parse_args()

    db_path = cfg.resolve(cfg.face_db_path)
    model_path = cfg.resolve(cfg.model_path)
    if not db_path.exists():
        print("No database found. Run: python -m src.enroll")
        return

    det = Haar5ptDetector(min_size=(70, 70), debug=False)
    embedder = ArcFaceEmbedderONNX(model_path=str(model_path), input_size=(112, 112))
    db = load_db_npz(db_path)
    matcher = FaceDBMatcher(db, dist_thresh=cfg.dist_thresh)
    system = FaceLockSystem(
        args.name,
        matcher,
        det,
        max_lost_frames=cfg.lost_frames_before_unlock,
        logs_dir=cfg.resolve(cfg.logs_dir),
    )

    cap = open_camera(cfg.camera_index)
    print("Face locking demo. Press 'q' to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = correct_frame_from_config(frame, cfg)
        result = system.process_frame(frame, embedder)
        cv2.imshow("Face Locking", result.vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
