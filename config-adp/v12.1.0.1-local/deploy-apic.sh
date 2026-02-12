#!/bin/bash

###################################################################################
# IBM API Connect v12.1.0.1 Deployment Automation for Talos Kubernetes
###################################################################################
# This script automates the complete deployment of IBM API Connect v12.1.0.1
# on a Talos Kubernetes cluster with nginx ingress controller.
#
# Prerequisites:
# - Talos Kubernetes cluster running
# - kubectl configured with proper KUBECONFIG
# - Harbor registry at harbor.talos.zebra-cloud.net with 'apic' project
# - All APIC v12.1.0.1 images mirrored to Harbor
# - NFS storage configured with no_root_squash
# - nginx ingress controller installed
#
# Usage:
#   ./deploy-apic.sh [OPTIONS]
#
# Options:
#   --skip-prereqs    Skip prerequisite installation (namespace, cert-manager, etc.)
#   --subsystems      Comma-separated list of subsystems to deploy (default: all)
#                     Options: management,gateway,portal,analytics
#   --wait            Wait for each subsystem to be ready before proceeding
#   --help            Show this help message
#
###################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="apic"
REGISTRY_SERVER="harbor.talos.zebra-cloud.net"
REGISTRY_PROJECT="apic"
DOMAIN_SUFFIX="apic.talos-nginx.zebra-cloud.net"
INGRESS_CLASS="nginx"
STORAGE_CLASS="nfs-ssd"

# Parse command line arguments
SKIP_PREREQS=false
SUBSYSTEMS="management,gateway,portal,analytics"
WAIT_FOR_READY=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-prereqs)
      SKIP_PREREQS=true
      shift
      ;;
    --subsystems)
      SUBSYSTEMS="$2"
      shift 2
      ;;
    --wait)
      WAIT_FOR_READY=true
      shift
      ;;
    --help)
      head -n 30 "$0" | grep "^#" | sed 's/^# //g' | sed 's/^#//g'
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Helper functions
print_step() {
  echo -e "\n${BLUE}===========================================================${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}===========================================================${NC}\n"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
  echo -e "${BLUE}ℹ $1${NC}"
}

wait_for_pods() {
  local namespace=$1
  local label=$2
  local timeout=${3:-600}

  print_info "Waiting for pods with label $label to be ready (timeout: ${timeout}s)..."
  kubectl wait --for=condition=Ready pods -l "$label" -n "$namespace" --timeout="${timeout}s" || true
}

check_prerequisite() {
  local cmd=$1
  local name=$2

  if ! command -v "$cmd" &> /dev/null; then
    print_error "$name is not installed or not in PATH"
    return 1
  fi
  print_success "$name is available"
  return 0
}

###################################################################################
# Pre-flight Checks
###################################################################################

print_step "STEP 0: Pre-flight Checks"

check_prerequisite kubectl "kubectl"

# Check if KUBECONFIG is set or default kubeconfig exists
if [ -z "$KUBECONFIG" ] && [ ! -f "$HOME/.kube/config" ]; then
  print_error "KUBECONFIG not set and default kubeconfig not found"
  exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
  print_error "Cannot connect to Kubernetes cluster"
  exit 1
fi
print_success "Connected to Kubernetes cluster"

# Check for .env file
if [ ! -f ".env" ]; then
  print_error ".env file not found. Please create it with required credentials."
  echo ""
  echo "Required variables:"
  echo "  REGISTRY_SERVER=harbor.talos.zebra-cloud.net"
  echo "  REGISTRY_USERNAME=<harbor_username>"
  echo "  REGISTRY_USERPWD=<harbor_password>"
  echo "  IBM_ENTITLEMENT_KEY=<ibm_entitlement_key>"
  echo "  APIC_ADMIN_PWD=<admin_password>"
  exit 1
fi

# Source environment variables
source .env
print_success ".env file loaded"

###################################################################################
# Step 1: Create Namespace
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 1: Create Namespace"

  if kubectl get namespace "$NAMESPACE" &> /dev/null; then
    print_warning "Namespace $NAMESPACE already exists"
  else
    kubectl create namespace "$NAMESPACE"
    print_success "Namespace $NAMESPACE created"
  fi
fi

###################################################################################
# Step 2: Install cert-manager
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 2: Install cert-manager"

  if kubectl get namespace cert-manager &> /dev/null; then
    print_warning "cert-manager namespace already exists, skipping installation"
  else
    print_info "Installing cert-manager..."
    kubectl apply -f cert-manager/cert-manager-1.19.2.yaml
    print_info "Waiting for cert-manager to be ready..."
    kubectl wait --for=condition=Ready pods --all -n cert-manager --timeout=300s
    print_success "cert-manager installed and ready"
  fi
fi

###################################################################################
# Step 3: Create Secrets
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 3: Create Secrets"

  # Harbor registry secret
  if kubectl get secret harbor-registry-secret -n "$NAMESPACE" &> /dev/null; then
    print_warning "harbor-registry-secret already exists"
  else
    kubectl create secret docker-registry harbor-registry-secret \
      --docker-server="$REGISTRY_SERVER" \
      --docker-username="$REGISTRY_USERNAME" \
      --docker-password="$REGISTRY_USERPWD" \
      --namespace "$NAMESPACE"
    print_success "harbor-registry-secret created"
  fi

  # IBM Entitled Registry secret (for operator images if needed)
  if kubectl get secret apic-registry-secret -n "$NAMESPACE" &> /dev/null; then
    print_warning "apic-registry-secret already exists"
  else
    kubectl create secret docker-registry apic-registry-secret \
      --docker-server=cp.icr.io \
      --docker-username=cp \
      --docker-password="$IBM_ENTITLEMENT_KEY" \
      --namespace "$NAMESPACE"
    print_success "apic-registry-secret created"
  fi

  # DataPower admin credentials
  if kubectl get secret datapower-admin-credentials -n "$NAMESPACE" &> /dev/null; then
    print_warning "datapower-admin-credentials already exists"
  else
    kubectl create secret generic datapower-admin-credentials \
      --from-literal=password="$APIC_ADMIN_PWD" \
      --namespace "$NAMESPACE"
    print_success "datapower-admin-credentials created"
  fi
fi

###################################################################################
# Step 4: Install CRDs
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 4: Install CRDs"

  kubectl apply --server-side --force-conflicts -f 01-ibm-apiconnect-crds.yaml
  print_success "CRDs installed"
fi

###################################################################################
# Step 5: Configure Storage
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 5: Configure NFS Storage"

  print_info "Setting $STORAGE_CLASS as default storage class..."

  # Remove default from openebs-hostpath if it exists
  if kubectl get storageclass openebs-hostpath &> /dev/null; then
    kubectl patch storageclass openebs-hostpath \
      -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}' || true
  fi

  # Make nfs-ssd the default
  kubectl patch storageclass "$STORAGE_CLASS" \
    -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

  print_success "$STORAGE_CLASS is now the default storage class"

  print_warning "IMPORTANT: Ensure NFS server is configured with no_root_squash!"
fi

###################################################################################
# Step 6: Install Operators
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 6: Install Operators"

  print_info "Installing IBM API Connect operator..."
  kubectl apply -f 02-ibm-apiconnect-operator.yaml -n "$NAMESPACE"

  print_info "Installing DataPower operator..."
  kubectl apply -f 03-ibm-datapower-operator.yaml -n "$NAMESPACE"

  print_info "Waiting for operators to be ready..."
  kubectl wait --for=condition=Available deployment/ibm-apiconnect -n "$NAMESPACE" --timeout=300s || true
  kubectl wait --for=condition=Available deployment/datapower-operator -n "$NAMESPACE" --timeout=300s || true

  print_success "Operators installed and ready"
fi

###################################################################################
# Step 7: Install Ingress Issuer
###################################################################################

if [ "$SKIP_PREREQS" = false ]; then
  print_step "STEP 7: Install Ingress Issuer"

  kubectl apply -f 04-ingress-issuer.yaml -n "$NAMESPACE"
  print_info "Waiting for ingress CA certificate to be ready..."
  kubectl wait --for=condition=Ready certificate/ingress-ca -n "$NAMESPACE" --timeout=60s || true
  print_success "Ingress issuer configured"
fi

###################################################################################
# Step 8: Patch Service Accounts
###################################################################################

print_step "STEP 8: Patch Service Accounts"

print_info "Patching all service accounts to use harbor-registry-secret..."
./patch-service-accounts.sh "$NAMESPACE" harbor-registry-secret
print_success "Service accounts patched"

###################################################################################
# Step 9: Deploy Subsystems
###################################################################################

deploy_management() {
  print_step "STEP 9a: Deploy Management Subsystem"

  if kubectl get managementcluster management -n "$NAMESPACE" &> /dev/null; then
    print_warning "Management subsystem already exists, applying updates..."
  fi

  kubectl apply -f 05-management-cr.yaml -n "$NAMESPACE"
  print_success "Management subsystem deployed"

  if [ "$WAIT_FOR_READY" = true ]; then
    print_info "Waiting for Management subsystem to be ready (this may take 15-20 minutes)..."
    kubectl wait --for=jsonpath='{.status.phase}'=Ready managementcluster/management -n "$NAMESPACE" --timeout=1200s || true
  fi

  print_info "Check status with: kubectl get managementcluster management -n $NAMESPACE"
}

deploy_gateway() {
  print_step "STEP 9b: Deploy Gateway Subsystem"

  if kubectl get gatewaycluster gwv6 -n "$NAMESPACE" &> /dev/null; then
    print_warning "Gateway subsystem already exists, applying updates..."
  fi

  kubectl apply -f 06-apigateway-cr.yaml -n "$NAMESPACE"
  print_success "Gateway subsystem deployed"

  if [ "$WAIT_FOR_READY" = true ]; then
    print_info "Waiting for Gateway subsystem to be ready (this may take 10-15 minutes)..."
    kubectl wait --for=jsonpath='{.status.phase}'=Ready gatewaycluster/gwv6 -n "$NAMESPACE" --timeout=900s || true
  fi

  print_info "Check status with: kubectl get gatewaycluster gwv6 -n $NAMESPACE"
}

deploy_portal() {
  print_step "STEP 9c: Deploy Portal Subsystem"

  if kubectl get portalcluster portal -n "$NAMESPACE" &> /dev/null; then
    print_warning "Portal subsystem already exists, applying updates..."
  fi

  kubectl apply -f 07-portal-cr.yaml -n "$NAMESPACE"
  print_success "Portal subsystem deployed"

  if [ "$WAIT_FOR_READY" = true ]; then
    print_info "Waiting for Portal subsystem to be ready (this may take 15-20 minutes)..."
    kubectl wait --for=jsonpath='{.status.phase}'=Ready portalcluster/portal -n "$NAMESPACE" --timeout=1200s || true
  fi

  print_info "Check status with: kubectl get portalcluster portal -n $NAMESPACE"
}

deploy_analytics() {
  print_step "STEP 9d: Deploy Analytics Subsystem"

  if kubectl get analyticscluster analytics -n "$NAMESPACE" &> /dev/null; then
    print_warning "Analytics subsystem already exists, applying updates..."
  fi

  kubectl apply -f 08-analytics-cr.yaml -n "$NAMESPACE"
  print_success "Analytics subsystem deployed"

  if [ "$WAIT_FOR_READY" = true ]; then
    print_info "Waiting for Analytics subsystem to be ready (this may take 10-15 minutes)..."
    kubectl wait --for=jsonpath='{.status.phase}'=Ready analyticscluster/analytics -n "$NAMESPACE" --timeout=900s || true
  fi

  print_info "Check status with: kubectl get analyticscluster analytics -n $NAMESPACE"
}

# Deploy requested subsystems
IFS=',' read -ra SUBSYS_ARRAY <<< "$SUBSYSTEMS"
for subsystem in "${SUBSYS_ARRAY[@]}"; do
  case $subsystem in
    management)
      deploy_management
      ;;
    gateway)
      deploy_gateway
      ;;
    portal)
      deploy_portal
      ;;
    analytics)
      deploy_analytics
      ;;
    *)
      print_error "Unknown subsystem: $subsystem"
      ;;
  esac
done

###################################################################################
# Final Status
###################################################################################

print_step "Deployment Complete!"

echo -e "\n${GREEN}✓ IBM API Connect v12.1.0.1 deployment initiated${NC}\n"

print_info "Access URLs:"
echo "  Cloud Manager:        https://admin.$DOMAIN_SUFFIX/admin"
echo "  API Manager:          https://manager.$DOMAIN_SUFFIX"
echo "  Platform API:         https://api.$DOMAIN_SUFFIX"
echo "  Consumer API:         https://consumer.$DOMAIN_SUFFIX"
echo "  Consumer Catalog:     https://consumer-catalog.$DOMAIN_SUFFIX"
echo "  Gateway:              https://rgw.$DOMAIN_SUFFIX"
echo "  Gateway Manager:      https://rgwd.$DOMAIN_SUFFIX"
echo "  Portal UI:            https://portal.$DOMAIN_SUFFIX"
echo "  Portal Admin:         https://api.portal.$DOMAIN_SUFFIX"
echo "  Analytics Ingestion:  https://ai.$DOMAIN_SUFFIX"

echo ""
print_info "Monitor deployment status:"
echo "  kubectl get pods -n $NAMESPACE -w"
echo "  kubectl get managementcluster,gatewaycluster,portalcluster,analyticscluster -n $NAMESPACE"

echo ""
print_info "Get admin credentials:"
echo "  kubectl get secret management-admin-secret -n $NAMESPACE -o jsonpath='{.data.password}' | base64 -d"

echo ""
print_warning "Note: Full deployment may take 30-45 minutes for all subsystems to be ready."

echo ""
