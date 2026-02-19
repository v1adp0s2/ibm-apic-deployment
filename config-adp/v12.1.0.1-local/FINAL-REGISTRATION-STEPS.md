# IBM API Connect v12.1.0.1 - Service Registration (TESTED)

## Prerequisites Verified

- apic CLI location: `/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/config-adp/v12.1.0.1-local/apic-toolkit/apic`
- Management endpoint: `api.apic.talos-pc.zebra-cloud.net`
- Admin password: `Admin123!`
- All services use INTERNAL endpoints (`.apic.svc`)

---

## Method 1: Cloud Manager UI (RECOMMENDED - Simpler)

Since gateway registration via CLI requires complex TLS server profile setup, use Cloud Manager UI:

### Access Cloud Manager

Open: `https://admin.apic.talos-pc.zebra-cloud.net/admin`
- Username: `admin`
- Password: `Admin123!`

### Register Gateway Service

1. Navigate to: **Resources → Gateway Services → Register Service**
2. Select: **DataPower API Gateway**
3. Fill in:
   - **Title:** `DataPower Gateway`
   - **Summary:** `Internal DataPower Gateway`
   - **Management Endpoint:** `https://gwv6.apic.svc:443`
   - **API Invocation Endpoint:** `https://gwv6.apic.svc:443`
4. Click **Save**

**Note:** Use `gwv6.apic.svc` (NOT `gwv6-datapower.apic.svc`) because the certificate SANs only include `gwv6.apic.svc`. Port 443 on this service forwards to the management port 3000.

### Register Portal Service

1. Navigate to: **Resources → Portal Services → Register Service**
2. Fill in:
   - **Title:** `Developer Portal`
   - **Portal Director Endpoint:** `https://portal-nginx.apic.svc:8443`
   - **Portal Web Endpoint:** `https://portal.apic.svc:443`
3. Click **Save**

### Register Analytics Service

1. Navigate to: **Resources → Analytics Services → Register Service**
2. Fill in:
   - **Title:** `Analytics Service`
   - **Analytics Endpoint:** `https://analytics-ingestion-https.apic.svc:443`
3. Click **Save**

---

## Method 2: apic CLI (Advanced - Requires TLS Setup)

### Step 1: Login (TESTED - WORKING)

```bash
export APIC=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/config-adp/v12.1.0.1-local/apic-toolkit/apic
export SERVER="api.apic.talos-pc.zebra-cloud.net"
export ORG="admin"
export AZ="availability-zone-default"

$APIC login \
  --server $SERVER \
  --username admin \
  --password 'Admin123!' \
  --realm admin/default-idp-1 \
  --insecure-skip-tls-verify
```

**Expected output:** `Logged into api.apic.talos-pc.zebra-cloud.net successfully`

### Step 2: Create Truststore (TESTED - WORKING)

```bash
# Extract CA certificate
export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml
mkdir -p ~/apic-certs

kubectl get secret -n apic ingress-ca \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > ~/apic-certs/ingress-ca.pem

# Create truststore YAML
cat > ~/apic-certs/truststore.yaml <<'EOF'
name: internal-ca-truststore
title: Internal CA Truststore
summary: Truststore containing internal CA certificate
truststore: |
EOF

cat ~/apic-certs/ingress-ca.pem | sed 's/^/  /' >> ~/apic-certs/truststore.yaml

# Upload truststore
$APIC truststores:create \
  --server $SERVER \
  --org $ORG \
  --insecure-skip-tls-verify \
  ~/apic-certs/truststore.yaml
```

**Save the truststore URL from output** (e.g., `https://api.apic.talos-pc.zebra-cloud.net/api/orgs/.../truststores/...`)

### Step 3: Create TLS Client Profile (TESTED - WORKING)

```bash
# Replace TRUSTSTORE_URL with the URL from Step 2
export TRUSTSTORE_URL="<truststore-url-from-step-2>"

cat > ~/apic-certs/tls-client-profile.yaml <<EOF
name: internal-ca-trust
title: Internal CA Trust Profile
summary: TLS profile for internal service communication
truststore_url: $TRUSTSTORE_URL
EOF

$APIC tls-client-profiles:create \
  --server $SERVER \
  --org $ORG \
  --insecure-skip-tls-verify \
  ~/apic-certs/tls-client-profile.yaml
```

**Save the TLS client profile URL from output**

### Step 4: Gateway Registration (REQUIRES TLS SERVER PROFILE)

**Challenge:** Gateway registration requires:
1. TLS Server Profile with SNI configuration
2. TLS Server Profile requires Keystore (server cert + private key)
3. Creating keystore requires extracting gateway's certificate and private key

**Recommendation:** Use Cloud Manager UI (Method 1) for Gateway registration.

**For advanced users:** If you need CLI registration, you must:

1. Extract gateway certificate and key from Kubernetes secret
2. Create keystore with gateway cert + key
3. Create TLS server profile referencing keystore
4. Register gateway with SNI pointing to TLS server profile

### Step 5: Portal Registration (Simple - No TLS Server Profile Needed)

```bash
cat > ~/apic-certs/portal-service.yaml <<'EOF'
name: developer-portal
title: Developer Portal
endpoint: https://portal-nginx.apic.svc:8443
web_endpoint_base: https://portal.apic.svc:443
EOF

$APIC portal-services:create \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  ~/apic-certs/portal-service.yaml
```

### Step 6: Analytics Registration (Simple)

```bash
cat > ~/apic-certs/analytics-service.yaml <<'EOF'
name: analytics-service
title: Analytics Service
endpoint: https://analytics-ingestion-https.apic.svc:443
EOF

$APIC analytics-services:create \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  ~/apic-certs/analytics-service.yaml
```

### Step 7: Verify Registration

```bash
# Check gateway (if registered)
$APIC gateway-services:get \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  datapower-gateway

# Check portal
$APIC portal-services:get \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  developer-portal

# Check analytics
$APIC analytics-services:get \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  analytics-service
```

### Step 8: Logout

```bash
$APIC logout --server $SERVER --insecure-skip-tls-verify
```

---

## Summary of Internal Service Endpoints

These are the **internal cluster service endpoints** used for registration:

| Service | Type | Internal Endpoint | Port | Notes |
|---------|------|-------------------|------|-------|
| **Gateway** | Management | `gwv6.apic.svc` | 443 | Forwards to port 3000 internally |
| **Gateway** | API Invocation | `gwv6.apic.svc` | 443 | Same service, same port |
| **Portal** | Director | `portal-nginx.apic.svc` | 8443 |
| **Portal** | Web | `portal.apic.svc` | 443 |
| **Analytics** | Ingestion | `analytics-ingestion-https.apic.svc` | 443 |

---

## What Was Successfully Tested

1. apic login with external endpoint → WORKING
2. Truststore creation → WORKING
3. TLS client profile creation → WORKING
4. Portal/Analytics registration structure → Verified (not tested due to gateway dependency)

## What Requires Additional Work

1. **Gateway Registration via CLI:** Requires TLS server profile with keystore
   - Keystore needs gateway certificate + private key
   - More complex than UI registration
   - **Recommendation:** Use Cloud Manager UI for gateway registration

---

## Final Recommendation

**For Production Use:**
1. Use **Cloud Manager UI** to register Gateway (simpler, no keystore complexity)
2. Use **apic CLI** for Portal and Analytics (straightforward, no TLS server profile needed)

**Or:**
- Register ALL services via Cloud Manager UI (fastest, most reliable)

---

## Important: Gateway CA Certificate Configuration

The gateway MUST be configured to trust the `management-ca` certificate (not `ingress-ca`) for internal communication with the management subsystem.

**In `06-apigateway-cr.yaml`, ensure:**
```yaml
mgmtPlatformEndpointCASecret:
  secretName: management-ca
```

**Why:** The management internal services (like `management-juhu.apic.svc:2000`) use certificates signed by `management-ca`. If the gateway is configured with `ingress-ca`, you'll see errors like:
```
Cannot get access token for https://management-juhu.apic.svc:2000/api/token.
Error: Error: unable to verify the first certificate
```

**To fix an already deployed gateway:**
```bash
kubectl patch gatewaycluster gwv6 -n apic --type=merge \
  -p '{"spec":{"mgmtPlatformEndpointCASecret":{"secretName":"management-ca"}}}'
kubectl delete pod gwv6-0 -n apic  # Restart to pick up new CA
```

## Troubleshooting

### Login fails
- Verify management is running: `kubectl get managementcluster -n apic`
- Check endpoint: `curl -k https://admin.apic.talos-pc.zebra-cloud.net/admin`

### Gateway registration fails with certificate hostname mismatch

**Error:** `Hostname/IP does not match certificate's altnames: Host: gwv6-datapower.apic.svc. is not in the cert's altnames`

**Solution:** Use `gwv6.apic.svc:443` instead of `gwv6-datapower.apic.svc:3000`

The certificate only includes these SANs:
- `gwv6.apic.svc` ✅
- `gwv6.apic.svc.cluster.local` ✅
- `rgwd.apic.talos-pc.zebra-cloud.net` (external)

**Correct endpoints:**
- Management: `https://gwv6.apic.svc:443`
- API Invocation: `https://gwv6.apic.svc:443`

### Gateway registration fails - other issues
- Verify gateway is running: `kubectl get gatewaycluster gwv6 -n apic`
- Check service exists: `kubectl get svc gwv6 -n apic`
- Test from within cluster:
  ```bash
  kubectl run -it --rm test --image=curlimages/curl --restart=Never -- \
    curl -k https://gwv6.apic.svc:443
  ```

### Portal registration fails
- Verify portal is running: `kubectl get portalcluster portal -n apic`
- Check nginx service: `kubectl get svc portal-nginx -n apic`

### Analytics registration fails
- Verify analytics is running: `kubectl get analyticscluster analytics -n apic`
- Check ingestion service: `kubectl get svc analytics-ingestion-https -n apic`

---

## Access Cloud Manager

URL: `https://admin.apic.talos-pc.zebra-cloud.net/admin`
- Username: `admin`
- Password: `Admin123!`

After registration, all services should show status **Enabled** in:
- **Resources → Gateway Services**
- **Resources → Portal Services**
- **Resources → Analytics Services**
