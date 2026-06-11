FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY paperless_cam ./paperless_cam
COPY paperless-cam-logo.jpeg ./paperless-cam-logo.jpeg

RUN mkdir -p /data/scans
ENV PAPERLESS_CAM_OUTPUT_DIR=/data/scans
EXPOSE 8000

CMD ["uvicorn", "paperless_cam.server:app", "--host", "0.0.0.0", "--port", "8000"]
