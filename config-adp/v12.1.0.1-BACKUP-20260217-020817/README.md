# IBM API Connect v12.1.0.1 Deployment Package

This package contains all necessary configuration files to deploy IBM API Connect v12.1.0.1 on Kubernetes with Contour ingress controller.

## Package Contents

```
v12.1.0.1/
├── 00-CONFIGURE.txt                    # Configuration replacement commands
├── 01-ibm-apiconnect-crds.yaml        # API Connect Custom Resource Definitions
├── 02-ibm-apiconnect-operator.yaml    # API Connect Operator
├── 03-ibm-datapower-operator.yaml     # DataPower Operator
├── 04-ingress-issuer.yaml             # cert-manager Issuers and Certificates
├── 05-management-cr.yaml              # Management Subsystem
├── 06-apigateway-cr.yaml              # Gateway Subsystem
├── 07-portal-cr.yaml                  # Portal Subsystem
├── 08-analytics-cr.yaml               # Analytics Subsystem
├── 09-contour-ingressclass.yaml       # Contour IngressClass
├── 10-httpproxy-management.yaml       # HTTPProxy for Management endpoints
├── 11-httpproxy-gateway.yaml          # HTTPProxy for Gateway endpoints
├── 12-httpproxy-portal.yaml           # HTTPProxy for Portal endpoints
├── 13-httpproxy-analytics.yaml        # HTTPProxy for Analytics endpoint
├── cert-manager/                      # cert-manager v1.13.2 deployment (45 MB amd64)
│   ├── README.md                      # cert-manager documentation
│   ├── QUICK-START.txt                # Quick deployment reference
│   ├── cert-manager-v1.13.2.yaml     # cert-manager manifest
│   └── images/                        # Pre-downloaded images (tar.gz, amd64)
│       ├── cert-manager-controller-v1.13.2.tar.gz (18 MB)
│       ├── cert-manager-cainjector-v1.13.2.tar.gz (13 MB)
│       └── cert-manager-webhook-v1.13.2.tar.gz (14 MB)
├── busybox/                           # Busybox utility for PVC cleanup (2.1 MB amd64)
│   ├── README.md                      # Busybox documentation
│   ├── busybox-dockerfile             # Dockerfile to build busybox
│   ├── clear-pvc-pod.yaml            # Pod manifest for PVC cleanup
│   └── busybox-1.37.tar.gz           # Pre-downloaded busybox image (2.1 MB, amd64)
├── README.md                          # This file
└── DEPLOYMENT-GUIDE.txt               # Step-by-step deployment commands
```

## Prerequisites

### 1. Kubernetes Cluster

- Kubernetes version: 1.24 - 1.30
- Minimum 3 worker nodes
- Total resources:
  - CPU: 24 cores minimum (48 cores recommended)
  - Memory: 96GB minimum (128GB recommended)
  - Storage: 500GB+ available via StorageClass

### 2. Required Software

- `kubectl` CLI configured for your cluster
- `docker` or `podman` for image management
- Access to container registry (Harbor, Docker Hub, Quay, etc.)

### 3. Pre-installed Components

**cert-manager** (v1.12+)

The cert-manager v1.13.2 manifest and images are included in the `cert-manager/` directory.

For online deployment (cluster has internet access):
```bash
kubectl apply -f cert-manager/cert-manager-v1.13.2.yaml
```

For offline/air-gapped deployment:

**Images are pre-downloaded** in `cert-manager/images/` directory (45 MB total, amd64).

```bash
# Transfer cert-manager/ directory to air-gapped environment
# Then extract, load and push images to your registry:
cd cert-manager/images
gunzip *.tar.gz

docker load -i cert-manager-controller-v1.13.2.tar
docker load -i cert-manager-cainjector-v1.13.2.tar
docker load -i cert-manager-webhook-v1.13.2.tar

export REGISTRY="harbor.example.com/apic"
docker tag quay.io/jetstack/cert-manager-controller:v1.13.2 $REGISTRY/cert-manager-controller:v1.13.2
docker tag quay.io/jetstack/cert-manager-cainjector:v1.13.2 $REGISTRY/cert-manager-cainjector:v1.13.2
docker tag quay.io/jetstack/cert-manager-webhook:v1.13.2 $REGISTRY/cert-manager-webhook:v1.13.2

docker push $REGISTRY/cert-manager-controller:v1.13.2
docker push $REGISTRY/cert-manager-cainjector:v1.13.2
docker push $REGISTRY/cert-manager-webhook:v1.13.2

cd ..
# Deploy (REGISTRY_PLACEHOLDER already replaced if you ran 00-CONFIGURE.txt)
kubectl apply -f cert-manager-v1.13.2.yaml
```

See `cert-manager/README.md` for detailed instructions and `cert-manager/QUICK-START.txt` for quick reference.

**Contour Ingress Controller** (v1.28+)

**IMPORTANT**: This package assumes Contour is **already installed** and configured.

To verify Contour installation:
```bash
# Check Contour pods
kubectl get pods -n projectcontour

# Expected: contour deployment and envoy daemonset pods running

# Check Contour LoadBalancer
kubectl get svc -n projectcontour envoy

# Expected: EXTERNAL-IP assigned

# Verify namespace is labeled for privileged pods
kubectl get namespace projectcontour -o yaml | grep pod-security
```

If Contour is not installed, please install it according to your environment's procedures.
For airgapped installations, Contour manifests and images must be prepared separately.

**PostgreSQL Operator** (EDB CloudNativePG)
- Automatically installed by API Connect operator

**Storage**
- StorageClass with dynamic provisioning
- Support for ReadWriteOnce (RWO) volumes
- Support for ReadWriteMany (RWX) volumes (for some Portal components)

### 4. Container Registry Setup

All API Connect images must be available in your container registry.

**IMPORTANT**: See `HARBOR-SETUP.md` for complete instructions on uploading API Connect images to Harbor.

Quick summary:
```bash
# Create Harbor project
# Upload images using apiconnect-image-tool
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  apiconnect-image-tool-12.1.0.1:latest upload \
  harbor.adp.example.com/apic \
  --username "<user>" \
  --password "<password>" \
  --tls-verify=false

# Verify ~40-50 images uploaded
```

Required images include:
```
harbor.adp.example.com/apic/ibm-apiconnect-management-lur:12.1.0.1-1591-...
harbor.adp.example.com/apic/ibm-apiconnect-management-apim:12.1.0.1-1591-...
harbor.adp.example.com/apic/datapower-api-gateway:12.1.0.1-1591-...
harbor.adp.example.com/apic/portal-admin:12.1.0.1-1591-...
harbor.adp.example.com/apic/portal-www:12.1.0.1-1591-...
harbor.adp.example.com/apic/analytics-ingestion:12.1.0.1-1591-...
... (and ~40-50 other API Connect images)
```

See `HARBOR-SETUP.md` for complete image list and troubleshooting.

### 5. DNS Configuration

**IMPORTANT**: See `DNS-ENTRIES.txt` for the complete list of all 10 required DNS entries.

You have two options:

**Option 1: Wildcard DNS (recommended)**
```
*.adp.example.com  →  <LoadBalancer-IP>
```

**Option 2: Individual DNS A records (if wildcard not available)**
```
admin.adp.example.com            →  <LoadBalancer-IP>
manager.adp.example.com          →  <LoadBalancer-IP>
api.adp.example.com              →  <LoadBalancer-IP>
consumer.adp.example.com         →  <LoadBalancer-IP>
consumer-catalog.adp.example.com →  <LoadBalancer-IP>
rgw.adp.example.com              →  <LoadBalancer-IP>
rgwd.adp.example.com             →  <LoadBalancer-IP>
api.portal.adp.example.com       →  <LoadBalancer-IP>
portal.adp.example.com           →  <LoadBalancer-IP>
ai.adp.example.com               →  <LoadBalancer-IP>
```

Get LoadBalancer IP after Contour installation:
```bash
kubectl get svc -n projectcontour envoy -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

See `DNS-ENTRIES.txt` for detailed DNS setup instructions, verification commands, and troubleshooting.

## Quick Start

### Step 1: Configure Environment

```bash
cd v12.1.0.1/

# Set your environment variables
export NAMESPACE="apic"
export DNS_DOMAIN="adp.example.com"
export INGRESS_CLASS="contour"
export STORAGE_CLASS="nfs-ssd"
export REGISTRY="harbor.example.com/apic"
export REGISTRY_SECRET="harbor-registry-secret"

# Run configuration replacements
find . -type f \( -name "*.yaml" -o -name "*.md" \) \
  -exec sed -i.bak \
    -e "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" \
    -e "s/DNS_PLACEHOLDER/$DNS_DOMAIN/g" \
    -e "s/INGRESS_CLASS_PLACEHOLDER/$INGRESS_CLASS/g" \
    -e "s/STORAGE_CLASS_PLACEHOLDER/$STORAGE_CLASS/g" \
    -e "s|REGISTRY_PLACEHOLDER|$REGISTRY|g" \
    -e "s/REGISTRY_SECRET_PLACEHOLDER/$REGISTRY_SECRET/g" \
  {} \;

# Verify configuration
grep -r "PLACEHOLDER" . --include="*.yaml"

# Clean up backup files
find . -type f -name "*.bak" -delete
```

For detailed configuration options, see **00-CONFIGURE.txt**.

### Step 2: Create Namespace and Registry Secret

```bash
# Create namespace
kubectl create namespace $NAMESPACE

# Create registry secret
kubectl create secret docker-registry $REGISTRY_SECRET \
  --namespace=$NAMESPACE \
  --docker-server=<REGISTRY_SERVER> \
  --docker-username=<REGISTRY_USER> \
  --docker-password=<REGISTRY_PASSWORD>
```

### Step 3: Deploy cert-manager Resources

```bash
# Apply cert-manager issuers
kubectl apply -f 04-ingress-issuer.yaml -n $NAMESPACE

# Wait for certificates to be ready
kubectl get certificates -n $NAMESPACE -w
```

### Step 4: Deploy Contour IngressClass

```bash
kubectl apply -f 09-contour-ingressclass.yaml
```

### Step 5: Deploy API Connect Operators

```bash
# Deploy CRDs
kubectl apply -f 01-ibm-apiconnect-crds.yaml

# Deploy API Connect Operator
kubectl apply -f 02-ibm-apiconnect-operator.yaml -n $NAMESPACE

# Deploy DataPower Operator
kubectl apply -f 03-ibm-datapower-operator.yaml -n $NAMESPACE

# Wait for operators to be ready
kubectl get pods -n $NAMESPACE -w
```

### Step 6: Deploy Subsystems

```bash
# Deploy Management (15-30 minutes)
kubectl apply -f 05-management-cr.yaml
kubectl get managementcluster -n $NAMESPACE -w

# Deploy Management HTTPProxy
kubectl apply -f 10-httpproxy-management.yaml

# Deploy Gateway (5-10 minutes)
kubectl apply -f 06-apigateway-cr.yaml
kubectl get gatewaycluster -n $NAMESPACE -w

# Deploy Gateway HTTPProxy
kubectl apply -f 11-httpproxy-gateway.yaml

# Deploy Portal (10-15 minutes)
kubectl apply -f 07-portal-cr.yaml
kubectl get portalcluster -n $NAMESPACE -w

# IMPORTANT: Update Portal www service name
export PORTAL_WWW_SERVICE=$(kubectl get service -n $NAMESPACE | grep www | awk '{print $1}')
sed -i.bak "s/PORTAL_WWW_SERVICE_PLACEHOLDER/$PORTAL_WWW_SERVICE/g" 12-httpproxy-portal.yaml

# Deploy Portal HTTPProxy
kubectl apply -f 12-httpproxy-portal.yaml

# Deploy Analytics (10-15 minutes)
kubectl apply -f 08-analytics-cr.yaml
kubectl get analyticscluster -n $NAMESPACE -w

# Deploy Analytics HTTPProxy
kubectl apply -f 13-httpproxy-analytics.yaml
```

### Step 7: Verify Deployment

```bash
# Check all subsystems
kubectl get managementcluster,gatewaycluster,portalcluster,analyticscluster -n $NAMESPACE

# Check HTTPProxy resources
kubectl get httpproxy -n $NAMESPACE

# Check all pods
kubectl get pods -n $NAMESPACE

# Test endpoints
curl -vk https://admin.$DNS_DOMAIN/admin
```

## Access Information

### Management Subsystem

- **Cloud Manager**: `https://admin.adp.example.com/admin`
  - Default username: `admin`
  - Initial password: Set via secret `management-admin-secret`

- **API Manager**: `https://manager.adp.example.com/manager`

- **Platform API**: `https://api.adp.example.com`

- **Consumer API**: `https://consumer.adp.example.com`

### Gateway Subsystem

- **Gateway**: `https://rgw.adp.example.com`
- **Gateway Manager**: `https://rgwd.adp.example.com`

### Portal Subsystem

- **Portal Director**: `https://api.portal.adp.example.com`
- **Portal Web**: `https://portal.adp.example.com`

### Analytics Subsystem

- **Analytics Ingestion**: `https://ai.adp.example.com`

## Default Credentials

### Cloud Manager Admin

```bash
# Get admin password
kubectl get secret -n $NAMESPACE management-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d && echo
```

To set a custom password before deployment:

```bash
kubectl create secret generic management-admin-secret \
  --namespace=$NAMESPACE \
  --from-literal=password='YourSecurePassword123!'
```

### DataPower Admin

```bash
# Get DataPower admin password
kubectl get secret -n $NAMESPACE datapower-admin-credentials \
  -o jsonpath='{.data.password}' | base64 -d && echo
```

To set a custom password:

```bash
kubectl create secret generic datapower-admin-credentials \
  --namespace=$NAMESPACE \
  --from-literal=password='YourDataPowerPassword123!'
```

## Architecture

### Network Flow

```
Internet
    ↓
DNS (*.adp.example.com)
    ↓
LoadBalancer (10.x.x.x)
    ↓
Contour Envoy (DaemonSet)
    ↓
HTTPProxy Resources (TLS termination)
    ↓
Backend Services (HTTPS/mTLS)
    ↓
API Connect Pods
```

### Subsystem Dependencies

```
Management (Core)
    ↓
Gateway ← → Analytics
    ↓
Portal
```

**Deployment Order:**
1. Management (must be first)
2. Gateway
3. Portal
4. Analytics

## Troubleshooting

### Common Issues

**1. Pods stuck in ImagePullBackOff**
```bash
# Check registry secret
kubectl get secret -n $NAMESPACE $REGISTRY_SECRET

# Verify image exists
docker pull $REGISTRY/ibm-apiconnect:12.1.0.1-1591-<hash>

# Check pod events
kubectl describe pod -n $NAMESPACE <pod-name>
```

**2. HTTPProxy shows "invalid" status**
```bash
# Check HTTPProxy details
kubectl describe httpproxy -n $NAMESPACE <httpproxy-name>

# Check Contour logs
kubectl logs -n projectcontour deployment/contour

# Verify backend service exists
kubectl get service -n $NAMESPACE <service-name>
```

**3. Certificate not ready**
```bash
# Check certificate status
kubectl get certificate -n $NAMESPACE
kubectl describe certificate -n $NAMESPACE <cert-name>

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

**4. PostgreSQL cluster not starting**
```bash
# Check PostgreSQL cluster
kubectl get cluster -n $NAMESPACE
kubectl describe cluster -n $NAMESPACE <cluster-name>

# Check storage
kubectl get pvc -n $NAMESPACE
```

**5. Subsystem stuck in "Pending" phase**
```bash
# Check subsystem conditions
kubectl get managementcluster -n $NAMESPACE -o yaml

# Check operator logs
kubectl logs -n $NAMESPACE deployment/ibm-apiconnect

# Check all pod statuses
kubectl get pods -n $NAMESPACE
```

### Diagnostic Commands

```bash
# Get all resources
kubectl get all -n $NAMESPACE

# Check events
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'

# Check resource usage
kubectl top nodes
kubectl top pods -n $NAMESPACE

# Export subsystem status
kubectl get managementcluster -n $NAMESPACE -o yaml > management-status.yaml

# Get operator version
kubectl get deployment -n $NAMESPACE ibm-apiconnect \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

## Maintenance

### Backup

**Management Database:**
```bash
kubectl exec -n $NAMESPACE <postgresql-pod> -- \
  pg_dump -U postgres -d apim > management-backup-$(date +%Y%m%d).sql
```

**Portal Database:**
```bash
kubectl exec -n $NAMESPACE <postgresql-pod> -- \
  pg_dump -U postgres -d portal > portal-backup-$(date +%Y%m%d).sql
```

### Reset Subsystem

See `busybox/README.md` for detailed PVC cleanup procedures.

**Example: Reset Management**
```bash
# Scale down Management
kubectl scale deployment -n $NAMESPACE --replicas=0 \
  management-apim management-lur management-ui

# Delete PostgreSQL cluster
kubectl delete cluster -n $NAMESPACE <management-cluster>

# Clear PVCs (use busybox utility)
# See busybox/README.md for detailed steps

# Delete PVCs
kubectl delete pvc -n $NAMESPACE <pvc-names>

# Re-apply Management CR
kubectl apply -f 05-management-cr.yaml
```

### Upgrade

```bash
# Update version in CR files
sed -i 's/version: 12.1.0.1/version: 12.1.0.2/g' 0*-cr.yaml

# Apply updated CRs
kubectl apply -f 05-management-cr.yaml
kubectl apply -f 06-apigateway-cr.yaml
kubectl apply -f 07-portal-cr.yaml
kubectl apply -f 08-analytics-cr.yaml

# Monitor upgrade
kubectl get managementcluster,gatewaycluster,portalcluster,analyticscluster -n $NAMESPACE -w
```

## Uninstallation

```bash
# Delete subsystems
kubectl delete analyticscluster -n $NAMESPACE analytics
kubectl delete portalcluster -n $NAMESPACE portal
kubectl delete gatewaycluster -n $NAMESPACE gwv6
kubectl delete managementcluster -n $NAMESPACE management

# Wait for deletion
kubectl wait --for=delete managementcluster -n $NAMESPACE management --timeout=600s

# Delete HTTPProxy resources
kubectl delete httpproxy -n $NAMESPACE --all

# Delete operators
kubectl delete -f 02-ibm-apiconnect-operator.yaml -n $NAMESPACE
kubectl delete -f 03-ibm-datapower-operator.yaml -n $NAMESPACE

# Delete CRDs (WARNING: This deletes all API Connect resources cluster-wide)
kubectl delete -f 01-ibm-apiconnect-crds.yaml

# Delete namespace
kubectl delete namespace $NAMESPACE
```

## Support and Documentation

### IBM Documentation

- [API Connect v12 Knowledge Center](https://www.ibm.com/docs/en/api-connect/12.x)
- [Installation Guide](https://www.ibm.com/docs/en/api-connect/12.x?topic=installing)
- [Configuration Reference](https://www.ibm.com/docs/en/api-connect/12.x?topic=reference-custom-resource-configuration)

### Community Resources

- [IBM API Connect Community](https://community.ibm.com/community/user/integration/communities/community-home?CommunityKey=2106cca0-a9f9-45c6-9b28-01a28f4ce947)
- [GitHub Issues](https://github.com/ibm-apiconnect)

### Getting Help

For issues or questions:
1. Check the Troubleshooting section above
2. Review IBM documentation
3. Search IBM Community forums
4. Contact IBM Support (for licensed customers)

## License

IBM API Connect v12.1.0.1
License: L-SBZZ-CNR329

Ensure you have accepted the license terms before deployment.

## Version History

- **v12.1.0.1-1591**: Initial deployment package
  - Includes all 4 subsystems (Management, Gateway, Portal, Analytics)
  - Contour ingress controller support with HTTPProxy
  - cert-manager integration for TLS
  - Busybox utility for PVC cleanup

## Notes

1. **Production Deployments**: This configuration uses `nonproduction` license. For production, update the `license.use` field in all CR files.

2. **High Availability**: For production HA deployments, increase replica counts and use appropriate profiles (e.g., n3xc16.m48 for Management).

3. **Security**:
   - Change default passwords immediately
   - Use proper TLS certificates (not self-signed) for production
   - Implement network policies
   - Configure RBAC appropriately

4. **Storage**: Ensure your storage class supports the required performance:
   - Management DB: 50 IOPS minimum
   - Analytics: 200 IOPS minimum for optimal performance

5. **Monitoring**: Consider deploying Prometheus/Grafana for monitoring API Connect metrics.

---

**Generated with IBM API Connect Deployment Package v1.0**
