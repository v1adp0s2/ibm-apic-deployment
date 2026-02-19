#!/bin/bash
#
# Create secrets required for webMethods API Gateway deployment
#

set -e

export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml
NAMESPACE="apic"

echo "=============================================="
echo "webMethods API Gateway - Secret Creation"
echo "=============================================="
echo ""

# Generate strong passwords
ENCRYPTION_PASSWORD=$(openssl rand -base64 32)
ADMIN_PASSWORD="Admin123!"

echo "Step 1: Creating encryption key secret..."
kubectl create secret generic wmapigateway-enc-key \
  --from-literal=password="$ENCRYPTION_PASSWORD" \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "[OK] Encryption key secret created"
echo ""

echo "Step 2: Creating admin credentials secret..."
kubectl create secret generic wmapigateway-admin-secret \
  --from-literal=password="$ADMIN_PASSWORD" \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "[OK] Admin credentials secret created"
echo ""

echo "=============================================="
echo "Secrets Created Successfully!"
echo "=============================================="
echo ""
echo "Admin Password: $ADMIN_PASSWORD"
echo "Encryption Key: $ENCRYPTION_PASSWORD"
echo ""
echo "Save these credentials securely!"
echo ""
