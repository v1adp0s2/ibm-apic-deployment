# IBM API Connect 10.0.8.6 - Kubernetes Deployment Guide

## Environment

| Item | Value |
|------|-------|
| Cluster | Kubernetes with Traefik ingress |
| Namespace | `apic` |
| Domain | `apic.talos.zebra-cloud.net` |
| Storage Class | `nfs-ssd` |
| Private Registry | `harbor.talos.zebra-cloud.net` |
| Operator Version | 10.0.8.6 |
| Product Version | 10.0.8.6 |
| Profile | `n1xc4.m16` (single-node, smallest) |
| License | `L-HTFS-UAXYM3` |

## Current Status

| Step | Status |
|------|--------|
| 1. Namespace | DONE |
| 2. cert-manager | DONE |
| 3. Registry secrets (cp.icr.io) | DONE (will need Harbor secret) |
| 4. CRDs | DONE |
| 5. API Connect operator | DONE (Running) |
| 6. DataPower operator | DONE (Running) |
| 7. Ingress issuer | DONE |
| 8. Mirror images to Harbor | **TODO** |
| 9. Update secrets + CRs for Harbor | **TODO** |
| 10. Management subsystem | **TODO** (deployed but stuck - edb-operator ImagePullBackOff) |
| 11. Gateway subsystem | **TODO** |
| 12. Portal subsystem | **TODO** |
| 13. Analytics subsystem | **TODO** |

---

## Step 1: Create Namespace (DONE)

    kubectl-1.30 create ns apic

## Step 2: Install cert-manager (DONE)

    kubectl-1.30 apply -f cert-manager/cert-manager-1.19.2.yaml
    kubectl-1.30 wait --for=condition=Ready pods --all -n cert-manager --timeout=300s

## Step 3: Create Secrets (DONE)

    source .env

    # IBM Entitled Registry secret (for operators)
    kubectl-1.30 create secret docker-registry apic-registry-secret \
      --docker-server=cp.icr.io \
      --docker-username=cp \
      --docker-password=$IBM_ENTITLEMENT_KEY \
      --docker-email=$IBM_USER \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

    # DataPower registry secret
    kubectl-1.30 create secret docker-registry datapower-docker-local-cred \
      --docker-server=cp.icr.io \
      --docker-username=cp \
      --docker-password=$IBM_ENTITLEMENT_KEY \
      --docker-email=$IBM_USER \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

    # DataPower admin credentials
    kubectl-1.30 create secret generic datapower-admin-credentials \
      --from-literal=password=$APIC_ADMIN_PWD \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

## Step 4: Install CRDs (DONE)

    kubectl-1.30 apply --server-side --force-conflicts \
      -f apiconnect-operator/ibm-apiconnect-crds.yaml

## Step 5: Install Operators (DONE)

    kubectl-1.30 apply -f apiconnect-operator/ibm-apiconnect.yaml --namespace apic
    kubectl-1.30 apply -f apiconnect-operator/ibm-datapower.yaml --namespace apic

**Important:** Before applying, ensure `namespace: default` is replaced with `namespace: apic`
in `ibm-datapower.yaml` (2 occurrences in RoleBinding/ClusterRoleBinding subjects).

## Step 6: Install Ingress Issuer (DONE)

    kubectl-1.30 apply -f apiconnect-operator/helper_files/ingress-issuer-v1.yaml -n apic

---

## Step 7: Download apiconnect-image-tool (TODO)

Download from [IBM Fix Central](https://www.ibm.com/support/fixcentral/):
- Product: IBM API Connect → 10.0.8.6
- File: `apiconnect-image-tool-10.0.8.6.tar.gz`

On Windows (download to E:\apic):

    curl.exe -L -C - -o E:\apic\apiconnect-image-tool-10.0.8.6.tar.gz --retry 999 --retry-delay 5 --retry-all-errors --create-dirs <DOWNLOAD_URL>

Then transfer to the server:

    scp E:\apic\apiconnect-image-tool-10.0.8.6.tar.gz demo01:/home/administrator/git/demos/apic-deployment/

## Step 8: Mirror Images to Harbor (TODO)

### 8a. Load image tool into Docker

    cd /home/administrator/git/demos/apic-deployment
    docker load < apiconnect-image-tool-10.0.8.6.tar.gz

### 8b. List all images (optional, for reference)

    docker run --rm apiconnect-image-tool-10.0.8.6 version --images

### 8c. Upload all images to Harbor

    docker run --rm apiconnect-image-tool-10.0.8.6 upload \
      harbor.talos.zebra-cloud.net/apic \
      --username <HARBOR_USER> \
      --password <HARBOR_PASSWORD> \
      --tls-verify=false

Note: Create a project called `apic` in Harbor first via the Harbor UI at
https://harbor.talos.zebra-cloud.net before running the upload.

The `--tls-verify=false` flag is needed for self-signed or internal CA certificates.

**Alternative: Upload to Docker Hub**

    docker run --rm apiconnect-image-tool-10.0.8.6 upload \
      docker.io/v1ad1m1r \
      --username v1ad1m1r \
      --password <DOCKERHUB_TOKEN>

Note: Docker Hub does not require the `--tls-verify=false` flag. Use a Docker Hub access token instead of your password for better security. Create an access token at https://hub.docker.com/settings/security

### 8d. Create registry pull secret

**For Harbor:**

    kubectl-1.30 create secret docker-registry harbor-registry-secret \
      --docker-server=harbor.talos.zebra-cloud.net \
      --docker-username=<HARBOR_USER> \
      --docker-password=<HARBOR_PASSWORD> \
      --docker-email=$IBM_USER \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

**For Docker Hub:**

    kubectl-1.30 create secret docker-registry dockerhub-registry-secret \
      --docker-server=docker.io \
      --docker-username=v1ad1m1r \
      --docker-password=<DOCKERHUB_TOKEN> \
      --docker-email=$IBM_USER \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

## Step 9: Update Operator IMAGE_REGISTRY (TODO)

Edit `apiconnect-operator/ibm-apiconnect.yaml` line ~898:

**For Harbor:**

    - name: IMAGE_REGISTRY
      value: harbor.talos.zebra-cloud.net/apic

**For Docker Hub:**

    - name: IMAGE_REGISTRY
      value: docker.io/v1ad1m1r

Then reapply:

    kubectl-1.30 apply -f apiconnect-operator/ibm-apiconnect.yaml --namespace apic

## Step 10: Deploy Management Subsystem (TODO - redo)

Delete the stuck deployment first:

    kubectl-1.30 delete managementcluster management -n apic

Edit `apiconnect-operator/helper_files/management_cr.yaml`:

**For Harbor:**
```yaml
apiVersion: management.apiconnect.ibm.com/v1beta1
kind: ManagementCluster
metadata:
  name: management
spec:
  version: 10.0.8.6
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.talos.zebra-cloud.net/apic
  profile: n1xc4.m16
  portal:
    admin:
      secretName: portal-admin-client
  analytics:
    ingestion:
      secretName: analytics-ingestion-client
  gateway:
    client:
      secretName: gateway-client-client
  cloudManagerEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: admin.apic.talos.zebra-cloud.net
      secretName: cm-endpoint
  apiManagerEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: manager.apic.talos.zebra-cloud.net
      secretName: apim-endpoint
  consumerCatalogEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: consumer-catalog.apic.talos.zebra-cloud.net
      secretName: consumer-catalog-endpoint
  platformAPIEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: api.apic.talos.zebra-cloud.net
      secretName: api-endpoint
  consumerAPIEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: consumer.apic.talos.zebra-cloud.net
      secretName: consumer-endpoint
  databaseVolumeClaimTemplate:
    storageClassName: nfs-ssd
  microServiceSecurity: certManager
  certManagerIssuer:
    name: selfsigning-issuer
    kind: Issuer
  license:
    accept: true
    use: production
    license: L-HTFS-UAXYM3
```

**For Docker Hub:**
```yaml
apiVersion: management.apiconnect.ibm.com/v1beta1
kind: ManagementCluster
metadata:
  name: management
spec:
  version: 10.0.8.6
  imagePullSecrets:
  - dockerhub-registry-secret
  imageRegistry: docker.io/v1ad1m1r
  profile: n1xc4.m16
  # ... rest of the configuration is identical to Harbor version
```

Note: The rest of the YAML configuration (endpoints, storage, etc.) remains the same.

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/management_cr.yaml -n apic

Wait for ready (can take 10-15 minutes):

    kubectl-1.30 get managementcluster management -n apic -w

## Step 11: Deploy Gateway Subsystem (TODO)

Edit `apiconnect-operator/helper_files/apigateway_cr.yaml` with these values:

**For Harbor:**

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.talos.zebra-cloud.net/apic` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.talos.zebra-cloud.net` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `$ADMIN_USER_SECRET` | `datapower-admin-credentials` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

**For Docker Hub:**

| Placeholder | Value |
|-------------|-------|
| `$SECRET_NAME` | `dockerhub-registry-secret` |
| `$DOCKER_REGISTRY` | `docker.io/v1ad1m1r` |

(All other values remain the same as Harbor)

Endpoints created:
- Gateway: `rgw.apic.talos.zebra-cloud.net`
- Gateway Manager: `rgwd.apic.talos.zebra-cloud.net`

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/apigateway_cr.yaml -n apic

## Step 12: Deploy Portal Subsystem (TODO)

Edit `apiconnect-operator/helper_files/portal_cr.yaml` with these values:

**For Harbor:**

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.talos.zebra-cloud.net/apic` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `$CONSUMER_CA_SECRET` | `ingress-ca` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.talos.zebra-cloud.net` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

**For Docker Hub:**

| Placeholder | Value |
|-------------|-------|
| `$SECRET_NAME` | `dockerhub-registry-secret` |
| `$DOCKER_REGISTRY` | `docker.io/v1ad1m1r` |

(All other values remain the same as Harbor)

Endpoints created:
- Portal Admin: `api.portal.apic.talos.zebra-cloud.net`
- Portal UI: `portal.apic.talos.zebra-cloud.net`

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/portal_cr.yaml -n apic

## Step 13: Deploy Analytics Subsystem (TODO)

Edit `apiconnect-operator/helper_files/analytics_cr.yaml` with these values:

**For Harbor:**

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.talos.zebra-cloud.net/apic` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.talos.zebra-cloud.net` |
| `$STORAGE_TYPE` | `shared` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `$DATA_VOLUME_SIZE` | `50Gi` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

**For Docker Hub:**

| Placeholder | Value |
|-------------|-------|
| `$SECRET_NAME` | `dockerhub-registry-secret` |
| `$DOCKER_REGISTRY` | `docker.io/v1ad1m1r` |

(All other values remain the same as Harbor)

Endpoints created:
- Analytics Ingestion: `ai.apic.talos.zebra-cloud.net`

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/analytics_cr.yaml -n apic

---

## Monitoring Deployment

    # Watch all pods
    kubectl-1.30 get pods -n apic -w

    # Check subsystem status
    kubectl-1.30 get managementcluster,gatewaycluster,portalcluster,analyticscluster -n apic

    # Check events
    kubectl-1.30 get events -n apic --sort-by='.lastTimestamp' | tail -30

    # Operator logs
    kubectl-1.30 logs deployment/ibm-apiconnect -n apic --tail=50
    kubectl-1.30 logs deployment/datapower-operator -n apic --tail=50

## Access URLs (after deployment)

| Service | URL |
|---------|-----|
| Cloud Manager | https://admin.apic.talos.zebra-cloud.net |
| API Manager | https://manager.apic.talos.zebra-cloud.net |
| Platform API | https://api.apic.talos.zebra-cloud.net |
| Consumer API | https://consumer.apic.talos.zebra-cloud.net |
| Consumer Catalog | https://consumer-catalog.apic.talos.zebra-cloud.net |
| Gateway | https://rgw.apic.talos.zebra-cloud.net |
| Gateway Manager | https://rgwd.apic.talos.zebra-cloud.net |
| Portal UI | https://portal.apic.talos.zebra-cloud.net |
| Portal Admin | https://api.portal.apic.talos.zebra-cloud.net |
| Analytics Ingestion | https://ai.apic.talos.zebra-cloud.net |

## DNS Requirements

All the above hostnames must resolve to the cluster's Traefik ingress IP.
Create a wildcard DNS record: `*.apic.talos.zebra-cloud.net` -> cluster ingress IP.

## Troubleshooting

### ImagePullBackOff
- Verify images were uploaded to Harbor: check Harbor UI project `apic`
- Verify `harbor-registry-secret` exists and has correct credentials
- Verify `imageRegistry` in CRs points to `harbor.talos.zebra-cloud.net/apic`

### Management stuck in Pending
- Check edb-operator pod is running (requires images in Harbor)
- Check operator logs: `kubectl-1.30 logs deployment/ibm-apiconnect -n apic --tail=100`

### CRD errors
- Re-apply with: `kubectl-1.30 apply --server-side --force-conflicts -f apiconnect-operator/ibm-apiconnect-crds.yaml`
