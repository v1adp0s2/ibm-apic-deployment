# cert-manager v1.19.2 - Harbor Integration

This directory contains cert-manager v1.19.2 files configured for deployment using Harbor private registry.

## Contents

| File | Description | Size |
|------|-------------|------|
| `cert-manager-1.19.2-original.yaml` | Original cert-manager YAML from quay.io | 984K |
| `cert-manager-1.19.2-harbor.yaml` | Modified YAML for Harbor registry | 984K |
| `cert-manager-cainjector-v1.19.2.tar` | Cainjector image tar file | 11M |
| `cert-manager-controller-v1.19.2.tar` | Controller image tar file | 20M |
| `cert-manager-webhook-v1.19.2.tar` | Webhook image tar file | 17M |
| `mirror-cert-manager-to-harbor.sh` | Script to push images to Harbor | - |

## Quick Start

### Option 1: Mirror Images to Harbor (Recommended)

If you have internet access and can pull from quay.io:

```bash
# Login to Harbor
docker login harbor.talos.zebra-cloud.net

# Run the mirror script
./mirror-cert-manager-to-harbor.sh

# Deploy cert-manager using Harbor images
kubectl apply -f cert-manager-1.19.2-harbor.yaml
```

### Option 2: Load from Tar Files (Air-gapped)

If you're in an air-gapped environment or already have the tar files:

```bash
# Load images from tar files
docker load -i cert-manager-cainjector-v1.19.2.tar
docker load -i cert-manager-controller-v1.19.2.tar
docker load -i cert-manager-webhook-v1.19.2.tar

# Tag for Harbor
docker tag quay.io/jetstack/cert-manager-cainjector:v1.19.2 \
  harbor.talos.zebra-cloud.net/apic/cert-manager-cainjector:v1.19.2
docker tag quay.io/jetstack/cert-manager-controller:v1.19.2 \
  harbor.talos.zebra-cloud.net/apic/cert-manager-controller:v1.19.2
docker tag quay.io/jetstack/cert-manager-webhook:v1.19.2 \
  harbor.talos.zebra-cloud.net/apic/cert-manager-webhook:v1.19.2

# Login to Harbor
docker login harbor.talos.zebra-cloud.net

# Push to Harbor
docker push harbor.talos.zebra-cloud.net/apic/cert-manager-cainjector:v1.19.2
docker push harbor.talos.zebra-cloud.net/apic/cert-manager-controller:v1.19.2
docker push harbor.talos.zebra-cloud.net/apic/cert-manager-webhook:v1.19.2

# Deploy cert-manager
kubectl apply -f cert-manager-1.19.2-harbor.yaml
```

## Image Details

All images are version **v1.19.2** and have been configured to pull from:

```
harbor.talos.zebra-cloud.net/apic/cert-manager-cainjector:v1.19.2
harbor.talos.zebra-cloud.net/apic/cert-manager-controller:v1.19.2
harbor.talos.zebra-cloud.net/apic/cert-manager-webhook:v1.19.2
```

## Harbor Project

- **Registry**: `harbor.talos.zebra-cloud.net`
- **Project**: `apic`
- **Access**: Requires authentication

Ensure the Harbor project `apic` exists and you have push permissions before running the mirror script.

## Verification

After deployment, verify cert-manager is running:

```bash
# Check pods
kubectl get pods -n cert-manager

# Check certificates CRD
kubectl get crd | grep cert-manager

# Verify version
kubectl get deployment -n cert-manager cert-manager-controller -o jsonpath='{.spec.template.spec.containers[0].image}'
```

Expected output should show Harbor registry:
```
harbor.talos.zebra-cloud.net/apic/cert-manager-controller:v1.19.2
```

## Differences from Original

The only modification in `cert-manager-1.19.2-harbor.yaml` is the image registry:

- **Original**: `quay.io/jetstack/*`
- **Modified**: `harbor.talos.zebra-cloud.net/apic/*`

All other configurations remain unchanged.

## Cleanup

To remove cert-manager:

```bash
kubectl delete -f cert-manager-1.19.2-harbor.yaml
```

## Notes

- cert-manager v1.19.2 requires Kubernetes 1.22+
- Total download size: ~48M (all 3 images)
- The Harbor YAML can be used for fresh installations or upgrades
- If cert-manager is already installed from quay.io, the deployment will update to use Harbor images

## Related Files

- Main deployment guide: `../DEPLOYMENT-GUIDE.md`
- APIC deployment automation: `../deploy-apic.sh`
