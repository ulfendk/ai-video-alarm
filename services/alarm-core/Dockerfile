FROM python:3.11-slim

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

CMD ["python", "-m", "aivideoalarm.main"]
