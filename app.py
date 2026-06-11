from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import threading
import time
import uuid

from flask import Flask, Response, jsonify, send_file
import cv2
import img2pdf
import numpy as np


@dataclass(frozen=True)
class Settings:
    camera_index: int = int(os.getenv("PAPERLESS_CAM_CAMERA_INDEX", "0"))
    camera_width: int = int(os.getenv("PAPERLESS_CAM_CAMERA_WIDTH", "1920"))
    camera_height: int = int(os.getenv("PAPERLESS_CAM_CAMERA_HEIGHT", "1080"))
    preview_width: int = int(os.getenv("PAPERLESS_CAM_PREVIEW_WIDTH", "960"))
    blur_threshold: float = float(os.getenv("PAPERLESS_CAM_BLUR_THRESHOLD", "100.0"))
    min_contour_area: float = float(os.getenv("PAPERLESS_CAM_MIN_CONTOUR_AREA", "50000"))
    stage_dir: Path = Path(os.getenv("PAPERLESS_CAM_STAGE_DIR", "/tmp/paperless-cam")).resolve()
    consume_dir: Path = Path(
        os.getenv(
            "PAPERLESS_CAM_CONSUME_DIR",
            os.getenv("PAPERLESS_CONSUME_DIR", "/consume"),
        )
    ).resolve()
    debug_no_camera: bool = os.getenv("PAPERLESS_CAM_DEBUG_NO_CAMERA", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass
class Page:
    id: str
    path: Path
    readable: bool
    blur_score: float
    document_found: bool


settings = Settings()
app = Flask(__name__, static_folder="paperless_cam/static", static_url_path="/static")

camera_lock = threading.Lock()
state_lock = threading.Lock()
camera: cv2.VideoCapture | None = None
pages: list[Page] = []
pending_page: Page | None = None


@app.get("/")
def index() -> Response:
    return send_file(Path(app.static_folder or "") / "index.html")


@app.get("/video_feed")
def video_feed() -> Response:
    return Response(
        mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/status")
def status() -> Response:
    with state_lock:
        payload = {
            "pages": [page_payload(page) for page in pages],
            "pending": page_payload(pending_page) if pending_page else None,
            "consume_dir": str(settings.consume_dir),
        }
    return jsonify(payload)


@app.get("/quality")
def quality() -> Response:
    frame = read_frame()
    report = assess_frame(frame)
    return jsonify(report)


@app.post("/capture")
def capture() -> Response:
    global pending_page

    frame = read_frame(high_resolution=True)
    processed, report = process_document(frame)
    page = write_page(processed, report)

    with state_lock:
        if pending_page:
            pending_page.path.unlink(missing_ok=True)
        pending_page = page

    return jsonify({"pending": page_payload(page)})


@app.post("/keep")
def keep() -> Response:
    global pending_page

    with state_lock:
        if pending_page is None:
            return jsonify({"error": "No pending capture"}), 400
        pages.append(pending_page)
        pending_page = None
        payload = [page_payload(page) for page in pages]

    return jsonify({"pages": payload})


@app.post("/discard")
def discard() -> Response:
    global pending_page

    with state_lock:
        if pending_page:
            pending_page.path.unlink(missing_ok=True)
        pending_page = None

    return jsonify({"pending": None})


@app.post("/finalize")
def finalize() -> Response:
    global pending_page

    with state_lock:
        if pending_page is not None:
            pages.append(pending_page)
            pending_page = None
        selected = list(pages)

    if not selected:
        frame = read_frame(high_resolution=True)
        processed, report = process_document(frame)
        page = write_page(processed, report)
        with state_lock:
            pages.append(page)
            selected = list(pages)

    settings.consume_dir.mkdir(parents=True, exist_ok=True)
    pdf_name = f"paperless-cam-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.pdf"
    pdf_path = settings.consume_dir / pdf_name
    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(img2pdf.convert([str(page.path) for page in selected]))

    clear_pages(remove_pending=True)
    return jsonify(
        {
            "message": f"Saved {len(selected)} page PDF to Paperless consume directory.",
            "pages": len(selected),
            "pdf": str(pdf_path),
        }
    )


@app.post("/new")
def new_document() -> Response:
    clear_pages(remove_pending=True)
    return jsonify({"pages": []})


@app.get("/page/<page_id>.jpg")
def page_image(page_id: str) -> Response:
    with state_lock:
        matches = [page for page in [*pages, pending_page] if page and page.id == page_id]
    if not matches:
        return jsonify({"error": "Page not found"}), 404
    return send_file(matches[0].path, mimetype="image/jpeg")


def mjpeg_stream():
    while True:
        frame = read_frame()
        report = assess_frame(frame)
        preview = draw_preview(frame, report)
        ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
        time.sleep(0.12)


def read_frame(high_resolution: bool = False) -> np.ndarray:
    if settings.debug_no_camera:
        return placeholder_frame()

    with camera_lock:
        capture_device = ensure_camera()
        if capture_device is None:
            return placeholder_frame("No USB camera")

        if high_resolution:
            capture_device.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
            capture_device.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)

        frame = None
        for _ in range(3):
            ok, candidate = capture_device.read()
            if ok and candidate is not None:
                frame = candidate

    if frame is None:
        return placeholder_frame("Camera read failed")
    return frame


def ensure_camera() -> cv2.VideoCapture | None:
    global camera

    if camera is not None and camera.isOpened():
        return camera

    camera = cv2.VideoCapture(settings.camera_index)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
    return camera if camera.isOpened() else None


def process_document(frame: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    report = assess_frame(frame)
    document, found = extract_document(frame)
    output = optimize_black_and_white(document)
    report["document_found"] = found
    report["readable"] = bool(report["readable"] and found)
    if not found:
        report["message"] = "Document edges not found"
    return output, report


def assess_frame(frame: np.ndarray) -> dict[str, object]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    focus = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    readable = focus >= settings.blur_threshold
    return {
        "readable": readable,
        "blur_score": round(focus, 2),
        "threshold": settings.blur_threshold,
        "message": "Readable" if readable else "Too blurry",
    }


def extract_document(frame: np.ndarray) -> tuple[np.ndarray, bool]:
    ratio = frame.shape[0] / 700.0
    resized = cv2.resize(frame, (int(frame.shape[1] / ratio), 700))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = sorted(contours, key=cv2.contourArea, reverse=True)
    for contour in candidates[:8]:
        area = cv2.contourArea(contour) * ratio * ratio
        if area < settings.min_contour_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            points = approx.reshape(4, 2).astype("float32") * ratio
            return four_point_transform(frame, points), True

    return frame, False


def four_point_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    rect = order_points(points)
    top_left, top_right, bottom_right, bottom_left = rect

    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    max_height = int(max(height_a, height_b))

    target = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, target)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def optimize_black_and_white(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        12,
    )


def draw_preview(frame: np.ndarray, report: dict[str, object]) -> np.ndarray:
    scale = min(settings.preview_width / frame.shape[1], 1.0)
    preview = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)))
    color = (31, 157, 85) if report["readable"] else (214, 69, 69)
    cv2.rectangle(preview, (10, 10), (preview.shape[1] - 10, preview.shape[0] - 10), color, 5)
    cv2.putText(
        preview,
        f'{report["message"]} {report["blur_score"]}',
        (24, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
        cv2.LINE_AA,
    )
    return preview


def write_page(image: np.ndarray, report: dict[str, object]) -> Page:
    settings.stage_dir.mkdir(parents=True, exist_ok=True)
    page_id = uuid.uuid4().hex
    path = settings.stage_dir / f"{page_id}.jpg"
    cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return Page(
        id=page_id,
        path=path,
        readable=bool(report["readable"]),
        blur_score=float(report["blur_score"]),
        document_found=bool(report.get("document_found", False)),
    )


def page_payload(page: Page | None) -> dict[str, object] | None:
    if page is None:
        return None
    return {
        "id": page.id,
        "image": f"/page/{page.id}.jpg",
        "readable": page.readable,
        "blur_score": round(page.blur_score, 2),
        "document_found": page.document_found,
    }


def clear_pages(remove_pending: bool = False) -> None:
    global pending_page

    with state_lock:
        selected = list(pages)
        pages.clear()
        if remove_pending and pending_page:
            selected.append(pending_page)
            pending_page = None

    for page in selected:
        page.path.unlink(missing_ok=True)


def placeholder_frame(label: str = "Debug camera") -> np.ndarray:
    width = settings.camera_width
    height = settings.camera_height
    image = np.full((height, width, 3), 246, dtype=np.uint8)
    cv2.rectangle(image, (180, 100), (width - 180, height - 100), (222, 222, 222), 5)
    cv2.putText(image, "paperless-cam", (230, 220), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (36, 44, 54), 5)
    cv2.putText(image, label, (230, 310), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (80, 90, 105), 3)
    cv2.putText(image, "Place a page inside the marked area", (230, 410), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (80, 90, 105), 3)
    return image


if __name__ == "__main__":
    if settings.stage_dir.exists():
        shutil.rmtree(settings.stage_dir)
    settings.stage_dir.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), threaded=True)
