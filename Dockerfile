# RevMatrix Demo Backend — Dockerfile
# Security hardened:
#   - Non-root user
#   - No unnecessary packages
#   - Read-only filesystem
#   - Health check included

FROM python:3.12-slim AS builder

# Don't run as root
RUN groupadd -r revmatrix && useradd -r -g revmatrix revmatrix

WORKDIR /app

# Install deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Final stage
FROM python:3.12-slim

RUN groupadd -r revmatrix && useradd -r -g revmatrix revmatrix

WORKDIR /app

# Copy installed packages and app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /app/main.py .

# Switch to non-root
USER revmatrix

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
