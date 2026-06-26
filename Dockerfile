# syntax=docker/dockerfile:1
#
# AI Code Reviewer — web demo image.
# Builds natively on the Raspberry Pi 5 (ARM64). Slim Python base, no Tk/GUI
# deps, runs as a non-root user, served by gunicorn.

FROM python:3.12-slim

# Keep Python lean and unbuffered for clean container logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8082

WORKDIR /app

# Install web-only dependencies first to leverage Docker layer caching.
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copy the application code (see .dockerignore for what is excluded).
COPY src ./src
COPY webapp ./webapp

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8082

# Liveness probe hitting the app's /healthz endpoint (no curl in slim image).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
url='http://127.0.0.1:%s/healthz' % os.getenv('PORT','8082'); \
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status==200 else 1)"

# One worker keeps the in-memory rate-limit counters authoritative; threads give
# light concurrency. Timeout is generous because a Groq call can take a while.
CMD ["sh", "-c", "gunicorn 'webapp.server:app' --workers 1 --threads 8 --bind 0.0.0.0:${PORT:-8082} --timeout 120 --access-logfile - --error-logfile -"]
