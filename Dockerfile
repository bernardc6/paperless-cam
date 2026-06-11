FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY paperless_cam/static ./paperless_cam/static
COPY paperless-cam-logo.jpeg ./paperless-cam-logo.jpeg

RUN mkdir -p /data/stage /consume
ENV PAPERLESS_CAM_STAGE_DIR=/data/stage \
    PAPERLESS_CAM_CONSUME_DIR=/consume
EXPOSE 5000

CMD ["python", "app.py"]
