#!/bin/bash

###################################################################################
# Download cert-manager v1.19.2 Images
###################################################################################
# This script pulls cert-manager images and saves them as tar files
#
# Usage:
#   ./download-cert-manager-images.sh [OUTPUT_DIR]
#
# Default output directory: ./cert-manager-images
###################################################################################

set -e

# Configuration
VERSION="v1.19.2"
OUTPUT_DIR="${1:-./cert-manager-images}"

# Images to download
IMAGES=(
  "quay.io/jetstack/cert-manager-cainjector:${VERSION}"
  "quay.io/jetstack/cert-manager-controller:${VERSION}"
  "quay.io/jetstack/cert-manager-webhook:${VERSION}"
)

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}cert-manager v${VERSION} Image Downloader${NC}"
echo -e "${BLUE}==========================================${NC}\n"

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✓${NC} Created output directory: $OUTPUT_DIR\n"

# Download each image
for image in "${IMAGES[@]}"; do
  # Extract image name for filename
  image_name=$(echo "$image" | sed 's|quay.io/jetstack/||' | sed 's|:|-|' | sed 's|/|-|g')
  tar_file="$OUTPUT_DIR/${image_name}.tar"

  echo -e "${BLUE}Downloading:${NC} $image"

  # Pull the image
  echo -e "${YELLOW}  → Pulling image...${NC}"
  docker pull "$image"

  # Save to tar file
  echo -e "${YELLOW}  → Saving to ${tar_file}...${NC}"
  docker save "$image" -o "$tar_file"

  # Get file size
  size=$(du -h "$tar_file" | cut -f1)
  echo -e "${GREEN}  ✓ Saved${NC} (${size})\n"
done

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}All images downloaded successfully!${NC}"
echo -e "${GREEN}==========================================${NC}\n"

echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_DIR"/*.tar | awk '{print "  " $9 " (" $5 ")"}'

echo ""
echo "To load these images on another system:"
echo "  docker load -i <tar-file>"
echo ""
echo "To push to Harbor registry:"
echo "  docker tag <source-image> harbor.talos.zebra-cloud.net/cert-manager/<image-name>"
echo "  docker push harbor.talos.zebra-cloud.net/cert-manager/<image-name>"
echo ""
