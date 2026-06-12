"""
vision_node.py
AI vision node: enroll speaker lock -> track -> MQTT motor commands + evidence logging.
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

sys.path.append(str(Path(__file__).parent.parent))

from src.camera import correct_frame_from_config, open_camera
from src.config import load_config
from src.env_check import check_python_and_mediapipe
from src.face_locking import FaceLockSystem, LockState
from src.haar_5pt import Haar5ptDetector
from src.operational_log import OperationalLogger
from src.recognize import ArcFaceEmbedderONNX, FaceDBMatcher, load_db_npz
from src.tracking_commands import MotionCommandGenerator, MotorCommand, TrackingState


class VisionNode:
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
                client_id=f"{self.cfg.team_id}_vision_node",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            )
        except (TypeError, AttributeError):
            self.client = mqtt.Client(client_id=f"{self.cfg.team_id}_vision_node")
        self.client.on_connect = self._on_connect
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

        print("Initializing face recognition...")
        model_path = self.cfg.resolve(self.cfg.model_path)
        db_path = self.cfg.resolve(self.cfg.face_db_path)

        if not model_path.exists():
            print(f"ERROR: ONNX model not found at {model_path}")
            print("Place embedder_arcface.onnx in models/ (see models/README.md).")
            sys.exit(1)
        if not db_path.exists():
            print(f"ERROR: Face DB not found at {db_path}. Run: python -m src.enroll")
            sys.exit(1)

        self.det = Haar5ptDetector(min_size=(70, 70))
        self.embedder = ArcFaceEmbedderONNX(
            model_path=str(model_path),
            input_size=(112, 112),
        )

        db = load_db_npz(db_path)
        if target_name not in db:
            print(f"WARNING: '{target_name}' not in DB. Available: {list(db.keys())}")

        self.matcher = FaceDBMatcher(db, dist_thresh=self.cfg.dist_thresh)
        self.system = FaceLockSystem(
            target_name,
            self.matcher,
            self.det,
            max_lost_frames=self.cfg.lost_frames_before_unlock,
            logs_dir=self.cfg.resolve(self.cfg.logs_dir),
        )
        self.motion = MotionCommandGenerator(
            deadband_left=self.cfg.deadband_left,
            deadband_right=self.cfg.deadband_right,
            smooth_alpha=self.cfg.command_smooth_alpha,
            lost_frames_before_unlock=self.cfg.lost_frames_before_unlock,
            out_of_frame_frames=self.cfg.out_of_frame_frames,
        )
        self.op_log = OperationalLogger(
            self.cfg.resolve(self.cfg.logs_dir),
            target_name,
        )

        self.running = True
        self.last_heartbeat = 0.0
        self.last_publish = 0.0
        self.publish_interval = 1.0 / max(1.0, self.cfg.publish_hz)
        self.snapshot_sent = False

        csv_p, jsonl_p = self.op_log.paths
        print(f"Operational log CSV : {csv_p}")
        print(f"Operational log JSONL: {jsonl_p}")

    def _on_connect(self, client, userdata, flags, rc):
        print(f"MQTT connected (rc={rc})")
        self._publish_heartbeat()

    def _publish_heartbeat(self) -> None:
        payload = {
            "node": "pc_vision",
            "status": "ONLINE",
            "target": self.target_name,
            "timestamp": time.time(),
        }
        self.client.publish(self.cfg.topic_heartbeat, json.dumps(payload))

    def _publish_movement(
        self,
        status: MotorCommand,
        confidence: float,
        locked: bool,
        faces_in_frame: int,
        face_image: np.ndarray | None = None,
    ) -> None:
        payload = {
            "status": status.value,
            "aliases": list(MotorCommand.aliases(status)),
            "confidence": round(float(confidence), 4),
            "target": self.target_name,
            "locked": locked,
            "faces_in_frame": faces_in_frame,
            "timestamp": time.time(),
        }
        if face_image is not None:
            ok, buffer = cv2.imencode(".jpg", face_image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                payload["face_image"] = base64.b64encode(buffer).decode("utf-8")

        self.client.publish(self.cfg.topic_movement, json.dumps(payload))
        print(f"MQTT -> {status.value} conf={confidence:.3f} locked={locked}")

    def _lock_state_label(self) -> str:
        if self.system.state == LockState.LOCKED:
            return "LOCKED"
        if self.system.lost_frames > 0:
            return "REACQUIRING"
        return "SEARCHING"

    def run(self) -> None:
        cap = open_camera(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {self.camera_index}")

        print(f"Vision node running. Target={self.target_name}")
        print(f"Publishing to {self.cfg.topic_movement} via {self.broker}:{self.port}")

        self.op_log.log(
            self.target_name,
            0.0,
            MotorCommand.SCAN.value,
            "SEARCHING",
            notes="session_start",
            force=True,
        )

        while self.running:
            ok, frame = cap.read()
            if not ok:
                break

            frame = correct_frame_from_config(frame, self.cfg)
            h, w = frame.shape[:2]

            result = self.system.process_frame(frame, self.embedder)
            vis = result.vis
            face_crop = None
            motor_cmd: MotorCommand

            tracking = TrackingState(
                locked=result.locked,
                searching=result.searching,
                lost_frames=result.lost_frames,
                faces_in_frame=result.faces_in_frame,
                confidence=result.confidence,
            )

            if result.target_face is not None:
                f = result.target_face
                if not self.snapshot_sent:
                    x1, y1, x2, y2 = int(f.x1), int(f.y1), int(f.x2), int(f.y2)
                    pad = 20
                    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                    face_crop = frame[y1:y2, x1:x2]
                    self.snapshot_sent = True

                cx_norm = ((f.x1 + f.x2) / 2.0) / w
                motor_cmd = self.motion.command_for_target(cx_norm)
            else:
                if self.snapshot_sent:
                    self.snapshot_sent = False
                    self.motion.reset_smooth()
                motor_cmd = self.motion.command_without_target(tracking)

            lock_label = self._lock_state_label()
            cv2.putText(
                vis,
                f"CMD: {motor_cmd.value} | conf: {result.confidence:.2f}",
                (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2,
            )

            now = time.time()
            if now - self.last_publish >= self.publish_interval:
                self._publish_movement(
                    motor_cmd,
                    result.confidence,
                    result.locked,
                    result.faces_in_frame,
                    face_crop,
                )
                self.op_log.log(
                    self.target_name,
                    result.confidence,
                    motor_cmd.value,
                    lock_label,
                    faces_in_frame=result.faces_in_frame,
                )
                self.last_publish = now

            if now - self.last_heartbeat > 5.0:
                self._publish_heartbeat()
                self.last_heartbeat = now

            cv2.imshow("Vision Node (Speaker Lock)", vis)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        self.op_log.log(
            self.target_name,
            0.0,
            MotorCommand.NO_FACE.value,
            "STOPPED",
            notes="session_end",
            force=True,
        )
        cap.release()
        cv2.destroyAllWindows()
        self.client.loop_stop()


def main() -> None:
    check_python_and_mediapipe(exit_on_fail=True)
    parser = argparse.ArgumentParser(description="Speaker-lock vision node with MQTT control")
    parser.add_argument("--broker", type=str, default=None, help="MQTT broker host/IP")
    parser.add_argument("--port", type=int, default=None, help="MQTT broker port")
    parser.add_argument("--name", type=str, required=True, help="Enrolled speaker name to lock onto")
    parser.add_argument("--camera-index", type=int, default=None, help="Override config camera_index")
    args = parser.parse_args()

    node = VisionNode(
        args.name,
        broker=args.broker,
        port=args.port,
        camera_index=args.camera_index,
    )
    node.run()


if __name__ == "__main__":
    main()
