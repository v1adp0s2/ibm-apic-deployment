#!/usr/bin/env bash

## Generate TLS self-signed certificates for Valkey and create Kubernetes secret.

NAMESPACE=${1}
SECRET_NAME=${2}
SERVICE_NAME=${3:-valkey}

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "Error: Invalid number of arguments."
  echo "Usage: $0 <namespace> <secret-name> [service-name]"
  echo ""
  echo "Arguments:"
  echo "  namespace    - Kubernetes namespace for the secret"
  echo "  secret-name  - Name of the Kubernetes secret to create"
  echo "  service-name - (Optional) Valkey service name e.g valkey or valkey-cluster (default: valkey)"
  exit 1
fi

CERT_DIR=$(mktemp -d)
# Setup cleanup trap - runs on EXIT, INT, TERM
trap "rm -rf ${CERT_DIR}" EXIT INT TERM

cd "${CERT_DIR}"

# Generate CA key and certificate
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365 -out ca.crt -subj "/CN=ValkeyCA"

# Generate server key
openssl genrsa -out tls.key 2048

# Generate certificate signing request
openssl req -new -key tls.key -out tls.csr -subj "/CN=${SERVICE_NAME}.${NAMESPACE}.svc.cluster.local"

# Create config file for SAN
cat > san.cnf <<EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${SERVICE_NAME}.${NAMESPACE}.svc.cluster.local
DNS.2 = ${SERVICE_NAME}.${NAMESPACE}.svc
DNS.3 = ${SERVICE_NAME}-headless.${NAMESPACE}.svc.cluster.local
DNS.4 = ${SERVICE_NAME}-headless.${NAMESPACE}.svc
DNS.5 = ${SERVICE_NAME}-headless
DNS.6 = ${SERVICE_NAME}
DNS.7 = ${SERVICE_NAME}-leader-headless.${NAMESPACE}.svc.cluster.local
DNS.8 = ${SERVICE_NAME}-leader-headless.${NAMESPACE}.svc
DNS.9 = ${SERVICE_NAME}-leader-headless
DNS.10 = ${SERVICE_NAME}-leader.${NAMESPACE}.svc.cluster.local
DNS.11 = ${SERVICE_NAME}-leader.${NAMESPACE}.svc
DNS.12 = ${SERVICE_NAME}-leader
EOF

# Generate the certificate with SAN
openssl x509 -req -in tls.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out tls.crt -days 365 -sha256 -extfile san.cnf -extensions v3_req

# Display the certificate details for verification
echo ""
echo "Certificate generated with the following SANs:"
openssl x509 -in tls.crt -text -noout | grep -A 1 "Subject Alternative Name"
echo ""

# Check if secret exists and delete it
if kubectl get secret "${SECRET_NAME}" -n "${NAMESPACE}" &> /dev/null; then
    echo "Warning: Secret already exists. Deleting..."
    kubectl delete secret "${SECRET_NAME}" -n "${NAMESPACE}"
fi

# Create the TLS secrete
echo "Creating TLS secret ${SECRET_NAME} in namespace ${NAMESPACE}"
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic ${SECRET_NAME} \
  --from-file=ca.crt=ca.crt \
  --from-file=tls.crt=tls.crt \
  --from-file=tls.key=tls.key \
  -n ${NAMESPACE}

echo "Secret ${SECRET_NAME} created in namespace ${NAMESPACE}"
