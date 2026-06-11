from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class QualityReport:
    readable: bool
    score: int
    focus: float
    contrast: float
    brightness: float
    detail: float
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "readable": self.readable,
            "score": self.score,
            "focus": round(self.focus, 2),
            "contrast": round(self.contrast, 2),
            "brightness": round(self.brightness, 2),
            "detail": round(self.detail, 4),
            "message": self.message,
        }


def assess_readability(frame: np.ndarray) -> QualityReport:
    """Estimate whether a document frame is sharp enough to read.

    This intentionally uses local computer-vision signals instead of cloud OCR:
    focus, contrast, exposure, and fine text-like detail. It is fast enough to
    run on every preview poll and works without sending page images anywhere.
    """
    if frame.size == 0:
        return QualityReport(False, 0, 0, 0, 0, 0, "No camera image")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    gray = _central_crop(gray)

    focus = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())
    detail = _text_like_detail(gray)

    focus_score = min(focus / 450.0, 1.0)
    contrast_score = min(contrast / 55.0, 1.0)
    exposure_score = 1.0 - min(abs(brightness - 150.0) / 120.0, 1.0)
    detail_score = min(detail / 0.075, 1.0)

    combined = (
        focus_score * 0.48
        + contrast_score * 0.22
        + exposure_score * 0.15
        + detail_score * 0.15
    )
    score = int(round(combined * 100))

    readable = focus >= 120 and contrast >= 22 and 55 <= brightness <= 235 and detail >= 0.008 and score >= 58
    if readable:
        message = "Readable"
    elif focus < 120:
        message = "Too blurry"
    elif contrast < 22:
        message = "Low contrast"
    elif brightness < 55:
        message = "Too dark"
    elif brightness > 235:
        message = "Too bright"
    else:
        message = "Text not clear"

    return QualityReport(readable, score, focus, contrast, brightness, detail, message)


def _central_crop(gray: np.ndarray) -> np.ndarray:
    height, width = gray.shape[:2]
    y0 = int(height * 0.08)
    y1 = int(height * 0.92)
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)
    return gray[y0:y1, x0:x1]


def _text_like_detail(gray: np.ndarray) -> float:
    resized = cv2.resize(gray, (900, max(1, int(gray.shape[0] * 900 / gray.shape[1]))))
    blurred = cv2.GaussianBlur(resized, (3, 3), 0)
    edges = cv2.Canny(blurred, 60, 160)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)

    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )
    components, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    textish = 0
    for idx in range(1, components):
        x, y, width, height, area = stats[idx]
        if 3 <= width <= 90 and 5 <= height <= 70 and 8 <= area <= 1600:
            aspect = width / max(height, 1)
            if 0.08 <= aspect <= 12:
                textish += 1

    component_density = min(textish / 450.0, 0.12)
    return edge_density * 0.7 + component_density * 0.3
