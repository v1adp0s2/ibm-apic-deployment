================================================================================
cert-manager v1.19.2 - Container Images
================================================================================

This directory is a placeholder for cert-manager container image tar files
(for air-gapped deployments).

================================================================================
IMAGES REQUIRED
================================================================================

Image Name:                          Size:      Source:
---------------------------------------------------------------------------
cert-manager-controller:v1.19.2      ~45 MB     quay.io/jetstack
cert-manager-cainjector:v1.19.2      ~35 MB     quay.io/jetstack
cert-manager-webhook:v1.19.2         ~38 MB     quay.io/jetstack
cert-manager-acmesolver:v1.19.2      ~30 MB     quay.io/jetstack

Total: ~148 MB (compressed tar.gz files)

================================================================================
METHOD 1: DIRECT PUSH TO REGISTRY (Recommended)
================================================================================

If you have access to both quay.io and your internal registry, push directly:

See ../COMMANDS.txt for detailed commands to:
  1. Pull images from quay.io/jetstack
  2. Tag them for your internal registry
  3. Push to ${APIC_IMAGE_REGISTRY}

No need to save tar files to this directory.

================================================================================
METHOD 2: SAVE AS TAR FILES (For Air-gapped Transfer)
================================================================================

If you need to save images as tar files for transfer to air-gapped environment:

STEP 1: Pull images from quay.io
---------------------------------
docker pull quay.io/jetstack/cert-manager-controller:v1.19.2
docker pull quay.io/jetstack/cert-manager-cainjector:v1.19.2
docker pull quay.io/jetstack/cert-manager-webhook:v1.19.2
docker pull quay.io/jetstack/cert-manager-acmesolver:v1.19.2

STEP 2: Save images as tar files
---------------------------------
docker save quay.io/jetstack/cert-manager-controller:v1.19.2 | \
  gzip > cert-manager-controller-v1.19.2.tar.gz

docker save quay.io/jetstack/cert-manager-cainjector:v1.19.2 | \
  gzip > cert-manager-cainjector-v1.19.2.tar.gz

docker save quay.io/jetstack/cert-manager-webhook:v1.19.2 | \
  gzip > cert-manager-webhook-v1.19.2.tar.gz

docker save quay.io/jetstack/cert-manager-acmesolver:v1.19.2 | \
  gzip > cert-manager-acmesolver-v1.19.2.tar.gz

STEP 3: Transfer to air-gapped environment
-------------------------------------------
Copy the tar.gz files to your air-gapped environment.

STEP 4: Load images on air-gapped system
-----------------------------------------
gunzip cert-manager-controller-v1.19.2.tar.gz
gunzip cert-manager-cainjector-v1.19.2.tar.gz
gunzip cert-manager-webhook-v1.19.2.tar.gz

docker load -i cert-manager-controller-v1.19.2.tar
docker load -i cert-manager-cainjector-v1.19.2.tar
docker load -i cert-manager-webhook-v1.19.2.tar

STEP 5: Tag for internal registry
----------------------------------
docker tag quay.io/jetstack/cert-manager-controller:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2

docker tag quay.io/jetstack/cert-manager-cainjector:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-cainjector:v1.19.2

docker tag quay.io/jetstack/cert-manager-webhook:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-webhook:v1.19.2

STEP 6: Push to internal registry
----------------------------------
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-cainjector:v1.19.2
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-webhook:v1.19.2

================================================================================
VERIFICATION
================================================================================

Verify images are in your registry:

  docker pull ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2
  docker pull ${APIC_IMAGE_REGISTRY}/cert-manager-cainjector:v1.19.2
  docker pull ${APIC_IMAGE_REGISTRY}/cert-manager-webhook:v1.19.2

Or check via registry API/UI (e.g., Harbor, Nexus, etc.)

================================================================================
