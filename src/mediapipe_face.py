"""Face mesh: legacy solutions (0.10.21) or tasks FaceLandmarker (0.10.35+)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "face_landmarker.task"


@dataclass
class _MeshResult:
    multi_face_landmarks: List[Any]


class _LandmarkList:
    def __init__(self, landmarks):
        self.landmark = landmarks


def _model_path() -> Path:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    raise FileNotFoundError(
        f"Missing {MODEL_PATH}. Place face_landmarker.task in models/ (no auto-download)."
    )


class FaceMeshCompat:
    def __init__(
        self,
        static_image_mode: bool = False,
        max_num_faces: int = 10,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        del refine_landmarks
        import mediapipe as mp

        if hasattr(mp, "solutions"):
            self._legacy = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=static_image_mode,
                max_num_faces=max_num_faces,
                refine_landmarks=True,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self._tasks = None
            return

        from mediapipe import Image, ImageFormat
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as bo

        mode = vision.RunningMode.IMAGE if static_image_mode else vision.RunningMode.VIDEO
        opts = vision.FaceLandmarkerOptions(
            base_options=bo.BaseOptions(model_asset_path=str(_model_path())),
            running_mode=mode,
            num_faces=max_num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._legacy = None
        self._tasks = vision.FaceLandmarker.create_from_options(opts)
        self._Image = Image
        self._ImageFormat = ImageFormat
        self._ts = 0

    def process(self, rgb: np.ndarray) -> _MeshResult:
        if self._legacy is not None:
            return self._legacy.process(rgb)

        self._ts += 33
        mp_image = self._Image(image_format=self._ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._tasks.detect_for_video(mp_image, self._ts)
        faces = []
        if result.face_landmarks:
            for fl in result.face_landmarks:
                lm = [SimpleNamespace(x=p.x, y=p.y, z=p.z) for p in fl]
                faces.append(_LandmarkList(lm))
        return _MeshResult(multi_face_landmarks=faces)

    def close(self) -> None:
        if self._legacy is not None:
            self._legacy.close()
        elif self._tasks is not None:
            self._tasks.close()


def create_face_mesh(**kwargs) -> FaceMeshCompat:
    return FaceMeshCompat(**kwargs)
