from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import settings
from .scanner import Capture, Scanner


app = FastAPI(title="paperless-cam", version="0.1.0")
scanner = Scanner(settings)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/status")
def status() -> dict[str, object]:
    return {
        "paperless_configured": scanner.paperless.configured,
        "captures": len(scanner.list_captures()),
        "camera_index": settings.camera_index,
    }


@app.get("/api/preview.jpg")
def preview() -> Response:
    frame, _ = scanner.preview()
    return Response(
        content=scanner.camera.jpeg(frame),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/api/quality")
def quality() -> dict[str, object]:
    _, report = scanner.preview()
    return report


@app.get("/api/captures")
def captures() -> dict[str, object]:
    return {"captures": [_capture_dict(capture) for capture in scanner.list_captures()]}


@app.post("/api/captures")
def add_capture() -> dict[str, object]:
    capture = scanner.add_capture()
    return {"capture": _capture_dict(capture), "captures": len(scanner.list_captures())}


@app.get("/api/captures/{capture_id}.jpg")
def capture_image(capture_id: str) -> FileResponse:
    try:
        path = scanner.capture_path(capture_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Capture not found") from exc
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/api/captures")
def clear_captures() -> dict[str, object]:
    scanner.clear()
    return {"captures": 0}


@app.post("/api/upload")
def upload() -> JSONResponse:
    try:
        result = scanner.finish_and_upload()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(result)


def _capture_dict(capture: Capture) -> dict[str, object]:
    return {
        "id": capture.id,
        "created_at": capture.created_at,
        "quality": capture.quality,
        "thumbnail": f"/api/captures/{capture.id}.jpg",
    }
