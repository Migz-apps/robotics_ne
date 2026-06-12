"""
Persistent operational evidence logging for assessment validation.
Writes CSV (primary) and JSON Lines (mirror) with speaker ID, confidence,
motor commands, and timestamps.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    import pandas as pd

    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


@dataclass
class OperationRecord:
    timestamp_iso: str
    timestamp_unix: float
    speaker_id: str
    confidence: float
    motor_command: str
    lock_state: str
    faces_in_frame: int
    notes: str = ""


class OperationalLogger:
    CSV_FIELDS = [
        "timestamp_iso",
        "timestamp_unix",
        "speaker_id",
        "confidence",
        "motor_command",
        "lock_state",
        "faces_in_frame",
        "notes",
    ]

    def __init__(self, logs_dir: Path, speaker_id: str):
        logs_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe = "".join(c for c in speaker_id if c.isalnum() or c in ("_", "-")) or "speaker"
        self.csv_path = logs_dir / f"operations_{safe}_{ts}.csv"
        self.jsonl_path = logs_dir / f"operations_{safe}_{ts}.jsonl"
        self._last_command: Optional[str] = None
        self._write_csv_header()

    def _write_csv_header(self) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.CSV_FIELDS).writeheader()

    def log(
        self,
        speaker_id: str,
        confidence: float,
        motor_command: str,
        lock_state: str,
        faces_in_frame: int = 0,
        notes: str = "",
        *,
        force: bool = False,
    ) -> None:
        """Append one row. Skips duplicate consecutive motor commands unless forced."""
        if not force and motor_command == self._last_command and not notes:
            return
        self._last_command = motor_command

        now = time.time()
        rec = OperationRecord(
            timestamp_iso=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            timestamp_unix=now,
            speaker_id=speaker_id,
            confidence=round(float(confidence), 4),
            motor_command=motor_command,
            lock_state=lock_state,
            faces_in_frame=int(faces_in_frame),
            notes=notes,
        )
        row = asdict(rec)

        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.CSV_FIELDS).writerow(row)

        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def summary_dataframe(self):
        """Return pandas DataFrame of the session log (requires pandas)."""
        if not _HAS_PANDAS:
            raise ImportError("pandas is required for summary_dataframe()")
        return pd.read_csv(self.csv_path)

    @property
    def paths(self) -> tuple[Path, Path]:
        return self.csv_path, self.jsonl_path
