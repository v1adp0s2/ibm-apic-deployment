#!/bin/bash

# Patch all APIC service accounts to use harbor-registry-secret
# This ensures all pods can pull images from the private Harbor registry

NAMESPACE=${1:-apic}
SECRET_NAME=${2:-harbor-registry-secret}

echo "Patching service accounts in namespace: $NAMESPACE"
echo "Using imagePullSecret: $SECRET_NAME"
echo "----------------------------------------"

# Patch default service account
echo "Patching default service account..."
kubectl patch serviceaccount default -n "$NAMESPACE" -p "{\"imagePullSecrets\": [{\"name\": \"$SECRET_NAME\"}]}"

# Get all service accounts (excluding default which we already patched)
SERVICE_ACCOUNTS=$(kubectl get sa -n "$NAMESPACE" --no-headers | awk '{print $1}' | grep -v "^default$")

# Patch each service account
for sa in $SERVICE_ACCOUNTS; do
  echo "Patching service account: $sa"
  kubectl patch serviceaccount "$sa" -n "$NAMESPACE" -p "{\"imagePullSecrets\": [{\"name\": \"$SECRET_NAME\"}]}"
done

echo "----------------------------------------"
echo "Done! All service accounts patched."
echo ""
echo "To verify, run:"
echo "  kubectl get sa -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name}{\"\\t\"}{.imagePullSecrets[*].name}{\"\\n\"}{end}'"
