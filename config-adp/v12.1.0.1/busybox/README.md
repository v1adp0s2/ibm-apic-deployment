# Busybox Utility for PVC Cleanup

This directory contains the busybox utility image and manifests for cleaning PVC (Persistent Volume Claim) contents in Kubernetes.

## Purpose

The busybox utility is used to clear PVC contents when resetting API Connect subsystems, particularly for PostgreSQL database resets. This is necessary because:

1. Deleting a PVC in Kubernetes doesn't necessarily delete the underlying storage data
2. NFS storage may retain data even after PVC deletion
3. Fresh subsystem deployments require clean storage

## Files

- `busybox-dockerfile` - Dockerfile to build the busybox image
- `clear-pvc-pod.yaml` - Pod manifest template for clearing PVCs
- `busybox-1.37.tar.gz` - Pre-downloaded busybox image (2.1 MB, amd64)

## Using the Pre-Downloaded Image

The busybox:1.37 image is already included as `busybox-1.37.tar.gz` (2.1 MB, amd64 architecture).

### Load and Push to Your Registry

```bash
cd busybox

# Set your registry (same as main API Connect registry)
export REGISTRY="harbor.example.com/apic"

# Extract the tar.gz
gunzip busybox-1.37.tar.gz

# Load image
docker load -i busybox-1.37.tar

# Tag for your registry
docker tag busybox:1.37 $REGISTRY/busybox:1.37

# Push to registry
docker push $REGISTRY/busybox:1.37
```

## Building the Busybox Image (If Needed)

If you need to rebuild the image:

```bash
# Build the image for amd64 architecture
docker buildx build --platform linux/amd64 \
  -t REGISTRY_PLACEHOLDER/busybox:1.37-amd64 \
  -f busybox/busybox-dockerfile \
  --push busybox/

# OR build without push and save locally
docker buildx build --platform linux/amd64 \
  -t busybox:1.37-amd64 \
  -f busybox/busybox-dockerfile \
  --load busybox/

# Save to tar file
docker save busybox:1.37-amd64 > busybox/busybox-1.37-amd64.tar

# Tag for your registry
docker tag busybox:1.37-amd64 REGISTRY_PLACEHOLDER/busybox:1.37-amd64

# Push to registry
docker push REGISTRY_PLACEHOLDER/busybox:1.37-amd64
```

## Using the Busybox Utility

### 1. Load and Push Image

The busybox image is already included. Load and push it:

```bash
export REGISTRY="harbor.example.com/apic"

# Extract tar.gz (if not already done)
gunzip busybox/busybox-1.37.tar.gz

# Load image from tar
docker load -i busybox/busybox-1.37.tar

# Tag for your registry
docker tag busybox:1.37 $REGISTRY/busybox:1.37

# Push to registry
docker push $REGISTRY/busybox:1.37
```

### 2. Identify PVCs to Clear

```bash
# List all PVCs in the namespace
kubectl get pvc -n NAMESPACE_PLACEHOLDER

# Example output:
# NAME                          STATUS   VOLUME          CAPACITY   STORAGECLASS
# management-xxxxx-db-1         Bound    pvc-xxxxx       50Gi       nfs-ssd
# management-xxxxx-db-1-wal     Bound    pvc-yyyyy       2Gi        nfs-ssd
```

### 3. Edit the Busybox Pod Manifest

Edit `busybox/clear-pvc-pod.yaml` and update:

- `namespace:` - Set to your namespace (e.g., `apic`)
- `image:` - Set to your registry path
- `claimName:` - Set to the PVC names you want to clear
- Add/remove volume mounts as needed

### 4. Deploy Busybox Pod

```bash
# Apply the pod
kubectl apply -f busybox/clear-pvc-pod.yaml

# Watch the logs to see progress
kubectl logs -n NAMESPACE_PLACEHOLDER busybox-clear-pvc -f

# Expected output:
# Starting PVC cleanup...
# Clearing /data PVC...
# /data cleared
# Clearing /wal PVC...
# /wal cleared
# PVC cleanup completed successfully
```

### 5. Clean Up

```bash
# Delete the busybox pod
kubectl delete pod -n NAMESPACE_PLACEHOLDER busybox-clear-pvc

# Now you can safely delete the PVCs
kubectl delete pvc -n NAMESPACE_PLACEHOLDER <pvc-name>
```

## Example: Management Database Reset

Complete procedure to reset Management PostgreSQL database:

```bash
# 1. Scale down Management deployments
kubectl scale deployment -n NAMESPACE_PLACEHOLDER --replicas=0 \
  management-apim management-lur management-ui

# 2. Delete PostgreSQL cluster
kubectl delete cluster -n NAMESPACE_PLACEHOLDER management-xxxxx-db

# 3. Identify PVC names
kubectl get pvc -n NAMESPACE_PLACEHOLDER | grep management

# 4. Edit busybox/clear-pvc-pod.yaml with correct PVC names

# 5. Apply busybox pod
kubectl apply -f busybox/clear-pvc-pod.yaml

# 6. Wait for completion
kubectl logs -n NAMESPACE_PLACEHOLDER busybox-clear-pvc -f

# 7. Delete busybox pod
kubectl delete pod -n NAMESPACE_PLACEHOLDER busybox-clear-pvc

# 8. Delete PVCs
kubectl delete pvc -n NAMESPACE_PLACEHOLDER management-xxxxx-db-1
kubectl delete pvc -n NAMESPACE_PLACEHOLDER management-xxxxx-db-1-wal

# 9. Re-apply Management CR to recreate database
kubectl apply -f 05-management-cr.yaml
```

## Troubleshooting

### Permission Denied Errors

The busybox pod runs as root (`runAsUser: 0`) to ensure it has permission to delete all files. If you encounter permission errors:

```bash
# Check pod events
kubectl describe pod -n NAMESPACE_PLACEHOLDER busybox-clear-pvc

# Check SecurityContext
kubectl get pod -n NAMESPACE_PLACEHOLDER busybox-clear-pvc -o yaml | grep -A5 securityContext
```

### Pod Stuck in Pending

```bash
# Check pod events
kubectl describe pod -n NAMESPACE_PLACEHOLDER busybox-clear-pvc

# Common issues:
# - PVC doesn't exist
# - Registry secret not configured
# - Image pull errors
```

### Image Architecture Mismatch

The pre-downloaded busybox image is for linux/amd64 architecture. Ensure your Kubernetes nodes are amd64:

```bash
# Check node architecture
kubectl get nodes -o wide

# The pre-downloaded image (busybox-1.37.tar.gz) is amd64
# If your nodes are arm64, you'll need to pull and save the arm64 image:
docker pull --platform linux/arm64 busybox:1.37
docker save busybox:1.37 -o busybox-1.37-arm64.tar
gzip busybox-1.37-arm64.tar
```

## Security Notes

- This pod runs with elevated privileges (root user) to clear all files
- Only use this for maintenance operations
- Delete the pod immediately after use
- Do not leave this pod running in production

## Alternative: Manual NFS Cleanup

If you have direct access to the NFS server:

```bash
# SSH to NFS server
ssh <nfs-server>

# Navigate to NFS export directory
cd /path/to/nfs/export

# Find and delete PVC directory
ls -la | grep pvc-<uuid>
rm -rf pvc-<uuid>
```

**Note:** Direct NFS cleanup is faster but requires SSH access to the storage server.
