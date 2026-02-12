# IBM API Connect 12.1.0.1 - Talos Kubernetes Deployment Guide

## Environment

| Item | Value |
|------|-------|
| Cluster | Talos Kubernetes with nginx ingress |
| Namespace | `apic` |
| Domain | `apic.talos-nginx.zebra-cloud.net` |
| Storage Class | `nfs-ssd` (NFS with no_root_squash enabled) |
| Private Registry | `harbor.talos.zebra-cloud.net/apic` |
| Ingress Controller | nginx |
| Ingress LoadBalancer | `10.20.221.220` |
| Operator Version | 12.1.0.1 |
| Product Version | 12.1.0.1 |
| Profile | `n1xc4.m16` (single-node, smallest) |
| License | `L-SBZZ-CNR329` (webMethods Hybrid Integration) |
| License Use | `nonproduction` |

## Current Status

| Subsystem | Status | Pods | Ready |
|-----------|--------|------|-------|
| **Management** | ✅ Running | 21/21 | Yes |
| **Gateway** | ✅ Running | 1/1 | Yes |
| **Portal** | ✅ Running | 3/3 | Yes |
| **Analytics** | ✅ Running | 7/7 | Yes |

## Quick Start (Automated Deployment)

For automated deployment, use the included script:

```bash
# Full automated deployment
./deploy-apic.sh --wait

# Deploy specific subsystems only
./deploy-apic.sh --subsystems management,gateway --wait

# Skip prerequisites (if already installed)
./deploy-apic.sh --skip-prereqs --subsystems portal,analytics
```

The script will handle all prerequisite installation and subsystem deployment automatically.

---

## Manual Deployment Steps

If you prefer manual deployment or need to troubleshoot specific steps:

### Prerequisites

Before starting, ensure you have:

1. **.env file** with required credentials:
   ```bash
   REGISTRY_SERVER=harbor.talos.zebra-cloud.net
   REGISTRY_USERNAME=<your_harbor_username>
   REGISTRY_USERPWD=<your_harbor_password>
   IBM_ENTITLEMENT_KEY=<your_ibm_entitlement_key>
   APIC_ADMIN_PWD=<desired_admin_password>
   ```

2. **All APIC v12.1.0.1 images mirrored to Harbor** (see IMAGE-MIRRORING-GUIDE.md)

3. **NFS storage configured with `no_root_squash`** (critical for PostgreSQL)

4. **nginx ingress controller installed** with LoadBalancer service

---

## Step 1: Create Namespace

```bash
kubectl create namespace apic
```

## Step 2: Install cert-manager

```bash
kubectl apply -f cert-manager/cert-manager-1.19.2.yaml
kubectl wait --for=condition=Ready pods --all -n cert-manager --timeout=300s
```

## Step 3: Create Secrets

```bash
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
```

**Note:** The primary registry is Harbor (`harbor.talos.zebra-cloud.net/apic`). All API Connect images must be mirrored to Harbor before deployment.

## Step 4: Install CRDs

```bash
kubectl apply --server-side --force-conflicts -f 01-ibm-apiconnect-crds.yaml
```

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

```bash
/nfs/kubernetes *(rw,sync,no_subtree_check,no_root_squash,no_all_squash)
```

Then reload:

```bash
exportfs -ra
```

### 5b. Set nfs-ssd as Default Storage Class

API Connect creates multiple PVCs. To ensure all use NFS storage:

```bash
# Remove default from openebs-hostpath (if present)
kubectl patch storageclass openebs-hostpath \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'

# Make nfs-ssd the default
kubectl patch storageclass nfs-ssd \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify
kubectl get storageclass
```

Expected output: `nfs-ssd (default)`

## Step 6: Install Operators

**Important:** Operators must be configured to use Harbor registry before deployment.

### 6a. Update API Connect Operator for Harbor

Edit `02-ibm-apiconnect-operator.yaml`:
- Line ~290: Change `IMAGE_REGISTRY` value to `harbor.talos.zebra-cloud.net/apic`
- Line ~94: Change `imagePullSecrets` to `harbor-registry-secret`
- Update all operator image references to `harbor.talos.zebra-cloud.net/apic/...`

Apply:

```bash
kubectl apply -f 02-ibm-apiconnect-operator.yaml -n apic
```

### 6b. Update DataPower Operator for Harbor

Edit `03-ibm-datapower-operator.yaml`:
- Line ~381: Change operator image to `harbor.talos.zebra-cloud.net/apic/datapower-operator:1.17.0`
- Line ~411-415: Update environment variables:
  - `IBM_ENTITLED_REGISTRY=harbor.talos.zebra-cloud.net/apic`
  - `IBM_FREE_REGISTRY_DATAPOWER=harbor.talos.zebra-cloud.net/apic`
  - `IBM_FREE_REGISTRY_CPOPEN=harbor.talos.zebra-cloud.net/apic`
- Line ~12: Change `imagePullSecrets` from `datapower-docker-local-cred` to `harbor-registry-secret`

Apply:

```bash
kubectl apply -f 03-ibm-datapower-operator.yaml -n apic
```

### 6c. Wait for operators to be ready

```bash
kubectl wait --for=condition=Available deployment/ibm-apiconnect -n apic --timeout=300s
kubectl wait --for=condition=Available deployment/datapower-operator -n apic --timeout=300s
```

## Step 7: Install Ingress Issuer

```bash
kubectl apply -f 04-ingress-issuer.yaml -n apic
kubectl wait --for=condition=Ready certificate/ingress-ca -n apic --timeout=60s
```

## Step 8: Patch Service Accounts (CRITICAL)

All service accounts must be patched to use the Harbor registry secret for image pulls:

```bash
./patch-service-accounts.sh apic harbor-registry-secret
```

This ensures all pods created by the operators can pull images from Harbor.

---

**Note:** Before proceeding, ensure all API Connect v12.1.0.1 images have been mirrored to Harbor. See the separate "IMAGE-MIRRORING-GUIDE.md" for instructions.

## Step 9: Deploy Subsystems

### 9a. Deploy Management Subsystem

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
  imageRegistry: harbor.talos.zebra-cloud.net/apic
  profile: n1xc4.m16

  # Ingress endpoints with nginx
  cloudManagerEndpoint:
    ingressClassName: nginx
    annotations:
      cert-manager.io/issuer: ingress-issuer
    hosts:
    - name: admin.apic.talos-nginx.zebra-cloud.net
      secretName: cm-endpoint

  # Additional endpoints (apiManager, platformAPI, etc.) similarly configured

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
- **Ingress**: Uses nginx ingress class with `.apic.talos-nginx.zebra-cloud.net` domain

Apply:

```bash
kubectl apply -f 05-management-cr.yaml -n apic
```

Wait for ready (15-20 minutes):

```bash
kubectl get managementcluster management -n apic -w
```

Monitor deployment:

```bash
kubectl get pods -n apic -w
kubectl get managementcluster management -n apic -o yaml | grep -A 10 status:
```

### 9b. Deploy Gateway Subsystem

The Gateway CR is configured in `06-apigateway-cr.yaml`:

```yaml
apiVersion: gateway.apiconnect.ibm.com/v1beta1
kind: GatewayCluster
metadata:
  name: gwv6
spec:
  version: 12.1.0.1
  profile: n1xc4.m8
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.talos.zebra-cloud.net/apic

  gatewayEndpoint:
    ingressClassName: nginx
    hosts:
    - name: rgw.apic.talos-nginx.zebra-cloud.net
      secretName: gwv6-endpoint

  gatewayManagerEndpoint:
    ingressClassName: nginx
    hosts:
    - name: rgwd.apic.talos-nginx.zebra-cloud.net
      secretName: gwv6-manager-endpoint

  tokenManagementService:
    enabled: true
    storage:
      storageClassName: nfs-ssd
      volumeSize: 30Gi

  license:
    accept: true
    use: nonproduction
    license: L-SBZZ-CNR329
```

Endpoints created:
- Gateway: `rgw.apic.talos-nginx.zebra-cloud.net`
- Gateway Manager: `rgwd.apic.talos-nginx.zebra-cloud.net`

Apply:

```bash
kubectl apply -f 06-apigateway-cr.yaml -n apic
```

Wait for ready (10-15 minutes):

```bash
kubectl get gatewaycluster gwv6 -n apic -w
```

### 9c. Deploy Portal Subsystem

The Portal CR is configured in `07-portal-cr.yaml`:

```yaml
apiVersion: portal.apiconnect.ibm.com/v1beta1
kind: PortalCluster
metadata:
  name: portal
spec:
  version: 12.1.0.1
  profile: n1xc4.m16
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.talos.zebra-cloud.net/apic

  portalAdminEndpoint:
    ingressClassName: nginx
    hosts:
    - name: api.portal.apic.talos-nginx.zebra-cloud.net
      secretName: portal-admin

  portalUIEndpoint:
    ingressClassName: nginx
    hosts:
    - name: portal.apic.talos-nginx.zebra-cloud.net
      secretName: portal-web

  # All volume claims use nfs-ssd
  databaseVolumeClaimTemplate:
    storageClassName: nfs-ssd
    volumeSize: 64Gi

  license:
    accept: true
    use: nonproduction
    license: L-SBZZ-CNR329
```

Endpoints created:
- Portal Admin: `api.portal.apic.talos-nginx.zebra-cloud.net`
- Portal UI: `portal.apic.talos-nginx.zebra-cloud.net`

Apply:

```bash
kubectl apply -f 07-portal-cr.yaml -n apic
```

Wait for ready (15-20 minutes):

```bash
kubectl get portalcluster portal -n apic -w
```

**Note:** Portal uses MySQL Galera cluster which may take longer to initialize on NFS storage.

### 9d. Deploy Analytics Subsystem

The Analytics CR is configured in `08-analytics-cr.yaml`:

```yaml
apiVersion: analytics.apiconnect.ibm.com/v1beta1
kind: AnalyticsCluster
metadata:
  name: analytics
spec:
  version: 12.1.0.1
  profile: n1xc2.m16
  imagePullSecrets:
  - harbor-registry-secret
  imageRegistry: harbor.talos.zebra-cloud.net/apic

  ingestion:
    endpoint:
      ingressClassName: nginx
      hosts:
      - name: ai.apic.talos-nginx.zebra-cloud.net
        secretName: analytics-ai-endpoint

  storage:
    type: shared
    shared:
      volumeClaimTemplate:
        storageClassName: nfs-ssd
        volumeSize: 50Gi

  license:
    accept: true
    use: nonproduction
    license: L-SBZZ-CNR329
```

Endpoints created:
- Analytics Ingestion: `ai.apic.talos-nginx.zebra-cloud.net`

Apply:

```bash
kubectl apply -f 08-analytics-cr.yaml -n apic
```

Wait for ready (10-15 minutes):

```bash
kubectl get analyticscluster analytics -n apic -w
```

---

## Post-Deployment Configuration

### Registering the DataPower Gateway

After Management and Gateway subsystems are ready, register the gateway in Cloud Manager:

1. **Extract gateway client certificates:**

```bash
kubectl get secret gateway-client-client -n apic -o jsonpath='{.data.ca\.crt}' | base64 -d > /tmp/gateway-ca.crt
kubectl get secret gateway-client-client -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/gateway-client.crt
kubectl get secret gateway-client-client -n apic -o jsonpath='{.data.tls\.key}' | base64 -d > /tmp/gateway-client.key
```

2. **Log in to Cloud Manager:**
   - URL: https://admin.apic.talos-nginx.zebra-cloud.net/admin
   - Username: `admin`
   - Password: Get from secret or use password set in .env

3. **Register Gateway Service:**
   - Navigate to: Topology → Register Service → DataPower API Gateway
   - Management Endpoint: `https://rgwd.apic.talos-nginx.zebra-cloud.net/`
   - Upload the three certificate files from /tmp/
   - Save the service

4. **Associate Gateway with Catalog:**
   - Go to your Provider Organization → Catalog
   - Settings → Gateway Services
   - Add the registered gateway service

---

## Monitoring Deployment

```bash
# Watch all pods
kubectl get pods -n apic -w

# Check subsystem status
kubectl get managementcluster,gatewaycluster,portalcluster,analyticscluster -n apic

# Check ingresses
kubectl get ingress -n apic

# Check events
kubectl get events -n apic --sort-by='.lastTimestamp' | tail -30

# Operator logs
kubectl logs deployment/ibm-apiconnect -n apic --tail=50
kubectl logs deployment/datapower-operator -n apic --tail=50
kubectl logs deployment/edb-operator -n apic --tail=50
```

## Access URLs

| Service | URL |
|---------|-----|
| Cloud Manager | https://admin.apic.talos-nginx.zebra-cloud.net/admin |
| API Manager | https://manager.apic.talos-nginx.zebra-cloud.net |
| Platform API | https://api.apic.talos-nginx.zebra-cloud.net |
| Consumer API | https://consumer.apic.talos-nginx.zebra-cloud.net |
| Consumer Catalog | https://consumer-catalog.apic.talos-nginx.zebra-cloud.net |
| Gateway | https://rgw.apic.talos-nginx.zebra-cloud.net |
| Gateway Manager | https://rgwd.apic.talos-nginx.zebra-cloud.net |
| Portal UI | https://portal.apic.talos-nginx.zebra-cloud.net |
| Portal Admin | https://api.portal.apic.talos-nginx.zebra-cloud.net |
| Analytics Ingestion | https://ai.apic.talos-nginx.zebra-cloud.net |

## Default Credentials

```bash
# Get admin password
kubectl get secret management-admin-secret -n apic -o jsonpath='{.data.password}' | base64 -d
```

Default username: `admin`

## DNS Requirements

All the above hostnames must resolve to the nginx ingress LoadBalancer IP (`10.20.221.220`).

Create a wildcard DNS record: `*.apic.talos-nginx.zebra-cloud.net` → `10.20.221.220`

---

## Troubleshooting

### ImagePullBackOff
- Verify images were uploaded to Harbor: check Harbor UI project `apic`
- Verify `harbor-registry-secret` exists and has correct credentials
- Verify `imageRegistry` in CRs points to `harbor.talos.zebra-cloud.net/apic`
- For operators: verify operator YAML has been updated with Harbor registry
- **Run the service account patch script**: `./patch-service-accounts.sh apic harbor-registry-secret`

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

1. **Clean up evicted pods:**
   ```bash
   kubectl delete pod --field-selector=status.phase=Failed -n apic
   ```

2. **Delete specific pod to reschedule on different node:**
   ```bash
   kubectl delete pod <pod-name> -n apic
   ```

3. **Kubernetes will automatically reschedule on a node with more space**

### Portal MySQL Database Stuck Initializing

**Symptoms:**
- Portal database pod stuck at 0/2 or 1/2 Running
- MySQL process running but socket file not created
- Init process perpetually waiting

**Solution:**

Portal MySQL Galera cluster may take 5-10 minutes to initialize on NFS storage. If stuck for more than 15 minutes:

1. **Check pod logs:**
   ```bash
   kubectl logs portal-<id>-db-0 -n apic -c mysql
   ```

2. **Delete portal cluster and PVCs:**
   ```bash
   kubectl delete portalcluster portal -n apic
   kubectl delete pvc -l app.kubernetes.io/instance=portal -n apic
   ```

3. **Redeploy portal:**
   ```bash
   kubectl apply -f 07-portal-cr.yaml -n apic
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

### Service Account ImagePull Issues

**Problem:** Pods failing with ImagePullBackOff even though harbor-registry-secret exists

**Solution:** Service accounts need to be patched to reference the registry secret

```bash
./patch-service-accounts.sh apic harbor-registry-secret
```

This is a critical step and must be done after operators are deployed.

### Default Storage Class Issues

**Problem:** Some PVCs use `openebs-hostpath` instead of NFS

**Solution:** Set nfs-ssd as default storage class (see Step 5b) BEFORE deploying Management

### License Errors

**Error:** `License L-HTFS-UAXYM3 is invalid for the chosen version 12.1.0.1`

**Solution:** Use `L-SBZZ-CNR329` with `use: nonproduction` for v12.1.0.1

### Ingress Not Working

**Symptoms:**
- Ingresses created but returning 404 or 400 errors
- Cannot access Cloud Manager UI

**Solutions:**

1. **Verify nginx ingress controller is running:**
   ```bash
   kubectl get pods -n ingress-nginx
   kubectl get svc -n ingress-nginx
   ```

2. **Verify ingress class is set correctly:**
   ```bash
   kubectl get ingress -n apic
   ```
   All should show `nginx` in the CLASS column

3. **Verify DNS resolution:**
   ```bash
   nslookup admin.apic.talos-nginx.zebra-cloud.net
   ```
   Should resolve to nginx LoadBalancer IP: `10.20.221.220`

4. **Check cert-manager certificates:**
   ```bash
   kubectl get certificate -n apic
   ```
   All should be in Ready=True state

### Operator Logs

Check operator logs for detailed error information:

```bash
kubectl logs deployment/ibm-apiconnect -n apic --tail=100
kubectl logs deployment/datapower-operator -n apic --tail=100
kubectl logs deployment/edb-operator -n apic --tail=100
```

### CRD Errors

Re-apply with server-side apply:

```bash
kubectl apply --server-side --force-conflicts -f 01-ibm-apiconnect-crds.yaml
```

---

## Key Differences from Template Configuration

This deployment has been customized for the Talos environment:

| Item | Template Value | Talos Value |
|------|---------------|-------------|
| Registry | `harbor.adp.example.com/apic` | `harbor.talos.zebra-cloud.net/apic` |
| Ingress Class | `traefik` | `nginx` |
| Domain | `.apic.adp.example.com` | `.apic.talos-nginx.zebra-cloud.net` |
| LoadBalancer IP | N/A | `10.20.221.220` |

All custom resource files (05-08) have been updated to reflect these changes.

---

## Deployment Timeline

Typical deployment times:
- Prerequisites (Steps 1-7): 5-10 minutes
- Management subsystem: 15-20 minutes
- Gateway subsystem: 10-15 minutes
- Portal subsystem: 15-20 minutes (MySQL initialization)
- Analytics subsystem: 10-15 minutes

**Total: 55-80 minutes for full deployment**

Use the automated script with `--wait` flag to automatically wait for each subsystem to be ready.
