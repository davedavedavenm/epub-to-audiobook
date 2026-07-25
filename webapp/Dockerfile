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

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    rsync \
    openssh-client \
    calibre \
    ffmpeg \
    procps \
    && rm -rf /var/lib/apt/lists/*
# procps provides pgrep, used by the worker healthcheck (test: pgrep -f worker.py).
# Without it the check always failed and the worker showed "unhealthy" though fine.

# Debian trixie's `docker.io` package ships only the DAEMON (dockerd,
# docker-proxy, docker-init) — NOT the `docker` client this app shells out to,
# and trixie has no docker-cli package. So the image had dpkg saying docker.io
# was installed while `which docker` failed, and every `docker run` path died
# with "No such file or directory: 'docker'" (Edge previews, ASR verify).
# Fetch the official static CLIENT only: DOCKER_HOST already points at the
# socket proxy, so no daemon is needed (and skipping it shrinks the image).
ARG DOCKER_CLI_VERSION=27.3.1
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" -o /tmp/d.tgz \
    && tar -xzf /tmp/d.tgz -C /tmp docker/docker \
    && install -m 0755 /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/d.tgz /tmp/docker \
    && docker --version

# Install Python dependencies
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY webapp/ .

# Copy conversion script
COPY scripts/convert_book.py ./scripts/convert_book.py

RUN mkdir -p /data/uploads /data/audiobooks /data/previews /data/logs

RUN useradd -r -m -s /bin/bash appuser \
    && mkdir -p /home/appuser/.ssh /home/appuser/.config/vastai \
    && chmod 700 /home/appuser/.ssh \
    && chown -R appuser:appuser /app /data /home/appuser

COPY webapp/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV SSH_KEY_PATH=/home/appuser/.ssh/id_ed25519
ENV VASTAI_API_KEY_FILE=/home/appuser/.config/vastai/vast_api_key
USER appuser

EXPOSE 8881

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8881", "--workers", "1", "--timeout", "300", "app:app"]
