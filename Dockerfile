FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        ffmpeg \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN pip install --no-cache-dir .

RUN groupadd --gid 10001 worker \
    && useradd --uid 10001 --gid worker --no-create-home --home-dir /tmp/keyway worker \
    && mkdir -p /models /media /output /tmp/keyway \
    && chown -R worker:worker /models /output /tmp/keyway

# Application path defaults match the declared volumes so a bare `docker run`
# never writes models or artifacts into the temp mount or the container layer.
ENV HOME=/tmp/keyway \
    HF_HOME=/models \
    TMPDIR=/tmp/keyway \
    MODEL_CACHE_DIR=/models \
    TEMP_DIR=/tmp/keyway \
    OUTPUT_DIR=/output

USER worker
VOLUME ["/models", "/output", "/tmp/keyway"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
