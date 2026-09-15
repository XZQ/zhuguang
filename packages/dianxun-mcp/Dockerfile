FROM python:3.11-slim

ARG DIANXUN_BUILD_SHA=unknown
LABEL org.opencontainers.image.revision=$DIANXUN_BUILD_SHA
ENV DIANXUN_BUILD_SHA=$DIANXUN_BUILD_SHA

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    DIANXUN_STATE_DB=/var/lib/dianxun/runtime.db \
    DIANXUN_TRACE_DB=/var/lib/dianxun/trace.db \
    DIANXUN_OUTPUT_DIR=/var/lib/dianxun

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY config/ ./config/
COPY demo/state/seed.json ./demo/state/seed.json
COPY demo/state/scenarios/ ./demo/state/scenarios/
COPY schemas/ ./schemas/
COPY skills/ ./skills/

RUN python -m pip install --no-cache-dir ".[postgres]" \
    && addgroup --system --gid 10001 dianxun \
    && adduser --system --uid 10001 --ingroup dianxun --home /home/dianxun dianxun \
    && mkdir -p /var/lib/dianxun \
    && chown -R 10001:10001 /var/lib/dianxun /home/dianxun

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=3)" || exit 1

ENTRYPOINT ["dianxun-mcp"]
