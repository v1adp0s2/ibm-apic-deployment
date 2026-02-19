#!/bin/bash
#
# IBM API Connect v12.1.0.1 - Service Registration Script
# This script registers Gateway, Portal, and Analytics services using apic CLI
#

set -e

echo "=============================================="
echo "IBM API Connect Service Registration"
echo "=============================================="
echo ""

# Configuration
export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml
export SERVER="api.apic.talos-pc.zebra-cloud.net"
export ORG="admin"
export AZ="availability-zone-default"
export REALM="admin/default-idp-1"

# Get admin password
echo "Step 1: Getting admin credentials..."
export ADMIN_PASSWORD=$(kubectl get secret -n apic management-admin-secret -o jsonpath='{.data.password}' | base64 -d)
echo "[OK] Admin password retrieved"
echo ""

# Create working directory
mkdir -p ~/apic-certs
cd ~/apic-certs

# Login
echo "Step 2: Logging in to API Connect..."
apic login \
  --server $SERVER \
  --username admin \
  --password "$ADMIN_PASSWORD" \
  --realm $REALM \
  --insecure-skip-tls-verify

echo "[OK] Login successful"
echo ""

# Extract CA certificate
echo "Step 3: Extracting CA certificate..."
kubectl get secret -n apic ingress-ca \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > ~/apic-certs/ingress-ca.pem

echo "[OK] CA certificate extracted"
echo ""

# Create TLS client profile YAML
echo "Step 4: Creating TLS client profile..."
cat > ~/apic-certs/tls-client-profile.yaml <<'EOF'
name: internal-ca-trust
title: Internal CA Trust Profile
certificates:
  - |
EOF

# Append certificate with proper indentation
cat ~/apic-certs/ingress-ca.pem | sed 's/^/    /' >> ~/apic-certs/tls-client-profile.yaml

# Upload TLS profile
apic tls-client-profiles:create \
  --server $SERVER \
  --org $ORG \
  --insecure-skip-tls-verify \
  ~/apic-certs/tls-client-profile.yaml

export TLS_PROFILE_URL="https://${SERVER}/api/orgs/${ORG}/tls-client-profiles/internal-ca-trust"
echo "[OK] TLS profile created: $TLS_PROFILE_URL"
echo ""

# Create Gateway service definition
echo "Step 5: Registering DataPower Gateway..."
cat > ~/apic-certs/gateway-service.yaml <<EOFGW
name: datapower-gateway
title: DataPower Gateway
endpoint: https://gwv6-datapower.apic.svc:3000
api_endpoint_base: https://gwv6.apic.svc:443
gateway_service_type: datapower-api-gateway
tls_client_profile_url: $TLS_PROFILE_URL
sni:
  - host: '*'
    tls_server_profile_url: $TLS_PROFILE_URL
EOFGW

apic gateway-services:create \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  ~/apic-certs/gateway-service.yaml

echo "[OK] Gateway registered"
echo ""

# Create Portal service definition
echo "Step 6: Registering Developer Portal..."
cat > ~/apic-certs/portal-service.yaml <<'EOFPORTAL'
name: developer-portal
title: Developer Portal
endpoint: https://portal-nginx.apic.svc:8443
web_endpoint_base: https://portal.apic.svc:443
EOFPORTAL

apic portal-services:create \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  ~/apic-certs/portal-service.yaml

echo "[OK] Portal registered"
echo ""

# Create Analytics service definition
echo "Step 7: Registering Analytics Service..."
cat > ~/apic-certs/analytics-service.yaml <<'EOFANALYTICS'
name: analytics-service
title: Analytics Service
endpoint: https://analytics-ingestion-https.apic.svc:443
EOFANALYTICS

apic analytics-services:create \
  --server $SERVER \
  --org $ORG \
  --availability-zone $AZ \
  --insecure-skip-tls-verify \
  ~/apic-certs/analytics-service.yaml

echo "[OK] Analytics registered"
echo ""

# Summary
echo "=============================================="
echo "Registration Complete!"
echo "=============================================="
echo ""
echo "Registered services:"
echo "  - DataPower Gateway: https://gwv6-datapower.apic.svc:3000"
echo "  - Developer Portal:  https://portal-nginx.apic.svc:8443"
echo "  - Analytics Service: https://analytics-ingestion-https.apic.svc:443"
echo ""
echo "Verify in Cloud Manager:"
echo "  https://admin.apic.talos-pc.zebra-cloud.net/admin"
echo ""
echo "  Resources > Gateway Services"
echo "  Resources > Portal Services"
echo "  Resources > Analytics Services"
echo ""

# Logout
apic logout --server $SERVER --insecure-skip-tls-verify
echo "[OK] Logged out"
