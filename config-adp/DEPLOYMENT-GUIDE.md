# IBM API Connect 10.0.8.6 - Kubernetes Deployment Guide

## Environment

| Item | Value |
|------|-------|
| Cluster | Kubernetes with Traefik ingress |
| Namespace | `apic` |
| Domain | `apic.adp.example.com` |
| Storage Class | `nfs-ssd` |
| Private Registry | `harbor.adp.example.com` |
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
      harbor.adp.example.com/apic \
      --username <HARBOR_USER> \
      --password <HARBOR_PASSWORD>

Note: Create a project called `apic` in Harbor first via the Harbor UI at
https://harbor.adp.example.com before running the upload.

If Harbor uses self-signed certs, add `--tls-verify=false`.

### 8d. Create Harbor pull secret

    kubectl-1.30 create secret docker-registry harbor-registry-secret \
      --docker-server=harbor.adp.example.com \
      --docker-username=<HARBOR_USER> \
      --docker-password=<HARBOR_PASSWORD> \
      --docker-email=$IBM_USER \
      --namespace apic \
      --dry-run=client -o yaml | kubectl-1.30 apply -f -

## Step 9: Update Operator IMAGE_REGISTRY (TODO)

Edit `apiconnect-operator/ibm-apiconnect.yaml` line ~898:

    - name: IMAGE_REGISTRY
      value: harbor.adp.example.com/apic

Then reapply:

    kubectl-1.30 apply -f apiconnect-operator/ibm-apiconnect.yaml --namespace apic

## Step 10: Deploy Management Subsystem (TODO - redo)

Delete the stuck deployment first:

    kubectl-1.30 delete managementcluster management -n apic

Edit `apiconnect-operator/helper_files/management_cr.yaml`:

```yaml
apiVersion: management.apiconnect.ibm.com/v1beta1
kind: ManagementCluster
metadata:
  name: management
spec:
  version: 10.0.8.6
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.adp.example.com/apic
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
    - name: admin.apic.adp.example.com
      secretName: cm-endpoint
  apiManagerEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: manager.apic.adp.example.com
      secretName: apim-endpoint
  consumerCatalogEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: consumer-catalog.apic.adp.example.com
      secretName: consumer-catalog-endpoint
  platformAPIEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: api.apic.adp.example.com
      secretName: api-endpoint
  consumerAPIEndpoint:
    ingressClassName: traefik
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: consumer.apic.adp.example.com
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

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/management_cr.yaml -n apic

Wait for ready (can take 10-15 minutes):

    kubectl-1.30 get managementcluster management -n apic -w

## Step 11: Deploy Gateway Subsystem (TODO)

Edit `apiconnect-operator/helper_files/apigateway_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.adp.example.com/apic` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.adp.example.com` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `$ADMIN_USER_SECRET` | `datapower-admin-credentials` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

Endpoints created:
- Gateway: `rgw.apic.adp.example.com`
- Gateway Manager: `rgwd.apic.adp.example.com`

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/apigateway_cr.yaml -n apic

## Step 12: Deploy Portal Subsystem (TODO)

Edit `apiconnect-operator/helper_files/portal_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.adp.example.com/apic` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `$CONSUMER_CA_SECRET` | `ingress-ca` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.adp.example.com` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

Endpoints created:
- Portal Admin: `api.portal.apic.adp.example.com`
- Portal UI: `portal.apic.adp.example.com`

Apply:

    kubectl-1.30 apply -f apiconnect-operator/helper_files/portal_cr.yaml -n apic

## Step 13: Deploy Analytics Subsystem (TODO)

Edit `apiconnect-operator/helper_files/analytics_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `10.0.8.6` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.adp.example.com/apic` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.adp.example.com` |
| `$STORAGE_TYPE` | `shared` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `$DATA_VOLUME_SIZE` | `50Gi` |
| `license.accept` | `true` |
| `license.license` | `L-HTFS-UAXYM3` |

Endpoints created:
- Analytics Ingestion: `ai.apic.adp.example.com`

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
| Cloud Manager | https://admin.apic.adp.example.com |
| API Manager | https://manager.apic.adp.example.com |
| Platform API | https://api.apic.adp.example.com |
| Consumer API | https://consumer.apic.adp.example.com |
| Consumer Catalog | https://consumer-catalog.apic.adp.example.com |
| Gateway | https://rgw.apic.adp.example.com |
| Gateway Manager | https://rgwd.apic.adp.example.com |
| Portal UI | https://portal.apic.adp.example.com |
| Portal Admin | https://api.portal.apic.adp.example.com |
| Analytics Ingestion | https://ai.apic.adp.example.com |

## DNS Requirements

All the above hostnames must resolve to the cluster's Traefik ingress IP.
Create a wildcard DNS record: `*.apic.adp.example.com` -> cluster ingress IP.

## Troubleshooting

### ImagePullBackOff
- Verify images were uploaded to Harbor: check Harbor UI project `apic`
- Verify `harbor-registry-secret` exists and has correct credentials
- Verify `imageRegistry` in CRs points to `harbor.adp.example.com/apic`

### Management stuck in Pending
- Check edb-operator pod is running (requires images in Harbor)
- Check operator logs: `kubectl-1.30 logs deployment/ibm-apiconnect -n apic --tail=100`

### CRD errors
- Re-apply with: `kubectl-1.30 apply --server-side --force-conflicts -f apiconnect-operator/ibm-apiconnect-crds.yaml`
