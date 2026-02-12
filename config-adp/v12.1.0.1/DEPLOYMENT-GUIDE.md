# IBM API Connect 12.1.0.1 - Kubernetes Deployment Guide

## Environment

| Item | Value |
|------|-------|
| Cluster | Talos Kubernetes with Traefik ingress |
| Namespace | `apic` |
| Domain | `apic.adp.example.com` |
| Storage Class | `nfs-ssd` (NFS with no_root_squash enabled) |
| Private Registry | `harbor.adp.example.com/apic` |
| Operator Version | 12.1.0.1 |
| Product Version | 12.1.0.1 |
| Profile | `n1xc4.m16` (single-node, smallest) |
| License | `L-SBZZ-CNR329` (webMethods Hybrid Integration) |
| License Use | `nonproduction` |

## Current Status

| Step | Status |
|------|--------|
| 1. Namespace | ✓ DONE |
| 2. cert-manager | ✓ DONE |
| 3. Registry secrets | ✓ DONE (Harbor + IBM entitlement) |
| 4. CRDs | ✓ DONE |
| 5. Configure NFS storage | ✓ DONE (no_root_squash + default SC) |
| 6. Install operators (Harbor) | ✓ DONE (ibm-apiconnect, datapower, edb) |
| 7. Ingress issuer | ✓ DONE |
| 8. Management subsystem | **IN PROGRESS** (10/23 components ready) |
| 9. Gateway subsystem | **TODO** |
| 10. Portal subsystem | **TODO** |
| 11. Analytics subsystem | **TODO** |

**Note:** Images must be mirrored to Harbor before deployment (see IMAGE-MIRRORING-GUIDE.md)

---

## Step 1: Create Namespace (DONE)

    kubectl-1.30 create ns apic

## Step 2: Install cert-manager (DONE)

    kubectl-1.30 apply -f cert-manager/cert-manager-1.19.2.yaml
    kubectl-1.30 wait --for=condition=Ready pods --all -n cert-manager --timeout=300s

## Step 3: Create Secrets (DONE)

    source .env

    # Harbor registry secret (primary registry for all images)
    kubectl create secret docker-registry harbor-registry-secret \
      --docker-server=$REGISTRY_SERVER \
      --docker-username=$REGISTRY_USERNAME \
      --docker-password=$REGISTRY_USERPWD \
      --namespace apic

    # IBM Entitled Registry secret (for initial operator images if needed)
    kubectl create secret docker-registry apic-registry-secret \
      --docker-server=cp.icr.io \
      --docker-username=cp \
      --docker-password=$IBM_ENTITLEMENT_KEY \
      --namespace apic

    # DataPower admin credentials
    kubectl create secret generic datapower-admin-credentials \
      --from-literal=password=$APIC_ADMIN_PWD \
      --namespace apic

**Note:** The primary registry is Harbor (`harbor.adp.example.com/apic`). All API Connect images must be mirrored to Harbor before deployment.

## Step 4: Install CRDs (DONE)

    kubectl apply --server-side --force-conflicts \
      -f 01-ibm-apiconnect-crds.yaml

## Step 5: Configure NFS Storage (CRITICAL)

### 5a. Configure NFS Server with no_root_squash

PostgreSQL requires the ability to set file ownership to UID 26 (postgres user). NFS must be configured with `no_root_squash` to allow this.

**For QNAP NFS:**
1. Open QNAP Control Panel → Privileges → Shared Folders
2. Select the NFS export used by Kubernetes
3. Click "Edit Shared Folder Permissions" → "NFS Host Access"
4. Add or edit the rule for your Kubernetes subnet
5. Set permissions: **Read/Write**
6. Set Squash option: **No squash** (or "no_root_squash")
7. Apply changes

**For Linux NFS server (e.g., /etc/exports):**

    /nfs/kubernetes *(rw,sync,no_subtree_check,no_root_squash,no_all_squash)

Then reload:

    exportfs -ra

### 5b. Set nfs-ssd as Default Storage Class

API Connect creates multiple PVCs. To ensure all use NFS storage:

    # Remove default from openebs-hostpath (if present)
    kubectl patch storageclass openebs-hostpath \
      -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'

    # Make nfs-ssd the default
    kubectl patch storageclass nfs-ssd \
      -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

    # Verify
    kubectl get storageclass

Expected output: `nfs-ssd (default)`

## Step 6: Install Operators (DONE)

**Important:** Operators must be configured to use Harbor registry before deployment.

### 6a. Update API Connect Operator for Harbor

Edit `02-ibm-apiconnect-operator.yaml`:
- Line ~290: Change `IMAGE_REGISTRY` value to `harbor.adp.example.com/apic`
- Line ~94: Change `imagePullSecrets` to `harbor-registry-secret`
- Update all operator image references from placeholder to `harbor.adp.example.com/apic/...`

Apply:

    kubectl apply -f 02-ibm-apiconnect-operator.yaml -n apic

### 6b. Update DataPower Operator for Harbor

Edit `03-ibm-datapower-operator.yaml`:
- Line ~381: Change operator image to `harbor.adp.example.com/apic/datapower-operator:1.17.0`
- Line ~411-415: Update environment variables:
  - `IBM_ENTITLED_REGISTRY=harbor.adp.example.com/apic`
  - `IBM_FREE_REGISTRY_DATAPOWER=harbor.adp.example.com/apic`
  - `IBM_FREE_REGISTRY_CPOPEN=harbor.adp.example.com/apic`
- Line ~12: Change `imagePullSecrets` from `datapower-docker-local-cred` to `harbor-registry-secret`

Apply:

    kubectl apply -f 03-ibm-datapower-operator.yaml -n apic

### 6c. Wait for operators to be ready

    kubectl wait --for=condition=Available deployment/ibm-apiconnect -n apic --timeout=300s
    kubectl wait --for=condition=Available deployment/datapower-operator -n apic --timeout=300s

## Step 7: Install Ingress Issuer (DONE)

    kubectl apply -f 04-ingress-issuer.yaml -n apic
    kubectl wait --for=condition=Ready certificate/ingress-ca -n apic --timeout=60s

---

**Note:** Before proceeding, ensure all API Connect v12.1.0.1 images have been mirrored to Harbor. See the separate "IMAGE-MIRRORING-GUIDE.md" for instructions.

## Step 8: Deploy Management Subsystem (IN PROGRESS)

The Management CR is already configured in `05-management-cr.yaml`. Key configuration:

```yaml
apiVersion: management.apiconnect.ibm.com/v1beta1
kind: ManagementCluster
metadata:
  name: management
spec:
  version: 12.1.0.1
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.adp.example.com/apic
  profile: n1xc4.m16

  # Subsystem client secrets
  portal:
    admin:
      secretName: portal-admin-client
  analytics:
    ingestion:
      secretName: analytics-ingestion-client
  gateway:
    client:
      secretName: gateway-client-client
  devPortal:
    admin:
      secretName: devportal-admin-client
  wmAPIGateway:
    mgmt:
      secretName: wmapigateway-mgmt-client
  nanoGateway:
    mgmt:
      secretName: nano-gateway-mgmt-client
  federatedAPIManagement:
    admin:
      secretName: federatedapimanagement-admin-client

  # Ingress endpoints
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

  # Storage - only specify database data, others use default SC
  databaseVolumeClaimTemplate:
    storageClassName: nfs-ssd

  # Security
  microServiceSecurity: certManager
  certManagerIssuer:
    name: selfsigning-issuer
    kind: Issuer

  # License - CRITICAL: Use L-SBZZ-CNR329 for v12.1.0.1
  license:
    accept: true
    use: nonproduction
    license: L-SBZZ-CNR329
```

**Important Notes:**
- **License**: Use `L-SBZZ-CNR329` (IBM webMethods Hybrid Integration) with `use: nonproduction` for development/testing
- **Storage**: Only `databaseVolumeClaimTemplate` is specified; WAL and S3 proxy volumes use the default storage class (nfs-ssd)
- **NFS**: Ensure `no_root_squash` is configured on NFS server before deployment (see Step 5a)

Apply:

    kubectl apply -f 05-management-cr.yaml -n apic

Wait for ready (10-20 minutes):

    kubectl get managementcluster management -n apic -w

Monitor deployment:

    kubectl get pods -n apic -w
    kubectl get managementcluster management -n apic -o yaml | grep -A 10 status:

## Step 9: Deploy Gateway Subsystem (TODO)

Edit `apiconnect-operator/helper_files/apigateway_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `12.1.0.1` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.adp.example.com/apic` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.adp.example.com` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `$ADMIN_USER_SECRET` | `datapower-admin-credentials` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `license.accept` | `true` |
| `license.license` | `L-SBZZ-CNR329` |
| `license.use` | `nonproduction` |

Endpoints created:
- Gateway: `rgw.apic.adp.example.com`
- Gateway Manager: `rgwd.apic.adp.example.com`

Apply:

    kubectl apply -f apiconnect-operator/helper_files/apigateway_cr.yaml -n apic

## Step 10: Deploy Portal Subsystem (TODO)

Edit `apiconnect-operator/helper_files/portal_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `12.1.0.1` |
| `$PROFILE` | `n1xc4.m16` |
| `$SECRET_NAME` | `harbor-registry-secret` |
| `$DOCKER_REGISTRY` | `harbor.adp.example.com/apic` |
| `$PLATFORM_CA_SECRET` | `ingress-ca` |
| `$CONSUMER_CA_SECRET` | `ingress-ca` |
| `$INGRESS_CLASS` | `traefik` (uncomment) |
| `$STACK_HOST` | `apic.adp.example.com` |
| `$STORAGE_CLASS` | `nfs-ssd` |
| `license.accept` | `true` |
| `license.license` | `L-SBZZ-CNR329` |
| `license.use` | `nonproduction` |

Endpoints created:
- Portal Admin: `api.portal.apic.adp.example.com`
- Portal UI: `portal.apic.adp.example.com`

Apply:

    kubectl apply -f apiconnect-operator/helper_files/portal_cr.yaml -n apic

## Step 11: Deploy Analytics Subsystem (TODO)

Edit `apiconnect-operator/helper_files/analytics_cr.yaml` with these values:

| Placeholder | Value |
|-------------|-------|
| `$APP_PRODUCT_VERSION` | `12.1.0.1` |
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
| `license.license` | `L-SBZZ-CNR329` |
| `license.use` | `nonproduction` |

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
- For operators: verify operator YAML has been updated with Harbor registry

### PostgreSQL Init Fails: "data directory has wrong ownership"

**Error:**
```
FATAL: data directory "/var/lib/postgresql/data/pgdata" has wrong ownership
HINT: The server must be started by the user that owns the data directory.
```

**Root Cause:** NFS `root_squash` prevents PostgreSQL from setting ownership to UID 26 (postgres user).

**Solution:**

1. **Configure NFS with no_root_squash** (see Step 5a)

2. **Delete failed PVCs and cluster:**
   ```bash
   kubectl delete managementcluster management -n apic
   kubectl delete pvc --all -n apic
   ```

3. **Redeploy Management:**
   ```bash
   kubectl apply -f 05-management-cr.yaml -n apic
   ```

### PostgreSQL Pod Evicted: "low on resource: ephemeral-storage"

**Error:**
```
The node was low on resource: ephemeral-storage. Threshold quantity: 7853624836, available: 7488688Ki
```

**Root Cause:** Node has insufficient ephemeral storage (local disk space).

**Solution:**

1. **Delete failed pod to reschedule on different node:**
   ```bash
   kubectl delete pod <pod-name> -n apic
   ```

2. **Kubernetes will automatically reschedule on a node with more space**

3. **Clean up evicted pods:**
   ```bash
   kubectl delete pod --field-selector=status.phase=Failed -n apic
   ```

### Management Stuck in Pending (EDB Cluster Issues)

**Symptoms:**
- Management cluster status: "Pending"
- EDB cluster shows "dangling PVCs" or "unrecoverable"
- Database initialization job fails repeatedly

**Solution:**

1. **Check EDB cluster status:**
   ```bash
   kubectl get cluster -n apic
   kubectl get cluster <cluster-name> -n apic -o yaml | grep -A 20 status
   ```

2. **If cluster is unrecoverable, delete and redeploy:**
   ```bash
   kubectl delete managementcluster management -n apic
   # Wait for all resources to be cleaned up
   kubectl get pvc -n apic
   # Delete any remaining PVCs
   kubectl delete pvc --all -n apic
   # Redeploy
   kubectl apply -f 05-management-cr.yaml -n apic
   ```

### Default Storage Class Issues

**Problem:** Some PVCs use `openebs-hostpath` instead of NFS

**Solution:** Set nfs-ssd as default storage class (see Step 5b) BEFORE deploying Management

### License Errors

**Error:** `License L-HTFS-UAXYM3 is invalid for the chosen version 12.1.0.1`

**Solution:** Use `L-SBZZ-CNR329` with `use: nonproduction` for v12.1.0.1

### Operator Logs

Check operator logs for detailed error information:

    kubectl logs deployment/ibm-apiconnect -n apic --tail=100
    kubectl logs deployment/datapower-operator -n apic --tail=100
    kubectl logs deployment/edb-operator -n apic --tail=100

### CRD Errors

Re-apply with server-side apply:

    kubectl apply --server-side --force-conflicts -f 01-ibm-apiconnect-crds.yaml
