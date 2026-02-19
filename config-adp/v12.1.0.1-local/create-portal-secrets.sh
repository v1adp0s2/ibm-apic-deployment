#!/bin/bash
#
# Create secrets required for Developer Portal deployment
#

set -e

export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml
NAMESPACE="apic"

echo "=============================================="
echo "Developer Portal - Secret Creation"
echo "=============================================="
echo ""

# Generate encryption key
ENCRYPTION_KEY=$(openssl rand -base64 32)

echo "Step 1: Creating Developer Portal encryption key secret..."
kubectl create secret generic devportal-enc-key \
  --from-literal=PORTAL_SERVER_CONFIG_ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "[OK] Developer Portal encryption key secret created"
echo ""

echo "=============================================="
echo "Secret Created Successfully!"
echo "=============================================="
echo ""
echo "Encryption Key: $ENCRYPTION_KEY"
echo ""
echo "Save this key securely!"
echo ""
