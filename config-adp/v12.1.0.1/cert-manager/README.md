# cert-manager v1.13.2 - Offline Deployment Package

This directory contains cert-manager manifests and instructions for offline/air-gapped deployment.

## Contents

```
cert-manager/
├── README.md                           # This file
├── cert-manager-v1.13.2.yaml          # cert-manager installation manifest
└── images/                            # Pre-downloaded image tar.gz files (amd64)
    ├── cert-manager-controller-v1.13.2.tar.gz  (18 MB)
    ├── cert-manager-cainjector-v1.13.2.tar.gz  (13 MB)
    └── cert-manager-webhook-v1.13.2.tar.gz     (14 MB)
```

## cert-manager Images

cert-manager requires 3 container images:

```
quay.io/jetstack/cert-manager-controller:v1.13.2
quay.io/jetstack/cert-manager-cainjector:v1.13.2
quay.io/jetstack/cert-manager-webhook:v1.13.2
```

## Option 1: Online Deployment (Internet Access)

**IMPORTANT**: The cert-manager manifest uses `REGISTRY_PLACEHOLDER` for images.

If deploying with original quay.io images, first replace the placeholder:

```bash
# Option A: Use quay.io (original registry)
sed "s|REGISTRY_PLACEHOLDER|quay.io/jetstack|g" \
  cert-manager-v1.13.2.yaml | kubectl apply -f -

# Option B: Use your own registry
export REGISTRY="harbor.example.com/apic"
sed "s|REGISTRY_PLACEHOLDER|$REGISTRY|g" \
  cert-manager-v1.13.2.yaml | kubectl apply -f -
```

**NOTE**: If you've run the main configuration in `00-CONFIGURE.txt`, the placeholder
is already replaced and you can deploy directly:

```bash
kubectl apply -f cert-manager-v1.13.2.yaml
```

Wait for cert-manager to be ready:

```bash
kubectl wait --for=condition=available --timeout=300s \
  deployment/cert-manager -n cert-manager

kubectl wait --for=condition=available --timeout=300s \
  deployment/cert-manager-webhook -n cert-manager

kubectl wait --for=condition=available --timeout=300s \
  deployment/cert-manager-cainjector -n cert-manager
```

## Option 2: Offline Deployment (Air-Gapped)

**NOTE: Images are already included in `images/` directory as tar.gz files!**

For air-gapped environments, the images are pre-downloaded. You just need to:
1. Transfer the cert-manager directory to air-gapped environment
2. Load images and push to private registry
3. Update manifest to use private registry
4. Deploy cert-manager

### Step 1: Images Already Provided

The following images are already saved in `images/` directory (amd64 architecture):
- cert-manager-controller-v1.13.2.tar.gz (18 MB)
- cert-manager-cainjector-v1.13.2.tar.gz (13 MB)
- cert-manager-webhook-v1.13.2.tar.gz (14 MB)

**Total: 45 MB (amd64)**

### Step 2: Transfer Files to Air-Gapped Environment

Transfer the entire `cert-manager/` directory to your air-gapped environment.
The directory includes:
- `cert-manager-v1.13.2.yaml`
- `images/*.tar.gz` (3 files, 45 MB total)

### Step 3: Extract and Load Images

First, extract the tar.gz files:

```bash
cd cert-manager/images
gunzip *.tar.gz
# This creates .tar files from .tar.gz files
```

### Step 4: Load and Push Images to Private Registry

On the air-gapped machine with access to your private registry:

```bash
cd cert-manager/images

# Set your registry (same as main API Connect registry)
export REGISTRY="harbor.example.com/apic"

# Extract tar.gz files
gunzip cert-manager-controller-v1.13.2.tar.gz
gunzip cert-manager-cainjector-v1.13.2.tar.gz
gunzip cert-manager-webhook-v1.13.2.tar.gz

# Load images from tar files
docker load -i cert-manager-controller-v1.13.2.tar
docker load -i cert-manager-cainjector-v1.13.2.tar
docker load -i cert-manager-webhook-v1.13.2.tar

# Tag images for your registry
docker tag quay.io/jetstack/cert-manager-controller:v1.13.2 $REGISTRY/cert-manager-controller:v1.13.2
docker tag quay.io/jetstack/cert-manager-cainjector:v1.13.2 $REGISTRY/cert-manager-cainjector:v1.13.2
docker tag quay.io/jetstack/cert-manager-webhook:v1.13.2 $REGISTRY/cert-manager-webhook:v1.13.2

# Push images to your registry
docker push $REGISTRY/cert-manager-controller:v1.13.2
docker push $REGISTRY/cert-manager-cainjector:v1.13.2
docker push $REGISTRY/cert-manager-webhook:v1.13.2
```

### Step 5: Update Manifest for Private Registry

The manifest already uses `REGISTRY_PLACEHOLDER` which is configured by the main
deployment configuration (`00-CONFIGURE.txt`).

If you haven't run the main configuration, manually replace the placeholder:

```bash
# Set your registry
export REGISTRY="harbor.example.com/apic"

# The placeholder is already "REGISTRY_PLACEHOLDER", just replace it
sed "s|REGISTRY_PLACEHOLDER|$REGISTRY|g" \
  cert-manager-v1.13.2.yaml > cert-manager-v1.13.2-local.yaml

# Verify the changes
grep "image:" cert-manager-v1.13.2-local.yaml | head -5
```

**NOTE**: If you ran the configuration in `00-CONFIGURE.txt`, this step is already done!

### Step 6: Deploy cert-manager

```bash
# Deploy from local registry
kubectl apply -f cert-manager-v1.13.2-local.yaml

# Wait for cert-manager to be ready
kubectl get pods -n cert-manager -w
```

## Option 3: Deploy with imagePullSecrets (Private Registry with Auth)

If your private registry requires authentication:

### Create Registry Secret in cert-manager Namespace

```bash
kubectl create namespace cert-manager

kubectl create secret docker-registry REGISTRY_SECRET_PLACEHOLDER \
  --namespace=cert-manager \
  --docker-server=<REGISTRY_SERVER> \
  --docker-username=<REGISTRY_USER> \
  --docker-password=<REGISTRY_PASSWORD>
```

### Add imagePullSecrets to Manifest

Edit `cert-manager-v1.13.2-local.yaml` and add to each Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cert-manager
  namespace: cert-manager
spec:
  template:
    spec:
      imagePullSecrets:
      - name: REGISTRY_SECRET_PLACEHOLDER  # Add this line
      serviceAccountName: cert-manager
      containers:
      - name: cert-manager-controller
        image: YOUR_REGISTRY/cert-manager-controller:v1.13.2
```

Add `imagePullSecrets` to all 3 Deployments:
- cert-manager
- cert-manager-cainjector
- cert-manager-webhook

Then deploy:

```bash
kubectl apply -f cert-manager-v1.13.2-local.yaml
```

## Verification

```bash
# Check all pods are running
kubectl get pods -n cert-manager

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# cert-manager-xxxxxxxxxx-xxxxx             1/1     Running   0          2m
# cert-manager-cainjector-xxxxxxxxxx-xxxxx  1/1     Running   0          2m
# cert-manager-webhook-xxxxxxxxxx-xxxxx     1/1     Running   0          2m

# Check deployments are ready
kubectl get deployments -n cert-manager

# All deployments should show READY 1/1

# Test cert-manager is working
kubectl get crds | grep cert-manager

# Should show several CRDs like:
# certificates.cert-manager.io
# issuers.cert-manager.io
# clusterissuers.cert-manager.io
```

## Troubleshooting

### Images Won't Pull from Private Registry

```bash
# Check if secret exists
kubectl get secret -n cert-manager REGISTRY_SECRET_PLACEHOLDER

# Check if images exist in registry
docker pull $REGISTRY/cert-manager-controller:v1.13.2

# Check pod events
kubectl describe pod -n cert-manager <pod-name>
```

### Pods in CrashLoopBackOff

```bash
# Check logs
kubectl logs -n cert-manager deployment/cert-manager
kubectl logs -n cert-manager deployment/cert-manager-webhook
kubectl logs -n cert-manager deployment/cert-manager-cainjector

# Check if webhook service is accessible
kubectl get svc -n cert-manager cert-manager-webhook
```

### Certificate/Issuer Not Working

```bash
# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager -f

# Check webhook is reachable
kubectl run -it --rm debug-curl --image=curlimages/curl --restart=Never -- \
  curl -v https://cert-manager-webhook.cert-manager.svc:443
```

## Uninstall

```bash
# Delete cert-manager
kubectl delete -f cert-manager-v1.13.2.yaml

# Or if using local manifest
kubectl delete -f cert-manager-v1.13.2-local.yaml

# Delete namespace (optional)
kubectl delete namespace cert-manager
```

**WARNING**: Deleting cert-manager will not delete certificates/secrets it created,
but you won't be able to renew them automatically.

## Image Sizes

**Included in `images/` directory (compressed, amd64 architecture):**
- cert-manager-controller-v1.13.2.tar.gz: 18 MB
- cert-manager-cainjector-v1.13.2.tar.gz: 13 MB
- cert-manager-webhook-v1.13.2.tar.gz: 14 MB

**Total compressed**: 45 MB (amd64)
**Total uncompressed**: ~150 MB (after gunzip)
**Architecture**: linux/amd64

## Version Information

- **cert-manager Version**: v1.13.2
- **Release Date**: October 2023
- **Kubernetes Compatibility**: 1.24 - 1.30
- **Architecture**: linux/amd64 (Intel/AMD 64-bit)
- **Source**: https://github.com/cert-manager/cert-manager/releases/tag/v1.13.2

**Note**: All pre-downloaded images are for amd64 architecture. If you need arm64 or other architectures, you'll need to pull and save the images yourself with the appropriate `--platform` flag.

## Additional Resources

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [cert-manager Installation Guide](https://cert-manager.io/docs/installation/)
- [cert-manager GitHub](https://github.com/cert-manager/cert-manager)

## Integration with API Connect

After cert-manager is deployed and verified:

1. Return to the main deployment directory:
   ```bash
   cd ..
   ```

2. Deploy the ingress issuer:
   ```bash
   kubectl apply -f 04-ingress-issuer.yaml -n NAMESPACE_PLACEHOLDER
   ```

3. Verify certificates are issued:
   ```bash
   kubectl get certificates -n NAMESPACE_PLACEHOLDER
   ```

4. Continue with API Connect deployment (see DEPLOYMENT-GUIDE.txt)

---

**Note**: If deploying to an air-gapped environment, ensure you also have all
API Connect images saved and pushed to your private registry before proceeding
with the main deployment.
