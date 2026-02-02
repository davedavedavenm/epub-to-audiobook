FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI for spawning conversion containers, and rsync+ssh for Audiobookshelf sync
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    rsync \
    openssh-client \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /data/uploads /data/audiobooks /data/previews

EXPOSE 8881

CMD ["gunicorn", "--bind", "0.0.0.0:8881", "--workers", "2", "--timeout", "300", "app:app"]
