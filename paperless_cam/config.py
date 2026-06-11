from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    camera_index: int = int(os.getenv("PAPERLESS_CAM_CAMERA_INDEX", "0"))
    camera_width: int = int(os.getenv("PAPERLESS_CAM_CAMERA_WIDTH", "1920"))
    camera_height: int = int(os.getenv("PAPERLESS_CAM_CAMERA_HEIGHT", "1080"))
    camera_warmup_frames: int = int(os.getenv("PAPERLESS_CAM_CAMERA_WARMUP_FRAMES", "3"))
    output_dir: Path = Path(os.getenv("PAPERLESS_CAM_OUTPUT_DIR", "./scans")).resolve()
    paperless_url: str = os.getenv("PAPERLESS_URL", "").rstrip("/")
    paperless_token: str = os.getenv("PAPERLESS_TOKEN", "")
    paperless_inbox_tags: str = os.getenv("PAPERLESS_CAM_TAGS", "")
    upload_timeout_seconds: int = int(os.getenv("PAPERLESS_CAM_UPLOAD_TIMEOUT_SECONDS", "60"))
    debug_no_camera: bool = _bool("PAPERLESS_CAM_DEBUG_NO_CAMERA", False)


settings = Settings()
