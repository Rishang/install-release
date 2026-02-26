#!/bin/bash
# set -x
cd "$(dirname "$0")/.."

case $1 in
  "ubuntu")
    docker rm -f ir-ubuntu
    docker run -itd \
      --name ir-ubuntu \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v u-ir:/app/.venv \
      -e HOME=/root \
      install-release-ubuntu:latest
    docker exec -it ir-ubuntu bash -c '/usr/local/bin/uv sync'
    # docker exec -it ir-ubuntu bash
    ;;
  "fedora")
    docker rm -f ir-fedora
    docker run -itd \
      --name ir-fedora \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v f-ir:/app/.venv \
      -e HOME=/root \
      install-release-fedora:latest
    docker exec -it ir-fedora bash -c '/usr/local/bin/uv sync'
    docker exec -it ir-fedora bash

    ;;
  "build")
    docker build -t install-release-ubuntu:latest -f test/images/ubuntu/Dockerfile .
    docker build -t install-release-fedora:latest -f test/images/fedora/Dockerfile .
    ;;
  *)
    echo "Usage: $0 [ubuntu|fedora]"
    exit 1
    ;;
esac
