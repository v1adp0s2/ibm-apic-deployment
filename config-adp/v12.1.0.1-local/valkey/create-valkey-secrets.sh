#!/bin/bash
#
# Create secrets required for Valkey deployment
#

set -e

export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml
NAMESPACE="apic"

echo "=============================================="
echo "Valkey - Secret Creation"
echo "=============================================="
echo ""

# Generate strong password
VALKEY_PASSWORD=$(openssl rand -base64 32)

echo "Step 1: Creating Valkey password secret..."
kubectl create secret generic valkey-secret \
  --from-literal=password="$VALKEY_PASSWORD" \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "[OK] Valkey password secret created"
echo ""

echo "Step 2: Creating Valkey TLS secret..."
# Extract CA from ingress-ca secret
kubectl get secret -n $NAMESPACE ingress-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > /tmp/valkey-ca.crt
kubectl get secret -n $NAMESPACE ingress-ca -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/valkey-tls.crt
kubectl get secret -n $NAMESPACE ingress-ca -o jsonpath='{.data.tls\.key}' | base64 -d > /tmp/valkey-tls.key

kubectl create secret generic valkey-tls \
  --from-file=ca.crt=/tmp/valkey-ca.crt \
  --from-file=tls.crt=/tmp/valkey-tls.crt \
  --from-file=tls.key=/tmp/valkey-tls.key \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

rm -f /tmp/valkey-ca.crt /tmp/valkey-tls.crt /tmp/valkey-tls.key

echo "[OK] Valkey TLS secret created"
echo ""

echo "=============================================="
echo "Secrets Created Successfully!"
echo "=============================================="
echo ""
echo "Valkey Password: $VALKEY_PASSWORD"
echo ""
echo "Save this password securely!"
echo ""
