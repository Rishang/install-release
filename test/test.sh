#!/bin/bash
set -e
cd "$(dirname "$0")/.."

case $1 in
  "ubuntu")
    docker build -t install-release-ubuntu:latest -f test/ubuntu/Dockerfile .
    docker run --rm -it \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v u-ir:/app/.venv \
      -e HOME=/root \
      --entrypoint /bin/bash \
      install-release-ubuntu:latest
    ;;
  "fedora")
    docker build -t install-release-fedora:latest -f test/fedora/Dockerfile .
    docker run --rm -it \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v f-ir:/app/.venv \
      -e HOME=/root \
      --entrypoint /bin/bash \
      install-release-fedora:latest
    ;;
  *)
    echo "Usage: $0 [ubuntu|fedora]"
    exit 1
    ;;
esac
