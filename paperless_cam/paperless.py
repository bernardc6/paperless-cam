from __future__ import annotations

from pathlib import Path

import requests

from .config import Settings


class PaperlessClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.paperless_url and self.settings.paperless_token)

    def upload(self, document_path: Path) -> dict[str, object]:
        if not self.configured:
            return {
                "uploaded": False,
                "saved": str(document_path),
                "message": "Paperless-ngx is not configured, so the PDF was saved locally.",
            }

        endpoint = f"{self.settings.paperless_url}/api/documents/post_document/"
        headers = {"Authorization": f"Token {self.settings.paperless_token}"}
        data: dict[str, str] = {}
        if self.settings.paperless_inbox_tags:
            data["tags"] = self.settings.paperless_inbox_tags

        with document_path.open("rb") as handle:
            response = requests.post(
                endpoint,
                headers=headers,
                data=data,
                files={"document": (document_path.name, handle, "application/pdf")},
                timeout=self.settings.upload_timeout_seconds,
            )

        response.raise_for_status()
        return {
            "uploaded": True,
            "status_code": response.status_code,
            "paperless_response": response.text.strip(),
            "message": "Uploaded to Paperless-ngx.",
        }
