![Paperless-Cam Logo](paperless-cam-logo.jpeg)

# paperless-cam

paperless-cam turns a USB webcam into a tiny web-based document scanner for
[Paperless-ngx](https://docs.paperless-ngx.com/). Put a document under the
camera, open the web UI from any device on your network, add pages, then upload
the finished PDF directly into Paperless-ngx.

The UI is deliberately simple:

- live camera preview
- **Add another photo**
- **Done & Upload**
- **New**
- automatic readability checking with a green or red scanner border

## How it works

paperless-cam runs on the machine that has the USB webcam attached. The browser
UI can be opened from a phone, tablet, or laptop on the same network.

The backend captures frames from `/dev/video0` using OpenCV, estimates whether
the page is readable using local computer vision signals, combines captured
pages into a PDF, and posts that PDF to the Paperless-ngx consume API.

No image data is sent to any cloud service.

## Quick start

```bash
git clone https://github.com/bernardc6/paperless-cam.git
cd paperless-cam
cp .env.example .env
```

Edit `.env`:

```bash
PAPERLESS_URL=http://your-paperless-host:8000
PAPERLESS_TOKEN=your-paperless-api-token
PAPERLESS_CAM_CAMERA_INDEX=0
```

Run with Docker:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

From another device on your LAN, replace `localhost` with the scanner machine's
IP address.

## Run without Docker

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn paperless_cam.server:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PAPERLESS_URL` | empty | Base URL for Paperless-ngx, for example `http://paperless-ngx:8000`. |
| `PAPERLESS_TOKEN` | empty | Paperless-ngx API token. |
| `PAPERLESS_CAM_CAMERA_INDEX` | `0` | OpenCV camera index. Use `1`, `2`, etc. for other webcams. |
| `PAPERLESS_CAM_CAMERA_WIDTH` | `1920` | Requested camera width. |
| `PAPERLESS_CAM_CAMERA_HEIGHT` | `1080` | Requested camera height. |
| `PAPERLESS_CAM_OUTPUT_DIR` | `./scans` | Local working directory for captures and PDFs. |
| `PAPERLESS_CAM_TAGS` | empty | Optional tag IDs/names to send with uploads. |
| `PAPERLESS_CAM_DEBUG_NO_CAMERA` | `false` | Show a generated preview image for UI testing without a webcam. |

If `PAPERLESS_URL` or `PAPERLESS_TOKEN` is missing, **Done & Upload** still
creates the PDF and saves it locally in `PAPERLESS_CAM_OUTPUT_DIR`.

## Readability checker

The green/red border is an estimate, not OCR. It checks:

- focus sharpness
- contrast
- exposure
- text-like fine detail

This is intended to catch the common failure modes: camera out of focus, page
too dark, glare, or the document being too far away. It is intentionally local
and fast so it can run continuously while the preview updates.

## USB webcam notes

On Linux, webcams usually appear as `/dev/video0`, `/dev/video1`, etc.

Check connected cameras:

```bash
ls /dev/video*
```

If Docker cannot access the camera, confirm the compose file maps the right
device:

```yaml
devices:
  - "/dev/video0:/dev/video0"
```

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Run the UI without a real camera:

```bash
PAPERLESS_CAM_DEBUG_NO_CAMERA=true uvicorn paperless_cam.server:app --reload
```

## Project status

This is an early open-source MVP. The intended direction is a reliable
"appliance-like" scanner for Paperless-ngx: minimal UI, local processing, and as
little manual document handling as possible.

Planned improvements:

- document edge detection and auto-cropping
- camera calibration guidance
- optional auto-capture when the page is stable and readable
- Paperless-ngx metadata presets
- Raspberry Pi friendly install guide

## License

MIT
