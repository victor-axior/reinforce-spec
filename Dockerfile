# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /build

# ① Lock + metadata first for cache stability.
COPY pyproject.toml uv.lock README.md ./

# ② Create venv + export requirements (excluding CUDA packages).
RUN uv venv /opt/venv

RUN uv export --frozen --no-dev --no-emit-project --no-hashes \
      --no-emit-package torch \
      --no-emit-package triton \
      --no-emit-package nvidia-cublas-cu12 \
      --no-emit-package nvidia-cuda-cupti-cu12 \
      --no-emit-package nvidia-cuda-nvrtc-cu12 \
      --no-emit-package nvidia-cuda-runtime-cu12 \
      --no-emit-package nvidia-cudnn-cu12 \
      --no-emit-package nvidia-cufft-cu12 \
      --no-emit-package nvidia-cufile-cu12 \
      --no-emit-package nvidia-curand-cu12 \
      --no-emit-package nvidia-cusolver-cu12 \
      --no-emit-package nvidia-cusparse-cu12 \
      --no-emit-package nvidia-cusparselt-cu12 \
      --no-emit-package nvidia-nccl-cu12 \
      --no-emit-package nvidia-nvjitlink-cu12 \
      --no-emit-package nvidia-nvshmem-cu12 \
      --no-emit-package nvidia-nvtx-cu12 \
      --no-emit-package cuda-bindings \
      > requirements.txt

# ③ Install CPU-only torch (own layer → cached until torch version bumps).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python \
      --index-url https://download.pytorch.org/whl/cpu \
      "torch>=2.2.0"

# ④ Install remaining deps (cached across rebuilds via uv cache mount).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python -r requirements.txt

# Ensure runtime DB stack deps exist even before lockfile refresh.
RUN --mount=type=cache,target=/root/.cache/uv \
        uv pip install --python /opt/venv/bin/python \
            "sqlalchemy[asyncio]>=2.0.30" \
            "asyncpg>=0.29.0" \
            "python-dotenv>=1.0.1"

# ⑤ Copy source, install just the project (deps cached → fast).
COPY reinforce_spec/ reinforce_spec/
RUN uv pip install --python /opt/venv/bin/python --no-deps .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Axior Engineering"
LABEL description="ReinforceSpec — RL-optimized enterprise spec generator"
LABEL org.opencontainers.image.title="reinforce-spec" \
      org.opencontainers.image.description="RL-optimized enterprise spec evaluator" \
      org.opencontainers.image.source="https://github.com/axior/reinforce-spec"

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 10001 -d /app -s /usr/sbin/nologin appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application code
COPY --chown=appuser:appuser reinforce_spec/ reinforce_spec/
COPY --chown=appuser:appuser data/policies/ /app/bootstrap/policies/
COPY --chown=appuser:appuser scripts/docker_entrypoint.sh /app/docker_entrypoint.sh

# Create data directory
RUN mkdir -p /app/data/policies /app/data/db && \
    chown -R appuser:appuser /app/data && \
    sed -i 's/\r$//' /app/docker_entrypoint.sh && \
    chmod 755 /app/docker_entrypoint.sh

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health', timeout=3)" || exit 1

EXPOSE 8000

ENTRYPOINT ["/app/docker_entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
