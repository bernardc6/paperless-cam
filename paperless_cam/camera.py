from __future__ import annotations

from datetime import datetime
import threading
from typing import Optional

import cv2
import numpy as np

from .config import Settings


class Camera:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._capture: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()

    def snapshot(self) -> np.ndarray:
        with self._lock:
            if self.settings.debug_no_camera:
                return self._placeholder("Debug camera")

            capture = self._ensure_capture()
            if capture is None:
                return self._placeholder("No USB camera")

            frame = None
            for _ in range(max(1, self.settings.camera_warmup_frames)):
                ok, candidate = capture.read()
                if ok and candidate is not None:
                    frame = candidate

            if frame is None:
                self.close()
                return self._placeholder("Camera read failed")

            return frame

    def jpeg(self, frame: np.ndarray, quality: int = 88) -> bytes:
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            raise RuntimeError("Could not encode camera frame")
        return buffer.tobytes()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _ensure_capture(self) -> Optional[cv2.VideoCapture]:
        if self._capture is not None and self._capture.isOpened():
            return self._capture

        capture = cv2.VideoCapture(self.settings.camera_index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera_height)

        if not capture.isOpened():
            capture.release()
            return None

        self._capture = capture
        return self._capture

    def _placeholder(self, label: str) -> np.ndarray:
        width = min(max(self.settings.camera_width, 960), 1920)
        height = min(max(self.settings.camera_height, 540), 1080)
        image = np.full((height, width, 3), (245, 246, 242), dtype=np.uint8)
        cv2.rectangle(image, (80, 70), (width - 80, height - 70), (222, 225, 216), 5)
        cv2.putText(image, "paperless-cam", (120, 155), cv2.FONT_HERSHEY_SIMPLEX, 2.1, (34, 40, 49), 5)
        cv2.putText(image, label, (120, 235), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (91, 101, 113), 3)
        cv2.putText(
            image,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            (120, height - 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (91, 101, 113),
            2,
        )
        return image
