from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
import uuid

import cv2
import numpy as np
from PIL import Image

from .camera import Camera
from .config import Settings
from .paperless import PaperlessClient
from .quality import assess_readability


@dataclass
class Capture:
    id: str
    created_at: str
    path: Path
    quality: dict[str, object]


class Scanner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.camera = Camera(settings)
        self.paperless = PaperlessClient(settings)
        self._captures: list[Capture] = []
        self._lock = threading.Lock()
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    def preview(self) -> tuple[np.ndarray, dict[str, object]]:
        frame = self.camera.snapshot()
        return frame, assess_readability(frame).to_dict()

    def add_capture(self) -> Capture:
        frame, report = self.preview()
        capture_id = uuid.uuid4().hex
        path = self.settings.output_dir / f"{capture_id}.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        capture = Capture(
            id=capture_id,
            created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            path=path,
            quality=report,
        )
        with self._lock:
            self._captures.append(capture)
        return capture

    def list_captures(self) -> list[Capture]:
        with self._lock:
            return list(self._captures)

    def clear(self) -> None:
        with self._lock:
            captures = self._captures
            self._captures = []
        for capture in captures:
            capture.path.unlink(missing_ok=True)

    def capture_path(self, capture_id: str) -> Path:
        for capture in self.list_captures():
            if capture.id == capture_id:
                return capture.path
        raise KeyError(capture_id)

    def finish_and_upload(self) -> dict[str, object]:
        captures = self.list_captures()
        if not captures:
            captures = [self.add_capture()]

        pdf_path = self._build_pdf(captures)
        result = self.paperless.upload(pdf_path)
        self.clear()
        return {
            "pages": len(captures),
            "pdf": str(pdf_path),
            **result,
        }

    def _build_pdf(self, captures: list[Capture]) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        pdf_path = self.settings.output_dir / f"paperless-cam-{timestamp}.pdf"
        images: list[Image.Image] = []
        for capture in captures:
            image = Image.open(capture.path).convert("RGB")
            images.append(image)

        first, rest = images[0], images[1:]
        first.save(pdf_path, "PDF", resolution=300.0, save_all=True, append_images=rest)
        for image in images:
            image.close()
        return pdf_path
