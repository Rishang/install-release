#!/bin/bash
# set -x
cd "$(dirname "$0")/.."

function build_ubuntu {
  docker build -t install-release-ubuntu:latest -f test/images/ubuntu/Dockerfile .
}

function build_fedora {
  docker build -t install-release-fedora:latest -f test/images/fedora/Dockerfile .
}

case $1 in
  "ubuntu")
    docker rm -f ir-ubuntu
    docker images | grep install-release-ubuntu || build_ubuntu
    docker run -d \
      --name ir-ubuntu \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$HOME/.config/install_release/config.json":/root/.config/install_release/config.json:ro \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v u-ir:/app/.venv \
      -e HOME=/root \
      install-release-ubuntu:latest
    docker exec ir-ubuntu bash -c '/usr/local/bin/uv sync'
    # docker exec -it ir-ubuntu bash
    ;;
  "fedora")
    docker rm -f ir-fedora
    docker images | grep install-release-fedora || build_fedora
    docker run -d \
      --name ir-fedora \
      -v "$(pwd)/InstallRelease":/app/InstallRelease \
      -v "$HOME/.config/install_release/config.json":/root/.config/install_release/config.json:ro \
      -v "$(pwd)/cli":/app/cli \
      -v "$(pwd)/pyproject.toml":/app/pyproject.toml \
      -v "$(pwd)/uv.lock":/app/uv.lock \
      -v f-ir:/app/.venv \
      -e HOME=/root \
      install-release-fedora:latest
    docker exec ir-fedora bash -c '/usr/local/bin/uv sync'
    docker exec -it ir-fedora bash

    ;;
  "build")
    build_ubuntu
    build_fedora
    ;;
  *)
    echo "Usage: $0 [ubuntu|fedora]"
    exit 1
    ;;
esac
