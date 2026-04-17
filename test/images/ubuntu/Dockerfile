FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    libmagic1

# Install uv (binary from official image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency manifests first for better layer caching (paths relative to context = repo root)
COPY pyproject.toml uv.lock ./

# Sync dependencies (including dev tools like pytest) and install package
RUN uv sync --frozen --dev

# Ensure venv bin is on PATH so `ir` and `install-release` are available
ENV PATH="/root/bin:/app/.venv/bin:$PATH"
ENV NO_COLOR=1
ENV PYTHONIOENCODING="utf-8"
ENTRYPOINT ["sleep", "infinity"]
