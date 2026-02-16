# Harbor Registry Setup for IBM API Connect v12.1.0.1

This guide explains how to load API Connect images to Harbor registry for airgapped deployment.

================================================================================

## Overview

IBM API Connect v12.1.0.1 requires approximately **40-50 container images** to be available in your Harbor registry before deployment.

This guide covers:
1. Harbor project setup
2. Loading images using apiconnect-image-tool
3. Manual image upload (alternative method)
4. Verifying images in Harbor
5. Troubleshooting

================================================================================

## Prerequisites

Before starting, ensure you have:

- [ ] Harbor registry accessible (harbor.adp.example.com)
- [ ] Harbor admin or project admin credentials
- [ ] API Connect v12.1.0.1 image bundle (tar files or loaded in local docker)
- [ ] apiconnect-image-tool-12.1.0.1:latest image available
- [ ] Docker or Podman installed on the machine with images
- [ ] Network access to Harbor from the machine

================================================================================

## Method 1: Using API Connect Image Tool (Recommended)

The API Connect Image Tool is the official IBM tool for uploading images to registries.

### Step 1: Verify apiconnect-image-tool Image

Check if the image tool is available:

```bash
docker images | grep apiconnect-image-tool

# Expected output:
# apiconnect-image-tool-12.1.0.1   latest   <image-id>   <size>
```

If not available, load it from the image bundle:
```bash
# If you have the tar file
docker load -i apiconnect-image-tool-12.1.0.1.tar
```

### Step 2: Verify API Connect Images are Loaded

All API Connect images must be loaded in local docker:

```bash
docker images | grep -E "ibm-apiconnect|datapower|portal|analytics"

# You should see approximately 40-50 images like:
# ibm-apiconnect-management-lur           12.1.0.1-1591-...
# ibm-apiconnect-management-apim          12.1.0.1-1591-...
# datapower-api-gateway                   12.1.0.1-1591-...
# portal-admin                            12.1.0.1-1591-...
# portal-www                              12.1.0.1-1591-...
# analytics-ingestion                     12.1.0.1-1591-...
# ... (and many more)
```

If images are not loaded, load them from tar files:
```bash
# Load all image tar files
for tarfile in *.tar; do
  echo "Loading $tarfile..."
  docker load -i "$tarfile"
done
```

### Step 3: Create Harbor Project

**Option A: Using Harbor Web UI**

1. Login to Harbor: https://harbor.adp.example.com
2. Navigate to Projects
3. Click "NEW PROJECT"
4. Project Name: `apic`
5. Access Level: Private (recommended)
6. Click OK

**Option B: Using Harbor API**

```bash
# Set Harbor credentials
export HARBOR_URL="harbor.adp.example.com"
export HARBOR_USER="admin"
export HARBOR_PASSWORD="Harbor12345"

# Create project
curl -k -X POST "https://${HARBOR_URL}/api/v2.0/projects" \
  -H "Content-Type: application/json" \
  -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  -d '{
    "project_name": "apic",
    "metadata": {
      "public": "false"
    }
  }'
```

**Option C: Using Kubernetes (if Harbor deployed in K8s)**

```bash
kubectl exec -it <harbor-core-pod> -n harbor -- \
  /harbor/harbor-cli project create apic
```

### Step 4: Upload Images Using apiconnect-image-tool

Now upload all images to Harbor using the image tool:

```bash
# Set your Harbor registry details
export HARBOR_URL="harbor.adp.example.com"
export HARBOR_PROJECT="apic"
export HARBOR_USER="<apic-harbor-user>"
export HARBOR_PASSWORD="<apic-harbor-password>"

# Upload all API Connect images
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  apiconnect-image-tool-12.1.0.1:latest upload \
  ${HARBOR_URL}/${HARBOR_PROJECT} \
  --username "${HARBOR_USER}" \
  --password "${HARBOR_PASSWORD}" \
  --tls-verify=false
```

**Important Notes**:
- The tool automatically detects all API Connect images in local docker
- Upload process can take 30-60 minutes depending on network speed
- `--tls-verify=false` disables TLS verification (use only if Harbor uses self-signed cert)
- For production with valid certs, remove `--tls-verify=false`

### Step 5: Monitor Upload Progress

The tool will output progress for each image:

```
Uploading image: ibm-apiconnect-management-lur:12.1.0.1-1591-abc123
✓ Successfully pushed ibm-apiconnect-management-lur:12.1.0.1-1591-abc123

Uploading image: ibm-apiconnect-management-apim:12.1.0.1-1591-def456
✓ Successfully pushed ibm-apiconnect-management-apim:12.1.0.1-1591-def456

... (continues for all images)
```

### Step 6: Verify Upload Completion

After upload completes, verify image count:

```bash
# Count images in Harbor project
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq '. | length'

# Expected: ~40-50 repositories
```

Or verify via Harbor Web UI:
1. Login to Harbor
2. Navigate to Projects > apic
3. Click on Repositories
4. Verify you see all API Connect images

================================================================================

## Method 2: Manual Upload (Alternative)

If apiconnect-image-tool is not available, you can manually tag and push images.

### Step 1: Login to Harbor

```bash
export HARBOR_URL="harbor.adp.example.com"
export HARBOR_USER="admin"
export HARBOR_PASSWORD="Harbor12345"

docker login ${HARBOR_URL} -u ${HARBOR_USER} -p ${HARBOR_PASSWORD}
```

### Step 2: Tag and Push Images

Tag and push each image manually:

```bash
# Get list of all API Connect images
docker images --format "{{.Repository}}:{{.Tag}}" | \
  grep -E "ibm-apiconnect|datapower|portal|analytics" > apic-images.txt

# Read image list and tag/push each
while IFS= read -r image; do
  echo "Processing: $image"

  # Extract image name and tag
  image_name=$(echo $image | cut -d: -f1 | awk -F'/' '{print $NF}')
  image_tag=$(echo $image | cut -d: -f2)

  # Tag for Harbor
  docker tag ${image} ${HARBOR_URL}/apic/${image_name}:${image_tag}

  # Push to Harbor
  docker push ${HARBOR_URL}/apic/${image_name}:${image_tag}

  echo "✓ Pushed ${image_name}:${image_tag}"
  echo ""
done < apic-images.txt
```

This method is slower but works when image tool is unavailable.

================================================================================

## Method 3: Using Skopeo (Alternative for Airgapped)

Skopeo can copy images without loading them to docker:

```bash
# Install skopeo (if not available)
# Ubuntu/Debian: apt-get install skopeo
# RHEL/CentOS: yum install skopeo

# Copy image from tar to Harbor
skopeo copy \
  docker-archive:ibm-apiconnect-management-lur-12.1.0.1.tar \
  docker://harbor.adp.example.com/apic/ibm-apiconnect-management-lur:12.1.0.1-1591-abc123 \
  --dest-creds ${HARBOR_USER}:${HARBOR_PASSWORD} \
  --dest-tls-verify=false
```

================================================================================

## Verification

After uploading images, perform these verification steps:

### 1. Check Image Count

```bash
# Via Harbor API
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq '. | length'

# Expected: 40-50 repositories
```

### 2. List All Images

```bash
# List all images in apic project
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq -r '.[].name'

# Expected output (sample):
# apic/ibm-apiconnect-management-lur
# apic/ibm-apiconnect-management-apim
# apic/datapower-api-gateway
# apic/portal-admin
# apic/portal-www
# ... (and more)
```

### 3. Verify Specific Images

Check that critical images are present:

```bash
# Management images
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq -r '.[].name' | grep management

# Gateway images
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq -r '.[].name' | grep datapower

# Portal images
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq -r '.[].name' | grep portal

# Analytics images
curl -k -s -u "${HARBOR_USER}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_URL}/api/v2.0/projects/apic/repositories" | \
  jq -r '.[].name' | grep analytics
```

### 4. Test Image Pull

Test pulling an image from Harbor:

```bash
docker pull ${HARBOR_URL}/apic/ibm-apiconnect-management-lur:12.1.0.1-1591-<hash>
```

If successful, Harbor is correctly configured.

================================================================================

## Required Images Checklist

Below is a checklist of key images required for each subsystem.

### Management Subsystem (~15-20 images)
- [ ] ibm-apiconnect-management-lur
- [ ] ibm-apiconnect-management-juhu
- [ ] ibm-apiconnect-management-apimanager-ui
- [ ] ibm-apiconnect-management-apim
- [ ] ibm-apiconnect-management-client-downloads-server
- [ ] ibm-apiconnect-management-db-backup
- [ ] ibm-apiconnect-management-ldap
- [ ] ibm-apiconnect-management-turnstile
- [ ] ibm-apiconnect-management-taskmanager
- [ ] postgresql (EDB CloudNativePG)
- [ ] postgres-ha-pgbouncer
- [ ] postgres-ha-keepalived

### Gateway Subsystem (~5 images)
- [ ] datapower-api-gateway
- [ ] datapower-monitor
- [ ] ibm-apiconnect-gateway-...

### Portal Subsystem (~10 images)
- [ ] portal-admin
- [ ] portal-www
- [ ] portal-db
- [ ] portal-dbproxy
- [ ] postgresql
- [ ] nginx
- [ ] portal-migration

### Analytics Subsystem (~10 images)
- [ ] analytics-ingestion
- [ ] analytics-client
- [ ] analytics-mq-kafka
- [ ] analytics-mq-zookeeper
- [ ] analytics-storage
- [ ] analytics-proxy

### Operators (~3 images)
- [ ] ibm-apiconnect-operator
- [ ] datapower-operator
- [ ] postgres-operator (EDB CloudNativePG)

### Additional Images
- [ ] busybox (for utilities)
- [ ] kubectl (for operator)

**Note**: Image names may vary slightly. The exact list is in the API Connect image bundle.

================================================================================

## Troubleshooting

### Issue: "unauthorized: authentication required"

**Solution**: Login to Harbor first:
```bash
docker login harbor.adp.example.com -u admin -p Harbor12345
```

### Issue: "failed to push image: denied"

**Possible causes**:
1. Project doesn't exist in Harbor
2. User doesn't have push permissions
3. Project is set to public but user isn't member

**Solution**:
```bash
# Verify project exists
curl -k -s -u "admin:Harbor12345" \
  "https://harbor.adp.example.com/api/v2.0/projects" | \
  jq -r '.[].name'

# Create project if missing (see Step 3 above)

# Add user to project with push permissions via Harbor UI:
# Projects > apic > Members > +USER
```

### Issue: "TLS verification error"

**Solution**: Use `--tls-verify=false` or add Harbor CA to system trust:

```bash
# Temporary: disable TLS verification
docker run --rm apiconnect-image-tool-12.1.0.1:latest upload \
  harbor.adp.example.com/apic \
  --username "admin" \
  --password "Harbor12345" \
  --tls-verify=false

# Permanent: add Harbor CA certificate
# 1. Get Harbor CA cert
# 2. Add to /etc/docker/certs.d/harbor.adp.example.com/ca.crt
# 3. Restart docker
```

### Issue: "Image not found in docker"

**Solution**: Load images first:
```bash
# If images are in tar files
for tarfile in *.tar; do
  docker load -i "$tarfile"
done

# Verify images loaded
docker images | grep -E "ibm-apiconnect|datapower|portal|analytics"
```

### Issue: "Push takes too long / times out"

**Possible causes**:
1. Network bandwidth too low
2. Harbor disk space full
3. Too many images pushed simultaneously

**Solution**:
```bash
# Check Harbor disk space (if you have access)
df -h /data

# Push images in batches (manual method)
# Split image list into smaller batches

# Increase docker timeout
# Edit /etc/docker/daemon.json:
{
  "max-concurrent-uploads": 2,
  "registry-timeout": 600
}
# Restart docker: systemctl restart docker
```

### Issue: "Wrong architecture (arm64 vs amd64)"

**Solution**: Verify image architecture before upload:
```bash
docker inspect <image> --format='{{.Architecture}}'

# Should return: amd64
```

If wrong architecture, re-download correct images for your cluster nodes.

================================================================================

## Post-Upload Steps

After all images are uploaded to Harbor:

1. **Create Registry Secret in Kubernetes**:
   ```bash
   kubectl create secret docker-registry harbor-registry-secret \
     --namespace=apic \
     --docker-server=harbor.adp.example.com \
     --docker-username=<harbor-user> \
     --docker-password=<harbor-password>
   ```

2. **Configure Deployment Package**:
   - Run `00-CONFIGURE.txt` commands
   - Set `REGISTRY="harbor.adp.example.com/apic"`
   - Set `REGISTRY_SECRET="harbor-registry-secret"`

3. **Verify Configuration**:
   ```bash
   grep "imageRegistry:" 05-management-cr.yaml
   # Should show: imageRegistry: harbor.adp.example.com/apic
   ```

4. **Proceed with Deployment**:
   - Follow `DEPLOYMENT-GUIDE.txt`

================================================================================

## Additional Resources

- IBM API Connect Documentation: https://www.ibm.com/docs/en/api-connect/12.x
- Harbor Documentation: https://goharbor.io/docs/
- API Connect Image Tool: Check IBM documentation for latest version

================================================================================

## Security Notes

- Store Harbor credentials securely (use secrets management)
- Use TLS verification in production (`--tls-verify=true`)
- Limit Harbor project access to authorized users only
- Regularly scan images for vulnerabilities using Harbor's built-in scanning
- Use strong passwords for Harbor admin account
- Enable content trust (image signing) in Harbor for production

================================================================================

## Summary Commands

Quick reference for experienced users:

```bash
# 1. Create Harbor project (via UI or API)

# 2. Upload images using image tool
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  apiconnect-image-tool-12.1.0.1:latest upload \
  harbor.adp.example.com/apic \
  --username "<user>" \
  --password "<password>" \
  --tls-verify=false

# 3. Verify upload
curl -k -s -u "user:password" \
  "https://harbor.adp.example.com/api/v2.0/projects/apic/repositories" | \
  jq '. | length'

# 4. Create K8s secret
kubectl create secret docker-registry harbor-registry-secret \
  --namespace=apic \
  --docker-server=harbor.adp.example.com \
  --docker-username=<user> \
  --docker-password=<password>

# 5. Configure deployment package
export REGISTRY="harbor.adp.example.com/apic"
export REGISTRY_SECRET="harbor-registry-secret"
# Run 00-CONFIGURE.txt commands

# 6. Deploy API Connect
# Follow DEPLOYMENT-GUIDE.txt
```

================================================================================
