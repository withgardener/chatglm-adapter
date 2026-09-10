FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG BUILD_GIT_SHA=unknown
ENV BUILD_GIT_SHA=${BUILD_GIT_SHA}

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /data /run/secrets && \
    useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app /data /run/secrets

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "chatglm_adapter.main:app", "--host", "0.0.0.0", "--port", "8000"]
