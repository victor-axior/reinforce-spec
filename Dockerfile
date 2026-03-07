# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching)
COPY pyproject.toml README.md ./
COPY reinforce_spec/ reinforce_spec/

# Create venv and install dependencies
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache-dir .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Axior Engineering"
LABEL description="ReinforceSpec — RL-optimized enterprise spec generator"

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY reinforce_spec/ reinforce_spec/
COPY data/policies/ /app/bootstrap/policies/
COPY scripts/docker_entrypoint.sh /app/docker_entrypoint.sh
COPY pyproject.toml README.md ./

# Create data directory
RUN mkdir -p /app/data/policies /app/data/db && \
    chmod +x /app/docker_entrypoint.sh && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')"

EXPOSE 8000

ENTRYPOINT ["/app/docker_entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
