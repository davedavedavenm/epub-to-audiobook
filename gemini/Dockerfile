FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

RUN useradd -r -m -s /bin/false appuser \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

EXPOSE 8014

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8014/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8014"]
