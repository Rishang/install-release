FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && pip install -U uv --break-system-packages

ENTRYPOINT [ "/bin/bash" ]

