FROM fedora:41

RUN dnf install -y \
    curl \
    file \
    file-libs \
    findutils \
    ncurses \
    python3 \
    && dnf clean all

# Install uv (binary from official image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first for better layer caching (paths relative to context = repo root)
COPY pyproject.toml uv.lock ./

# Sync dependencies and install the package (CLI: ir, install-release)
RUN uv sync --frozen

# Ensure venv bin is on PATH so `ir` and `install-release` are available
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["ir"]
