"""
Flask web server for the AI Code Reviewer.

Exposes a small JSON API consumed by the single-page front-end. All heavy
lifting is delegated to the existing core modules (file handling, Groq client,
report generation) so the business logic stays in one place.

Two modes, selected by the ENVIRONMENT variable:

  * development (default) — full features, no rate limiting, file uploads on.
  * production            — public demo hardening:
        - multi-layer rate limiting (per real client IP + global daily cap),
        - snippet-only input (file uploads disabled),
        - strict input-size limit,
        - the report is built in memory and never written to disk.

The Groq API key lives only in the server environment (GROQ_API_KEY); it is
never sent to or stored in the front-end bundle. The SPA and the API are served
same-origin, so a single Cloudflare Tunnel route is enough.

Run (development):
    python -m webapp.server

Run (production):
    gunicorn "webapp.server:app" --workers 1 --threads 8 \
        --bind 127.0.0.1:8082 --timeout 120
    # NOTE: a single worker keeps the in-memory rate-limit counters
    # authoritative (no shared Redis needed for a low-traffic demo).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.utils.config import Config
from src.utils.logger import setup_logger
from src.analyzer.file_reader import LocalFileReader
from src.ai_engine.llm_client import GroqClient
from src.reports.generator import ReportGenerator

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Environment / tunables (overridable via env vars)
# ---------------------------------------------------------------------------
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Rate-limit profile (defaults = "Balanced"). All per the REAL client IP.
RL_PER_MIN = _int_env("RL_PER_MIN", 8)        # analyses / minute / IP
RL_PER_DAY = _int_env("RL_PER_DAY", 40)       # analyses / day / IP
RL_GLOBAL_PER_DAY = _int_env("RL_GLOBAL_PER_DAY", 300)  # analyses / day (all IPs)

# Input-size cap for a single analysis (characters of source code).
MAX_CODE_CHARS = _int_env("MAX_CODE_CHARS", 50 * 1024)  # 50 KB

# Hard request-body cap. Tight in production (snippet only); roomy in dev.
MAX_CONTENT_LENGTH = _int_env(
    "MAX_CONTENT_LENGTH", (256 * 1024) if IS_PRODUCTION else (5 * 1024 * 1024)
)

SUPPORTED_EXTENSIONS = LocalFileReader.SUPPORTED_EXTENSIONS
MODEL_NAME = "llama-3.3-70b-versatile"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def real_client_ip() -> str:
    """
    Resolve the real visitor IP. Behind Cloudflare Tunnel, ``remote_addr`` is
    Cloudflare's address, so the per-IP limit must key off CF-Connecting-IP
    (falling back to X-Forwarded-For, then the socket address).
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address()


limiter = Limiter(key_func=real_client_ip, app=app, default_limits=[])


def _limits_off() -> bool:
    """Rate limits apply only in the public production demo."""
    return not IS_PRODUCTION


def _api_key_available() -> bool:
    return bool(Config.GROQ_API_KEY or os.getenv("GROQ_API_KEY"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Render the single-page application."""
    return render_template(
        "index.html",
        api_key_set=_api_key_available(),
        extensions=sorted(SUPPORTED_EXTENSIONS),
        public_demo=IS_PRODUCTION,
        max_code_kb=MAX_CODE_CHARS // 1024,
        model=MODEL_NAME,
    )


@app.get("/healthz")
def healthz():
    """Liveness probe for the container healthcheck."""
    return jsonify(status="ok"), 200


@app.get("/api/status")
def status():
    """Lightweight status endpoint used by the front-end on load."""
    return jsonify(
        api_key_set=_api_key_available(),
        extensions=sorted(SUPPORTED_EXTENSIONS),
        model=MODEL_NAME,
        public_demo=IS_PRODUCTION,
        max_code_kb=MAX_CODE_CHARS // 1024,
    )


@app.post("/api/analyze")
@limiter.limit(f"{RL_PER_MIN} per minute", exempt_when=_limits_off)
@limiter.limit(f"{RL_PER_DAY} per day", exempt_when=_limits_off)
@limiter.limit(
    f"{RL_GLOBAL_PER_DAY} per day",
    key_func=lambda: "global",
    exempt_when=_limits_off,
)
def analyze():
    """
    Analyze a pasted snippet and/or uploaded files.

    In production only the pasted snippet is accepted (file uploads disabled),
    which caps the request at a single Groq call.
    """
    # In the public demo the client must never influence which key is used:
    # always fall back to the server-side key and ignore any submitted key.
    api_key = "" if IS_PRODUCTION else (request.form.get("api_key") or "").strip()
    effective_key = api_key or os.getenv("GROQ_API_KEY") or Config.GROQ_API_KEY
    if not effective_key:
        return jsonify(error="No Groq API key configured. Add one to analyze."), 400

    items: Dict[str, str] = {}

    # File uploads are accepted only outside the public demo.
    if not IS_PRODUCTION:
        for storage in request.files.getlist("files"):
            if not storage or not storage.filename:
                continue
            name = Path(storage.filename).name
            if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                content = storage.read().decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read upload %s: %s", name, exc)
                continue
            if len(content) > MAX_CODE_CHARS:
                return (
                    jsonify(error=f"'{name}' exceeds the {MAX_CODE_CHARS // 1024} KB limit."),
                    413,
                )
            items[name] = content

    pasted = (request.form.get("code") or "").strip()
    if pasted:
        if len(pasted) > MAX_CODE_CHARS:
            return (
                jsonify(
                    error=f"Snippet too large. The limit is {MAX_CODE_CHARS // 1024} KB "
                    f"of code per analysis."
                ),
                413,
            )
        snippet_name = Path((request.form.get("filename") or "snippet.py")).name
        items[snippet_name] = pasted

    if not items:
        return jsonify(error="No source provided. Paste some code to review."), 400

    try:
        client = GroqClient(api_key=api_key or None)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialize Groq client: %s", exc)
        return jsonify(error=f"Could not initialize AI client: {exc}"), 500

    reviews: Dict[str, str] = {}
    for name, content in items.items():
        logger.info("Analyzing %s via web request...", name)
        reviews[name] = client.analyze_code(name, content)

    # Build the report in memory; the browser turns it into a download Blob.
    report_md = ReportGenerator.build_markdown_report(reviews)
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"code_review_report_{timestamp}.md"

    return jsonify(
        reviews=reviews,
        report_markdown=report_md,
        report_filename=report_filename,
    )


# ---------------------------------------------------------------------------
# JSON error handlers (keep the API responses consistent)
# ---------------------------------------------------------------------------
@app.errorhandler(429)
def too_many_requests(_e):
    return (
        jsonify(
            error="Rate limit reached. This is a shared public demo — "
            "please wait a moment and try again."
        ),
        429,
    )


@app.errorhandler(413)
def payload_too_large(_e):
    return jsonify(error="Request too large. Reduce the amount of code and retry."), 413


def main() -> None:
    port = int(os.getenv("PORT", "5000"))
    debug = (not IS_PRODUCTION) and os.getenv("FLASK_DEBUG", "0") == "1"
    logger.info(
        "Starting AI Code Reviewer (env=%s) on http://127.0.0.1:%s", ENVIRONMENT, port
    )
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
