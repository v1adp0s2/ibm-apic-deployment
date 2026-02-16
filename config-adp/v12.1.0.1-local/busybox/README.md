# Busybox Utility for PVC Cleanup

This directory contains the busybox image and instructions for clearing PVC contents in Kubernetes.

## Files

- `busybox-1.37.tar` - Busybox Docker image (version 1.37)
- `clear-pvc-pod.yaml` - Pod manifest for clearing PVC contents
- `load-and-push.sh` - Script to load and push to Harbor

## Usage

### 1. Load and Push Image to Harbor

```bash
# Load image
docker load -i busybox-1.37.tar

# Tag for Harbor
docker tag busybox:1.37 harbor.talos.zebra-cloud.net/apic/busybox:1.37

# Push to Harbor
docker push harbor.talos.zebra-cloud.net/apic/busybox:1.37
```

### 2. Clear PVC Contents

Use this when you need to completely wipe a PVC's contents:

```bash
# 1. Scale down or delete the workload using the PVC
kubectl scale deployment <deployment-name> -n <namespace> --replicas=0

# 2. Delete the StatefulSet/Pod using the PVC
kubectl delete statefulset <statefulset-name> -n <namespace>

# 3. Edit clear-pvc-pod.yaml and update:
#    - PVC name(s) in the volumes section
#    - Namespace
#    - Mount paths if needed

# 4. Apply the cleanup pod
kubectl apply -f clear-pvc-pod.yaml

# 5. Wait for completion and check logs
kubectl wait --for=condition=Ready pod/busybox-clear-pvc -n <namespace> --timeout=60s
kubectl logs busybox-clear-pvc -n <namespace>

# 6. Delete the cleanup pod
kubectl delete -f clear-pvc-pod.yaml

# 7. Recreate the workload
```

## Example: Clear Management PostgreSQL PVCs

```bash
export KUBECONFIG=/path/to/kubeconfig.yaml

# 1. Scale down Management deployments
kubectl scale deployment -n apic --replicas=0 -l app.kubernetes.io/instance=management

# 2. Delete PostgreSQL cluster
kubectl delete cluster management-99543590-db -n apic

# 3. Wait for database pod to terminate
kubectl wait --for=delete pod -l cnpg.io/cluster=management-99543590-db -n apic --timeout=120s

# 4. Apply busybox cleanup pod (already configured for Management DB PVCs)
kubectl apply -f clear-pvc-pod.yaml

# 5. Wait and check logs
sleep 10
kubectl logs busybox-clear-pvc -n apic

# 6. Delete cleanup pod
kubectl delete -f clear-pvc-pod.yaml

# 7. PostgreSQL cluster will be auto-recreated by API Connect operator with fresh database
```

## Important Notes

- **Data Loss**: This operation permanently deletes all data in the PVC
- **Backup First**: Always backup important data before clearing PVCs
- **PVC Must Be Released**: The PVC must not be mounted by any running pod
- **Auto-Recreation**: For API Connect, the operator will automatically recreate resources like PostgreSQL clusters

## Troubleshooting

### Pod Stays in Pending State

Check if the PVC is still bound to another pod:

```bash
kubectl describe pvc <pvc-name> -n <namespace>
kubectl get pods -n <namespace> -o json | jq -r '.items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName=="<pvc-name>") | .metadata.name'
```

### Permission Denied Errors

The busybox pod runs as root by default. If you encounter permission issues:

```bash
kubectl exec -it busybox-clear-pvc -n <namespace> -- ls -la /data
```

### PVC Not Clearing Due to NFS Issues

If NFS has stale filehandles or locks:

```bash
# SSH to NFS server
ssh nas.local

# Find the PV directory
ls -la "/share/NFSv=4/talos-nfs/" | grep <pv-name>

# Force remove (use with caution)
rm -rf "/share/NFSv=4/talos-nfs/<pv-directory>/*"
```

## Alternative: Manual NFS Cleanup

If Kubernetes pod method fails, clean directly on NFS server:

```bash
# 1. SSH to NFS server
ssh nas.local

# 2. Find PVC directory
export PV_NAME="pvc-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
cd "/share/NFSv=4/talos-nfs/$PV_NAME"

# 3. Clear contents
rm -rf ./* ./.*

# 4. Verify
ls -la
```

## Security Considerations

- The busybox pod requires elevated privileges to delete files
- Only use in namespaces where you have appropriate RBAC permissions
- Always verify the PVC name before applying the cleanup pod
- Consider using Kubernetes Job instead of Pod for automatic cleanup after completion
