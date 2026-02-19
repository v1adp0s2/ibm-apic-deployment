# Register DataPower Gateway in API Connect

## Prerequisites Verification

DataPower gateway is already deployed and running:
- **Namespace**: `apic`
- **Name**: `gwv6`
- **Status**: Running (3/3 pods ready)

## Gateway Endpoints

Based on the deployment:

### Internal Service Endpoints
- **Management Endpoint**: `https://gwv6-datapower.apic.svc:3000`
- **Gateway Service**: `https://gwv6.apic.svc:443`

### External Ingress Endpoints
- **Management Endpoint**: `https://rgwd.apic.demo01.mea-presales.org`
- **API Gateway Endpoint**: `https://rgw.apic.demo01.mea-presales.org`

## Registration Steps

### Step 1: Access Cloud Manager

1. Navigate to Cloud Manager at: `https://admin.apic.demo01.mea-presales.org`
2. Login with admin credentials

### Step 2: Navigate to Topology

1. In Cloud Manager, go to **Topology** section
2. Click on **Register Service**
3. Select **DataPower API Gateway** as the service type

### Step 3: Configure Gateway Service

Fill in the following configuration:

#### Basic Information
- **Title**: `DataPower API Gateway` (or `AI DataPower Gateway` if using for AI workloads)
- **Name**: This will be auto-generated from title (e.g., `datapower-api-gateway`)
- **Summary**: Optional description (e.g., "DataPower gateway for AI and traditional API workloads")

#### Management Endpoint
- **Management Endpoint**: `https://gwv6.apic.svc:3000`
  - Alternative: Use external endpoint `https://rgwd.apic.demo01.mea-presales.org`
- **TLS Client Profile**: Select `Gateway management client TLS client profile:1.0.0`
  - This profile contains the certificates to authenticate with DataPower

#### API Endpoints
- **API Endpoint Base**: `https://rgw.apic.demo01.mea-presales.org`
  - This is the endpoint where API traffic will be routed
- **SNI Hostname**: `*` (wildcard to accept all SNI hostnames)
  - Or specify specific hostname if required

#### Gateway Service Configuration
- **Gateway Service Type**: `DataPower API Gateway`
- **Integration Type**: `v5 compatible` (for backward compatibility)
  - Or `v10 native` for newer features

### Step 4: Configure Advanced Settings (Optional)

#### High Availability
- **Quorum**: Enable if running multiple DataPower instances
- **Peer Group**: Configure if using DataPower peer groups

#### Analytics
- **Analytics Endpoint**: Already configured via `gwv6` CR
- Should automatically connect to analytics service

### Step 5: Test Connection

1. Click **Test Connection** to verify:
   - Management endpoint is reachable
   - Certificates are valid
   - DataPower is responding

2. Expected result: "Connection successful"

### Step 6: Save and Register

1. Click **Save** to register the gateway
2. Wait for registration to complete
3. Status should change to **Active**

## Verify Registration

### Via Cloud Manager UI

1. Go to **Topology** → **Gateway Services**
2. You should see both gateways:
   - `local-wm-gateway` (webMethods - already registered)
   - `datapower-api-gateway` (DataPower - newly registered)

### Via CLI (using apic toolkit)

```bash
cd /Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/config-adp/v12.1.0.1-local/apic-toolkit

# List gateway services
./apic gateway-services:list \
  --server api.apic.demo01.mea-presales.org \
  --org admin

# Get details of DataPower gateway
./apic gateway-services:get datapower-api-gateway \
  --server api.apic.demo01.mea-presales.org \
  --org admin
```

## Certificate Configuration

The DataPower gateway uses the following certificates:

### Management Communication
- **CA**: `management-ca` (already configured in gwv6 CR)
- **Client Certificate**: Generated during deployment
- **Server Certificate**: DataPower presents its certificate to management

### API Traffic
- **CA**: `ingress-ca` (for ingress traffic)
- **TLS Profile**: Configured in DataPower for API endpoints

## Troubleshooting

### Connection Issues

If registration fails with connection errors:

1. **Verify endpoints are accessible**:
```bash
export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml

# Check internal connectivity
kubectl exec -it deployment/management-apic-apim -n apic -- curl -k https://gwv6.apic.svc:3000/healthcheck

# Check external connectivity
curl -k https://rgwd.apic.demo01.mea-presales.org/healthcheck
```

2. **Check DataPower logs**:
```bash
kubectl logs -n apic gwv6-datapower-0 --tail=50
```

### Certificate Issues

If registration fails with "Certificate subject ineligible":

1. Check the mgmtClientSubjectDN in DataPower:
```bash
kubectl get gatewaycluster gwv6 -n apic -o yaml | grep mgmtClientSubjectDN
```

2. Should match: `CN=management-client`

### Already Registered Error

If you get "Gateway service already exists":
1. Check if DataPower was already registered under a different name
2. Remove the existing registration first, then re-register

## Using Both Gateways

After successful registration, you'll have two gateway services:

1. **webMethods Gateway** (`local-wm-gateway`)
   - Use for: Standard APIs, integration services
   - Endpoint: `https://wmagw.apic.demo01.mea-presales.org`

2. **DataPower Gateway** (`datapower-api-gateway`)
   - Use for: AI workloads, high-performance APIs
   - Endpoint: `https://rgw.apic.demo01.mea-presales.org`

### Assigning Gateways to Catalogs

In your API products, you can now:
1. Choose which gateway to use per catalog
2. Deploy different APIs to different gateways
3. Use DataPower for AI APIs and webMethods for integration APIs

## Next Steps

1. **Create a test API** and deploy to DataPower
2. **Configure gateway policies** specific to DataPower
3. **Set up gateway-specific extensions** if needed
4. **Configure load balancing** between gateway instances