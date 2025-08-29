#!/bin/bash
set -euo pipefail

# In the container, the app code is under /app (see Dockerfile WORKDIR)
APP_DIR="/app"
cd "$APP_DIR"

# Optional: activate venv if present (local dev). In container, deps are system-wide.
if [ -f "venv/bin/activate" ]; then
	echo "[Entrypoint] Activating venv..."
	. venv/bin/activate
fi

# Ensure Python can import the 'src' package
export PYTHONPATH="$APP_DIR"

echo "[Entrypoint] Env snapshot:"
echo "  FLASK_ENV=${FLASK_ENV:-}"
echo "  PORT=${PORT:-8080}"
echo "  REDIS_URL=${REDIS_URL:-}"
echo "  UPLOAD_FOLDER=${UPLOAD_FOLDER:-/tmp/uploads}"

# If REDIS_URL is set but CELERY_* are not, set them to REDIS_URL
if [ -n "${REDIS_URL:-}" ]; then
	if [ -z "${CELERY_BROKER_URL:-}" ]; then
		export CELERY_BROKER_URL="$REDIS_URL"
	fi
	if [ -z "${CELERY_RESULT_BACKEND:-}" ]; then
		export CELERY_RESULT_BACKEND="$REDIS_URL"
	fi
fi
echo "  CELERY_BROKER_URL=${CELERY_BROKER_URL:-}"
echo "  CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-}"


# Ensure upload folder exists (ephemeral)
mkdir -p "${UPLOAD_FOLDER:-/tmp/uploads}"

# If service account JSON is provided via env, materialize it to a file
if [ -n "${GCP_SERVICE_ACCOUNT_JSON:-}" ]; then
    mkdir -p /secrets
    echo "$GCP_SERVICE_ACCOUNT_JSON" > /secrets/gcs-credentials.json
    chmod 600 /secrets/gcs-credentials.json
    export GOOGLE_APPLICATION_CREDENTIALS="/secrets/gcs-credentials.json"
    echo "[Entrypoint] Wrote GCS credentials to /secrets/gcs-credentials.json"
else
    echo "[Entrypoint] No inline GCP credentials found (GCP_SERVICE_ACCOUNT_JSON unset)"
fi

PORT_TO_BIND=${PORT:-8080}
echo "[Entrypoint] Preparing to start processes on port ${PORT_TO_BIND}..."

# Decide whether Celery should run based on availability of a broker URL
SHOULD_RUN_CELERY=false
if [ -n "${CELERY_BROKER_URL:-}" ] || [ -n "${REDIS_URL:-}" ]; then
    SHOULD_RUN_CELERY=true
fi

if [ "$SHOULD_RUN_CELERY" = true ]; then
    echo "[Entrypoint] Starting Gunicorn in background..."
    gunicorn -b 0.0.0.0:${PORT_TO_BIND} \
        --timeout=1800 \
        --keep-alive=10 \
        --worker-class=sync \
        --workers=1 \
        --worker-connections=10 \
        --limit-request-line=8192 \
        --limit-request-field_size=16384 \
        --preload \
        src.main:app &

    sleep 2
    echo "[Entrypoint] Starting Celery worker (foreground)..."
    # Concurrency = 1 to match 1 shared CPU; memory cap ~1.5GB per child; recycle after 10 tasks
    exec celery -A src.celery_app.celery worker \
        --loglevel=INFO \
        --concurrency=1 \
        --max-memory-per-child=1500000 \
        --max-tasks-per-child=10 \
        --time-limit=600 \
        --soft-time-limit=300 \
        -Ofair \
        -Q fileops,default
else
    echo "[Entrypoint] No Celery broker configured. Running web server only."
    # Run Gunicorn in the foreground to keep the container alive
    exec gunicorn -b 0.0.0.0:${PORT_TO_BIND} \
        --timeout=1800 \
        --keep-alive=10 \
        --worker-class=sync \
        --workers=1 \
        --worker-connections=10 \
        --limit-request-line=8192 \
        --limit-request-field_size=16384 \
        --preload \
        src.main:app
fi
