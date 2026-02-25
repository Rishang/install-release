FROM ubuntu:25.10

RUN apt-get update && apt-get install -y \
    curl \
    libmagic1 sudo libmagic1 \
    python3 \
    python3-venv nginx \
    && rm -rf /var/lib/apt/lists/*

# Install uv (binary from official image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first for better layer caching (paths relative to context = repo root)
COPY pyproject.toml uv.lock ./

# Sync dependencies and install the package (CLI: ir, install-release)
RUN uv sync --frozen

# Ensure venv bin is on PATH so `ir` and `install-release` are available
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["sleep", "infinity"]
