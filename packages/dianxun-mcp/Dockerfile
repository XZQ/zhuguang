FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    DIANXUN_STATE_DB=/var/lib/dianxun/runtime.db

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY config/ ./config/
COPY demo/state/seed.json ./demo/state/seed.json
COPY demo/state/scenarios/ ./demo/state/scenarios/
COPY schemas/ ./schemas/

RUN python -m pip install --no-cache-dir ".[postgres]" \
    && addgroup --system --gid 10001 dianxun \
    && adduser --system --uid 10001 --ingroup dianxun --home /home/dianxun dianxun \
    && mkdir -p /var/lib/dianxun \
    && chown -R 10001:10001 /var/lib/dianxun /home/dianxun

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1

ENTRYPOINT ["dianxun-mcp"]
