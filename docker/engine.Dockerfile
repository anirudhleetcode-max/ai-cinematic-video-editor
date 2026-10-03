# Cutroom engine image. Two targets from one build:
#   docker build -f docker/engine.Dockerfile --target api    -t cutroom-api .
#   docker build -f docker/engine.Dockerfile --target worker -t cutroom-worker .
# Base images come from mirror.gcr.io (Docker Hub's library mirror); override BASE for another registry.
ARG BASE=mirror.gcr.io/library/python:3.11-slim-bookworm

FROM ${BASE} AS engine
# Debian's FFmpeg includes libx264/libx265, libzimg (zscale), libvidstab, libass and xfade.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY services/engine/pyproject.toml /app/services/engine/pyproject.toml
COPY services/engine/editor /app/services/engine/editor
RUN pip install "/app/services/engine[vad]" \
 && python -c "import editor, cv2, librosa, onnxruntime"
COPY packages /app/packages
COPY scripts/download_models.py /app/scripts/download_models.py
# Optional free ONNX models (YuNet, NanoDet-Plus, Silero VAD; ~6 MB). Without them the classic OpenCV / DSP fallbacks
# run, and /health reports which is active. A failed download does not fail the build.
ARG WITH_MODELS=1
RUN if [ "$WITH_MODELS" = "1" ]; then python /app/scripts/download_models.py --dest /app/models || echo "WARNING: model download failed - fallbacks will be used"; fi
RUN useradd --system --uid 10001 --home /data cutroom && mkdir -p /data && chown cutroom /data
ENV EDITOR_MODELS_DIR=/app/models EDITOR_DATA_DIR=/data EDITOR_FONTS_DIR=/app/packages/fonts EDITOR_TEMPLATES_DIR=/app/packages/templates \
    EDITOR_ENV=production EDITOR_AUTH=token
VOLUME ["/data"]
USER cutroom
WORKDIR /app/services/engine
ENTRYPOINT ["/usr/bin/tini", "--"]

FROM engine AS api
ENV EDITOR_ROLE=api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health/live',timeout=5)"
CMD ["python", "-m", "uvicorn", "editor.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]

FROM engine AS worker
ENV EDITOR_ROLE=worker
# The worker touches /data/.worker-heartbeat every 5 s while its threads are alive.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s CMD python -c "import os,time,sys;p='/data/.worker-heartbeat';sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p)<30 else 1)"
CMD ["python", "-m", "editor.worker"]
