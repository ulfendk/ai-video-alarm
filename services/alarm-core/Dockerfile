FROM python:3.11-slim

# OCI labels: GHCR links the published package back to this repo using
# org.opencontainers.image.source, and shows the description on the
# package page.
LABEL org.opencontainers.image.source="https://github.com/ulfendk/ai-video-alarm"
LABEL org.opencontainers.image.description="alarm-core: Frigate verification + alarm-orchestration layer"

WORKDIR /app

# System deps for Pillow/onnxruntime; kept minimal for the CPU-only base
# image. Swap the base image for an NVIDIA CUDA image (and
# onnxruntime-gpu in pyproject.toml) once GPU passthrough is set up on the
# host — see docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8090

# No curl/wget in the slim base — a one-line urllib check avoids adding a
# package just for this. Surfaces container health in `docker ps` and in
# Portainer's container list/dashboard.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8090/health', timeout=3)" || exit 1

CMD ["python", "-m", "aivideoalarm.main"]
