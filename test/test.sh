#!/bin/bash

docker build -t test-ubuntu -f ubuntu/Dockerfile .

docker run -it test-ubuntu -v $(pwd)/..:/app -w /app