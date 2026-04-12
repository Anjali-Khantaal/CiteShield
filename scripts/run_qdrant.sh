#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
STORAGE_DIR="$ROOT_DIR/.qdrant_storage"

mkdir -p "$STORAGE_DIR"

docker run \
  --name citeshield-qdrant \
  --rm \
  -d \
  -p 127.0.0.1:6333:6333 \
  -p 127.0.0.1:6334:6334 \
  -v "$STORAGE_DIR:/qdrant/storage" \
  qdrant/qdrant
