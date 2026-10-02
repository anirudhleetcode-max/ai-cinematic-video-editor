# Media worker + API. FFmpeg from Debian (includes libass, libx264/265, xfade).
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/engine /app/services/engine
COPY packages /app/packages
RUN pip install --no-cache-dir -e /app/services/engine
ENV EDITOR_DATA_DIR=/data EDITOR_FONTS_DIR=/app/packages/fonts EDITOR_TEMPLATES_DIR=/app/packages/templates EDITOR_ENV=production
VOLUME ["/data"]
EXPOSE 8000
WORKDIR /app/services/engine
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "editor.api:app", "--host", "0.0.0.0", "--port", "8000"]
