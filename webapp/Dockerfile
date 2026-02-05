FROM python:3.11-slim

WORKDIR /app
ARG APP_VERSION=dev
ARG APP_GIT_SHA=unknown
ARG APP_BUILD_TIME=unknown
LABEL org.opencontainers.image.version=$APP_VERSION
LABEL org.opencontainers.image.revision=$APP_GIT_SHA
LABEL org.opencontainers.image.created=$APP_BUILD_TIME
ENV APP_VERSION=$APP_VERSION
ENV APP_GIT_SHA=$APP_GIT_SHA
ENV APP_BUILD_TIME=$APP_BUILD_TIME

# Install Docker CLI for spawning conversion containers, rsync+ssh for Audiobookshelf sync,
# and Calibre for ebook format conversion (mobi, azw3, fb2, docx, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    rsync \
    openssh-client \
    calibre \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /data/uploads /data/audiobooks /data/previews /data/logs

EXPOSE 8881

CMD ["gunicorn", "--bind", "0.0.0.0:8881", "--workers", "1", "--timeout", "300", "app:app"]
