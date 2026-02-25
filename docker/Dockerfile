# Dockerfile for Lex.uz Search Proxy API

FROM python:3.13-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install dependencies (lxml has pre-built wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser main.py .

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 19780

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:19780/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "19780", "--workers", "2", "--log-level", "info"]
