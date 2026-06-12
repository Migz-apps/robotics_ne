"""Central configuration loaded from config.json at project root."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"


@dataclass(frozen=True)
class SystemConfig:
    team_id: str = "team313"
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    pc_lan_ip: str = "192.168.0.188"
    esp8266_arduino_core_path: str = "C:/Users/RCA/Downloads/esp8266"
    esp8266_sketch_path: str = "C:/Users/RCA/Downloads/vision_servo/vision_servo.ino"
    esp8266_sketch_path_project: str = "esp8266/vision_servo/vision_servo.ino"
    ws_host: str = "localhost"
    ws_port: int = 9002
    http_port: int = 8080
    camera_index: int = 0
    camera_rotate: int = 0  # 0, 90, 180, or 270 degrees
    camera_flip_horizontal: bool = False
    camera_flip_vertical: bool = False
    dist_thresh: float = 0.48
    deadband_left: float = 0.4
    deadband_right: float = 0.6
    publish_hz: float = 10.0
    lost_frames_before_unlock: int = 10
    out_of_frame_frames: int = 30
    command_smooth_alpha: float = 0.35
    enroll_samples_min: int = 10
    enroll_samples_max: int = 30
    enroll_samples_default: int = 15
    model_path: str = "models/embedder_arcface.onnx"
    face_db_path: str = "data/db/face_db.npz"
    logs_dir: str = "logs"

    @property
    def topic_movement(self) -> str:
        return f"vision/{self.team_id}/movement"

    @property
    def topic_heartbeat(self) -> str:
        return f"vision/{self.team_id}/heartbeat"

    def resolve(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else ROOT / p


def load_config(path: Path | None = None) -> SystemConfig:
    cfg_path = path or CONFIG_PATH
    data: Dict[str, Any] = {}
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    fields = {f.name for f in SystemConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in fields}
    return SystemConfig(**filtered)
