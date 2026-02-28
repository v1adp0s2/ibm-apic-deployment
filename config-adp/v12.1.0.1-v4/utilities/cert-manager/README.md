# cert-manager v1.19.2 for IBM API Connect

**Kubernetes native certificate management controller**

## Overview

cert-manager automates the management and issuance of TLS certificates in Kubernetes. It is a **required prerequisite** for IBM API Connect deployment.

### Version Information

- **Version**: v1.19.2 (latest stable as of February 2025)
- **Upstream**: [cert-manager.io](https://cert-manager.io)
- **Release**: [v1.19.2 Release Notes](https://github.com/cert-manager/cert-manager/releases/tag/v1.19.2)

### Why v1.19.2?

cert-manager v1.19.2 includes critical bug fixes from v1.19.0 and v1.19.1:
- Fixes unnecessary certificate re-issuance bug in v1.19.0
- Improved stability and performance
- Full Kubernetes 1.30+ support

## Quick Start

### Prerequisites

1. **Source configuration first**:
   ```bash
   cd ../..
   source config.env
   ```

2. **Verify variables are loaded**:
   ```bash
   echo $APIC_IMAGE_REGISTRY
   # Should output: harbor.adp.example.com/ibm-apic (or your registry)
   ```

### Online Deployment (Internet Access)

If your cluster can pull from `quay.io/jetstack`:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.19.2/cert-manager.yaml
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager -n cert-manager
```

### Offline Deployment (Air-gapped / Internal Registry)

#### Step 1: Push Images to Internal Registry

Manually push images:

```bash
# Pull core images from quay.io (required for all deployments)
docker pull quay.io/jetstack/cert-manager-controller:v1.19.2
docker pull quay.io/jetstack/cert-manager-cainjector:v1.19.2
docker pull quay.io/jetstack/cert-manager-webhook:v1.19.2

# Optional: Only if using ACME/Let's Encrypt (not needed for air-gapped IBM APIC)
# docker pull quay.io/jetstack/cert-manager-acmesolver:v1.19.2

# Tag for your registry
docker tag quay.io/jetstack/cert-manager-controller:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2
docker tag quay.io/jetstack/cert-manager-cainjector:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-cainjector:v1.19.2
docker tag quay.io/jetstack/cert-manager-webhook:v1.19.2 \
  ${APIC_IMAGE_REGISTRY}/cert-manager-webhook:v1.19.2

# Push to your registry
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-cainjector:v1.19.2
docker push ${APIC_IMAGE_REGISTRY}/cert-manager-webhook:v1.19.2
```

#### Step 2: Deploy cert-manager

```bash
cd utilities/cert-manager
source ../../config.env
envsubst < cert-manager-v1.19.2.yaml.template | kubectl apply -f -
```

#### Step 3: Wait for Ready

```bash
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager -n cert-manager
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager-webhook -n cert-manager
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager-cainjector -n cert-manager
```

#### Step 4: Verify

```bash
kubectl get pods -n cert-manager
```

Expected output:
```
NAME                                      READY   STATUS    RESTARTS   AGE
cert-manager-xxxxxxxxxx-xxxxx             1/1     Running   0          2m
cert-manager-cainjector-xxxxxxxxxx-xxxxx  1/1     Running   0          2m
cert-manager-webhook-xxxxxxxxxx-xxxxx     1/1     Running   0          2m
```

## Files in This Directory

```
cert-manager/
├── README.md                              # This file
├── COMMANDS.txt                           # Detailed deployment commands
├── cert-manager-v1.19.2.yaml.template     # Parameterized manifest
└── images/                                # (empty - for reference)
```

## How Parameterization Works

The `cert-manager-v1.19.2.yaml.template` file uses environment variables:

**Before (upstream)**:
```yaml
image: "quay.io/jetstack/cert-manager-controller:v1.19.2"
```

**After (parameterized)**:
```yaml
image: "${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2"
```

When you run `envsubst`, it replaces `${APIC_IMAGE_REGISTRY}` with your actual registry from `config.env`.

## Components Deployed

cert-manager consists of 3 core components + 1 optional:

### Core Components (Required)
1. **cert-manager-controller** - Main certificate controller
2. **cert-manager-cainjector** - Injects CA bundles into resources
3. **cert-manager-webhook** - Validates cert-manager resources

### Optional Component
4. **cert-manager-acmesolver** - Solves ACME challenges (for Let's Encrypt)
   - Only needed if using ACME issuers (Let's Encrypt, etc.)
   - **NOT required** for air-gapped/offline deployments using self-signed or internal CA
   - IBM API Connect typically uses self-signed certificates, so this is optional

All components run in the `cert-manager` namespace.

## Custom Resource Definitions (CRDs)

cert-manager installs the following CRDs:

- `certificates.cert-manager.io` - Certificate requests
- `certificaterequests.cert-manager.io` - Low-level certificate requests
- `issuers.cert-manager.io` - Namespace-scoped certificate issuers
- `clusterissuers.cert-manager.io` - Cluster-scoped certificate issuers
- `challenges.acme.cert-manager.io` - ACME challenges
- `orders.acme.cert-manager.io` - ACME orders

## Usage in API Connect

After cert-manager is deployed, API Connect uses it for:

1. **Internal TLS Communications**:
   - Management cluster internal certificates
   - Analytics cluster internal certificates
   - Gateway cluster internal certificates
   - Developer Portal internal certificates

2. **Ingress TLS**:
   - Management endpoints (Cloud Manager, API Manager, Platform API)
   - Gateway endpoints
   - Developer Portal endpoints
   - Analytics ingestion endpoint

3. **mTLS Client Certificates**:
   - Analytics ingestion client
   - Developer Portal admin client
   - Gateway management client

## Verification

Check cert-manager is working:

```bash
# Check all components are running
kubectl get pods -n cert-manager

# Check CRDs are installed
kubectl get crds | grep cert-manager

# Check for any existing issuers
kubectl get clusterissuers
kubectl get issuers --all-namespaces

# View controller logs
kubectl logs -n cert-manager deployment/cert-manager --tail=50
```

## Troubleshooting

### Pods in ImagePullBackOff

**Cause**: Images not available in internal registry

**Solution**:
1. Verify images exist: `docker pull ${APIC_IMAGE_REGISTRY}/cert-manager-controller:v1.19.2`
2. Check registry credentials are configured
3. Re-push images using commands from COMMANDS.txt

### Pods in CrashLoopBackOff

**Cause**: Configuration or resource issues

**Solution**:
1. Check logs: `kubectl logs -n cert-manager deployment/cert-manager --tail=100`
2. Check resource limits: `kubectl describe pod -n cert-manager`
3. Verify RBAC permissions are created

### Webhook Errors

**Cause**: Webhook service not accessible

**Solution**:
1. Check service: `kubectl get svc cert-manager-webhook -n cert-manager`
2. Check endpoints: `kubectl get endpoints cert-manager-webhook -n cert-manager`
3. Check webhook logs: `kubectl logs -n cert-manager deployment/cert-manager-webhook`

## Uninstall

**WARNING: WARNING**: This removes ALL cert-manager resources including any certificates!

```bash
# Delete cert-manager
kubectl delete -f cert-manager-v1.19.2.yaml.template

# Verify removal
kubectl get namespace cert-manager
```

If namespace stuck in `Terminating`:
```bash
kubectl get namespace cert-manager -o yaml
# Check for finalizers and remove if needed
```

## Next Steps

After cert-manager is deployed and verified:

1. **Return to main package**:
   ```bash
   cd ../..
   ```

2. **Continue with API Connect deployment**:
   ```bash
   cat core/DEPLOY-CORE.txt
   ```

3. **Deploy core components** following `core/DEPLOY-CORE.txt`

## Additional Resources

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [cert-manager GitHub](https://github.com/cert-manager/cert-manager)
- [cert-manager v1.19 Release Notes](https://cert-manager.io/docs/releases/release-notes/release-notes-1.19/)
- [IBM API Connect Documentation](https://www.ibm.com/docs/en/api-connect)

## Support

For issues with:
- **cert-manager itself**: [cert-manager GitHub Issues](https://github.com/cert-manager/cert-manager/issues)
- **API Connect integration**: IBM Support or API Connect documentation
- **This deployment package**: Check package README.md

---

**Package**: v12.1.0.1-v3
**Created**: 2026-02-19
**cert-manager Version**: v1.19.2
