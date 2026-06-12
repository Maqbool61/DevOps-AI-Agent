#!/usr/bin/env bash
# Build Docker image for devops-ai-agent
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE_NAME="${IMAGE_NAME:-devops-ai-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f docker/Dockerfile .

echo ""
echo "Done."
echo ""
echo "Run:"
echo "  docker run -d --name devops-ai-agent -p 8000:8000 --env-file .env ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Or with docker compose:"
echo "  docker compose up -d"
