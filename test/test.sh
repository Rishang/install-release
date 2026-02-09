#!/bin/bash
set -e
cd "$(dirname "$0")/.."

case $1 in
  "ubuntu")
    docker build -t install-release-ubuntu:latest -f test/ubuntu/Dockerfile .
    docker run --rm -it \
      -e HOME=/root \
      --entrypoint /bin/bash \
      install-release-ubuntu:latest
    ;;
  "fedora")
    docker build -t install-release-fedora:latest -f test/fedora/Dockerfile .
    docker run --rm -it \
      -e HOME=/root \
      --entrypoint /bin/bash \
      install-release-fedora:latest
    ;;
  *)
    echo "Usage: $0 [ubuntu|fedora]"
    exit 1
    ;;
esac
