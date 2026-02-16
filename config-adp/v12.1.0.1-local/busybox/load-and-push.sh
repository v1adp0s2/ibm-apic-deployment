#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAR="$SCRIPT_DIR/busybox-1.37.tar"
HARBOR_REGISTRY="harbor.talos.zebra-cloud.net"
HARBOR_PROJECT="apic"
IMAGE_NAME="busybox"
IMAGE_TAG="1.37"

echo "Loading busybox image from tar..."
docker load -i "$IMAGE_TAR"

echo "Tagging image for Harbor..."
docker tag busybox:1.37 "$HARBOR_REGISTRY/$HARBOR_PROJECT/$IMAGE_NAME:$IMAGE_TAG"

echo "Pushing image to Harbor..."
docker push "$HARBOR_REGISTRY/$HARBOR_PROJECT/$IMAGE_NAME:$IMAGE_TAG"

echo "Done! Image pushed to: $HARBOR_REGISTRY/$HARBOR_PROJECT/$IMAGE_NAME:$IMAGE_TAG"
