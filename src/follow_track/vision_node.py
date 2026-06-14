"""
Vision node with follow + re-acquire tracking.

Run (same MQTT/topics/logs as default vision_node):
  python -m src.follow_track.vision_node --name Miguel
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.camera import correct_frame_from_config, open_camera
from src.config import load_config
from src.env_check import check_python_and_mediapipe
from src.face_locking import FaceLockSystem, LockState
from src.follow_track.motion_planner import FollowMotionPlanner, LockPhase
from src.haar_5pt import Haar5ptDetector
from src.operational_log import OperationalLogger
from src.recognize import ArcFaceEmbedderONNX, FaceDBMatcher, load_db_npz
from src.tracking_commands import MotorCommand


class FollowVisionNode:
    def __init__(
        self,
        target_name: str,
        broker: str | None = None,
        port: int | None = None,
        camera_index: int | None = None,
    ):
        self.cfg = load_config()
        self.broker = broker or self.cfg.mqtt_broker
        self.port = port or self.cfg.mqtt_port
        self.target_name = target_name
        self.camera_index = camera_index if camera_index is not None else self.cfg.camera_index

        try:
            self.client = mqtt.Client(
                client_id=f"{self.cfg.team_id}_follow_track",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            )
        except (TypeError, AttributeError):
            self.client = mqtt.Client(client_id=f"{self.cfg.team_id}_follow_track")
        self.client.on_connect = self._on_connect
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

        model_path = self.cfg.resolve(self.cfg.model_path)
        db_path = self.cfg.resolve(self.cfg.face_db_path)
        if not model_path.exists():
            print(f"ERROR: ONNX model not found at {model_path}")
            sys.exit(1)
        if not db_path.exists():
            print(f"ERROR: Face DB not found at {db_path}")
            sys.exit(1)

        self.det = Haar5ptDetector(min_size=(70, 70))
        self.embedder = ArcFaceEmbedderONNX(model_path=str(model_path), input_size=(112, 112))
        db = load_db_npz(db_path)
        self.matcher = FaceDBMatcher(db, dist_thresh=self.cfg.dist_thresh)
        # Keep lock longer while scanning so the servo can sweep and re-find the speaker.
        reacquire_frames = max(self.cfg.lost_frames_before_unlock, 90)
        self.system = FaceLockSystem(
            target_name,
            self.matcher,
            self.det,
            max_lost_frames=reacquire_frames,
            logs_dir=self.cfg.resolve(self.cfg.logs_dir),
        )
        self.motion = FollowMotionPlanner(
            deadband_left=self.cfg.deadband_left,
            deadband_right=self.cfg.deadband_right,
            smooth_alpha=self.cfg.command_smooth_alpha,
            lost_frames_before_unlock=reacquire_frames,
            out_of_frame_frames=max(self.cfg.out_of_frame_frames, reacquire_frames * 2),
        )
        self.op_log = OperationalLogger(self.cfg.resolve(self.cfg.logs_dir), target_name)

        self.running = True
        self.last_heartbeat = 0.0
        self.last_publish = 0.0
        self.publish_interval = 1.0 / max(1.0, self.cfg.publish_hz)
        self.snapshot_sent = False
        self.had_target_once = False

        print("Follow-track vision node (re-acquire + follow mode)")
        print(f"Target={target_name} | topic={self.cfg.topic_movement}")

    def _on_connect(self, client, userdata, flags, rc):
        print(f"MQTT connected (rc={rc})")

    def _publish_movement(self, status: MotorCommand, confidence: float, locked: bool, faces: int, crop=None):
        payload = {
            "status": status.value,
            "mode": "follow_track",
            "phase": self.motion.phase.value,
            "confidence": round(float(confidence), 4),
            "target": self.target_name,
            "locked": locked,
            "faces_in_frame": faces,
            "timestamp": time.time(),
        }
        if crop is not None:
            ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                payload["face_image"] = base64.b64encode(buf).decode("utf-8")
        self.client.publish(self.cfg.topic_movement, json.dumps(payload))
        print(f"MQTT -> {status.value} phase={self.motion.phase.value} conf={confidence:.3f}")

    def _lock_label(self, result) -> str:
        if self.motion.phase == LockPhase.REACQUIRING:
            return "REACQUIRING"
        if result.target_face is not None:
            return "LOCKED"
        if self.system.state == LockState.SEARCHING:
            return "SEARCHING"
        return "SEARCHING"

    def run(self) -> None:
        cap = open_camera(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.camera_index}")

        self.op_log.log(self.target_name, 0.0, MotorCommand.SCAN.value, "SEARCHING", notes="follow_track_start", force=True)

        while self.running:
            ok, frame = cap.read()
            if not ok:
                break

            frame = correct_frame_from_config(frame, self.cfg)
            h, w = frame.shape[:2]
            result = self.system.process_frame(frame, self.embedder)
            vis = result.vis
            face_crop = None
            cx_norm = None

            if result.target_face is not None:
                f = result.target_face
                self.had_target_once = True
                if not self.snapshot_sent:
                    x1, y1, x2, y2 = int(f.x1), int(f.y1), int(f.x2), int(f.y2)
                    pad = 20
                    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                    face_crop = frame[y1:y2, x1:x2]
                    self.snapshot_sent = True
                cx_norm = ((f.x1 + f.x2) / 2.0) / w
            elif self.had_target_once and self.system.state == LockState.SEARCHING:
                # Fully lost — allow smooth reset for next acquisition
                self.motion.reset_smooth()
                self.snapshot_sent = False

            motor_cmd = self.motion.command(
                cx_norm=cx_norm,
                system_searching=(self.system.state == LockState.SEARCHING),
                lost_frames=result.lost_frames,
                faces_in_frame=result.faces_in_frame,
                confidence=result.confidence,
            )
            if result.target_face is None and (result.lost_frames > 0 or self.had_target_once):
                motor_cmd = MotorCommand.SCAN

            lock_label = self._lock_label(result)
            cv2.putText(
                vis,
                f"{lock_label} | CMD: {motor_cmd.value} | conf: {result.confidence:.2f}",
                (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            now = time.time()
            if now - self.last_publish >= self.publish_interval:
                self._publish_movement(
                    motor_cmd,
                    result.confidence,
                    result.target_face is not None,
                    result.faces_in_frame,
                    face_crop,
                )
                self.op_log.log(
                    self.target_name,
                    result.confidence,
                    motor_cmd.value,
                    lock_label,
                    faces_in_frame=result.faces_in_frame,
                    notes=self.motion.phase.value,
                )
                self.last_publish = now

            if now - self.last_heartbeat > 5.0:
                self.client.publish(
                    self.cfg.topic_heartbeat,
                    json.dumps({"node": "follow_track", "status": "ONLINE", "target": self.target_name}),
                )
                self.last_heartbeat = now

            cv2.imshow("Follow Track (Speaker Lock)", vis)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        self.op_log.log(self.target_name, 0.0, MotorCommand.NO_FACE.value, "STOPPED", notes="session_end", force=True)
        cap.release()
        cv2.destroyAllWindows()
        self.client.loop_stop()


def main() -> None:
    check_python_and_mediapipe(exit_on_fail=True)
    p = argparse.ArgumentParser(description="Follow + re-acquire vision node")
    p.add_argument("--name", required=True, help="Enrolled speaker name")
    p.add_argument("--broker", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--camera-index", type=int, default=None)
    args = p.parse_args()
    FollowVisionNode(args.name, broker=args.broker, port=args.port, camera_index=args.camera_index).run()


if __name__ == "__main__":
    main()
