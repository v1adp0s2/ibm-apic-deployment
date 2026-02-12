#!/bin/bash

###################################################################################
# Mirror cert-manager v1.19.2 Images to Harbor
###################################################################################
# This script pulls cert-manager images from quay.io and pushes them to Harbor
#
# Prerequisites:
# - Docker logged in to Harbor: docker login harbor.talos.zebra-cloud.net
# - Harbor project 'apic' exists
#
# Usage:
#   ./mirror-cert-manager-to-harbor.sh
#
###################################################################################

set -e

# Configuration
VERSION="v1.19.2"
SOURCE_REGISTRY="quay.io/jetstack"
TARGET_REGISTRY="harbor.talos.zebra-cloud.net/apic"

# Images to mirror
IMAGES=(
  "cert-manager-cainjector"
  "cert-manager-controller"
  "cert-manager-webhook"
)

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}cert-manager v${VERSION} Image Mirror to Harbor${NC}"
echo -e "${BLUE}=================================================${NC}\n"

# Check if logged into Harbor
if ! docker info 2>/dev/null | grep -q "harbor.talos.zebra-cloud.net"; then
  echo -e "${YELLOW}⚠ Not logged into Harbor. Attempting login...${NC}"
  echo "Please enter Harbor credentials:"
  docker login harbor.talos.zebra-cloud.net
  echo ""
fi

# Mirror each image
for image_name in "${IMAGES[@]}"; do
  source_image="${SOURCE_REGISTRY}/${image_name}:${VERSION}"
  target_image="${TARGET_REGISTRY}/${image_name}:${VERSION}"

  echo -e "${BLUE}Mirroring:${NC} ${image_name}:${VERSION}"
  echo -e "${YELLOW}  Source:${NC} $source_image"
  echo -e "${YELLOW}  Target:${NC} $target_image"

  # Pull from quay.io
  echo -e "${YELLOW}  → Pulling from quay.io...${NC}"
  docker pull "$source_image"

  # Tag for Harbor
  echo -e "${YELLOW}  → Tagging for Harbor...${NC}"
  docker tag "$source_image" "$target_image"

  # Push to Harbor
  echo -e "${YELLOW}  → Pushing to Harbor...${NC}"
  docker push "$target_image"

  echo -e "${GREEN}  ✓ Mirrored successfully${NC}\n"
done

echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}All cert-manager images mirrored to Harbor!${NC}"
echo -e "${GREEN}=================================================${NC}\n"

echo "Images pushed to Harbor project: apic"
echo ""
echo "Next steps:"
echo "  1. Use the modified cert-manager YAML that references Harbor images"
echo "  2. Deploy: kubectl apply -f cert-manager-1.19.2-harbor.yaml"
echo ""
