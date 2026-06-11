import cv2
import numpy as np

from paperless_cam.quality import assess_readability


def _document_frame() -> np.ndarray:
    image = np.full((900, 1200, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (120, 80), (1080, 820), (255, 255, 255), -1)
    y = 160
    for row in range(18):
        cv2.putText(
            image,
            f"Paperless camera test line {row:02d} with readable document text",
            (170, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )
        y += 34
    return image


def test_readable_document_scores_green() -> None:
    report = assess_readability(_document_frame())

    assert report.readable is True
    assert report.score >= 58


def test_blurry_document_scores_red() -> None:
    blurred = cv2.GaussianBlur(_document_frame(), (51, 51), 0)
    report = assess_readability(blurred)

    assert report.readable is False
    assert report.message in {"Too blurry", "Text not clear", "Low contrast"}
