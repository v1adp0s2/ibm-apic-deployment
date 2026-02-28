# IBM API Connect v12.1.0.1-v3 Deployment Package

**Parameterized deployment package for IBM API Connect v12.1.0.1 on Kubernetes**

## Overview

This is a **parameterized** deployment package that uses environment variables to configure all environment-specific values. This approach provides:

- [OK] **Single source of truth** - All configuration in one file (`config.env`)
- [OK] **Environment portability** - Easy to adapt for dev/test/prod
- [OK] **Version control friendly** - Template files only, no hardcoded secrets
- [OK] **Automation ready** - CI/CD integration via environment variables

## Package Configuration

### Target Environment
- **Domain**: `k8s.adp.example.com`
- **Registry**: `harbor.adp.example.com/ibm-apic`
- **Namespace**: `ibm-apic`
- **Storage Class**: `nfs-ssd`
- **Ingress**: Contour (auto-assign LoadBalancer IP)

### Components Included
- [OK] APIC Operators (API Connect & DataPower)
- [OK] Management Cluster
- [OK] Analytics Cluster
- [OK] webMethods Developer Portal
- [OK] webMethods API Gateway
- [OK] AI DataPower Gateway
- [OK] Contour HTTPProxy Ingress

## Quick Start

### 1. Review Configuration
```bash
cd /path/to/v12.1.0.1-v3
cat config.env
```

The `config.env` file is pre-configured with your specified values. Review and adjust as needed.

### 2. Source Configuration
```bash
source config.env
```

This loads all environment variables into your shell session.

### 3. Verify Configuration
```bash
env | grep APIC_
```

You should see all `APIC_*` variables exported.

### 4. Deploy Core Components
```bash
# Follow the deployment guide
cat core/DEPLOY-CORE.txt

# Create namespace
kubectl create namespace ${APIC_NAMESPACE}

# Deploy operators
kubectl apply -f core/01-operators/01-apiconnect-crds.yaml

# Deploy parameterized operator (using envsubst)
envsubst < core/01-operators/02-apiconnect-operator.yaml.template | kubectl apply -f -
envsubst < core/01-operators/03-datapower-operator.yaml.template | kubectl apply -f -

# Deploy prerequisites
kubectl apply -f core/02-prerequisites/

# Deploy management
envsubst < core/03-management/06-management-cr.yaml.template | kubectl apply -f -
```

### 5. Deploy Sub-Components
Each sub-component has its own `COMMANDS.txt` guide:

```bash
# Analytics
cat sub-components/01-analytics/COMMANDS.txt

# wM DevPortal
cat sub-components/02-wm-devportal/COMMANDS.txt

# wM API Gateway
cat sub-components/03-wm-gateway/COMMANDS.txt

# AI Gateway
cat sub-components/04-ai-gateway/COMMANDS.txt
```

### 6. Deploy Ingress
```bash
cat ingress/COMMANDS.txt
```

## File Structure

```
v12.1.0.1-v3/
├── config.env                      # ← Active configuration (your values)
├── config.env.template             # ← Documented template
├── INDEX.yaml                      # ← Package metadata
├── README.md                       # ← This file
├── 00-START-HERE.txt              # ← Quick start guide
├── 00-CONFIGURE.txt               # ← Configuration guide
│
├── core/                          # Core components
│   ├── DEPLOY-CORE.txt
│   ├── 01-operators/              # Operators
│   │   ├── 01-apiconnect-crds.yaml
│   │   ├── 02-apiconnect-operator.yaml.template
│   │   └── 03-datapower-operator.yaml.template
│   ├── 02-prerequisites/          # Prerequisites
│   │   ├── 04-ingress-issuer.yaml
│   │   └── 05-contour-ingressclass.yaml
│   └── 03-management/             # Management cluster
│       └── 06-management-cr.yaml.template
│
├── sub-components/                # Optional components
│   ├── 01-analytics/
│   │   ├── COMMANDS.txt
│   │   └── analytics-cr.yaml.template
│   ├── 02-wm-devportal/
│   │   ├── COMMANDS.txt
│   │   └── devportal-cr.yaml.template
│   ├── 03-wm-gateway/
│   │   ├── COMMANDS.txt
│   │   └── wm-gateway-cr.yaml.template
│   └── 04-ai-gateway/
│       ├── COMMANDS.txt
│       └── ai-gateway-cr.yaml.template
│
├── ingress/                       # Ingress resources
│   ├── COMMANDS.txt
│   ├── contour-httpproxy-management.yaml.template
│   ├── contour-httpproxy-analytics.yaml.template
│   ├── contour-httpproxy-devportal.yaml.template
│   ├── contour-httpproxy-gateway.yaml.template
│   └── contour-httpproxy-ai-gateway.yaml.template
│
└── utilities/                     # Utility components
    ├── cert-manager/              # cert-manager v1.19.2 deployment
    ├── busybox/                   # Troubleshooting tools
    └── register-services/         # Service registration

```

## How Parameterization Works

### Template Files
All environment-specific YAML files end with `.template` extension:
- `02-apiconnect-operator.yaml.template`
- `06-management-cr.yaml.template`
- `contour-httpproxy-management.yaml.template`

### Variables
These templates contain placeholders like:
```yaml
namespace: ${APIC_NAMESPACE}
imageRegistry: ${APIC_IMAGE_REGISTRY}
storageClassName: ${APIC_STORAGE_CLASS}
```

### Processing
The `envsubst` command replaces variables with actual values:

```bash
# Input (template)
namespace: ${APIC_NAMESPACE}

# After envsubst (with config.env sourced)
namespace: ibm-apic
```

### Deployment Workflow
```bash
# 1. Source configuration
source config.env

# 2. Process template and apply
envsubst < template.yaml.template | kubectl apply -f -
```

## Environment Variables

All variables are defined in `config.env` and prefixed with `APIC_`:

### Core Variables
- `APIC_NAMESPACE` - Kubernetes namespace
- `APIC_DOMAIN_BASE` - Base DNS domain
- `APIC_IMAGE_REGISTRY` - Container registry
- `APIC_STORAGE_CLASS` - Storage class name
- `APIC_INGRESS_CLASS` - Ingress controller class

### Service Hostnames
- `APIC_MGMT_ADMIN_HOST` - Management admin endpoint
- `APIC_MGMT_MANAGER_HOST` - API Manager endpoint
- `APIC_MGMT_PLATFORM_API_HOST` - Platform API endpoint
- `APIC_ANALYTICS_INGESTION_HOST` - Analytics ingestion
- `APIC_DEVPORTAL_ADMIN_HOST` - DevPortal admin
- `APIC_WM_GATEWAY_HOST` - wM Gateway endpoint
- `APIC_AI_GATEWAY_HOST` - AI Gateway endpoint

### Secrets
- `APIC_IMAGE_PULL_SECRET` - Registry pull secret name
- `APIC_MGMT_ADMIN_PASSWORD` - Management admin password
- `APIC_DATAPOWER_ADMIN_PASSWORD` - DataPower admin password
- `APIC_WM_GATEWAY_ADMIN_PASSWORD` - wM Gateway admin password

See `config.env.template` for complete list with documentation.

## Customization

### Changing Values
Edit `config.env` and modify any values:

```bash
vi config.env

# Example changes
export APIC_DOMAIN_BASE="production.example.com"
export APIC_MGMT_REPLICAS="3"
export APIC_STORAGE_CLASS="cephfs"
```

### Sourcing Updated Config
```bash
source config.env
```

### Re-deploying
Templates can be reprocessed with new values at any time.

## Troubleshooting

### Verify Variables
```bash
source config.env
echo $APIC_NAMESPACE
echo $APIC_DOMAIN_BASE
```

### Test Template Processing
```bash
source config.env
envsubst < core/03-management/06-management-cr.yaml.template
```

### BusyBox Utilities
```bash
# Use busybox pod for troubleshooting
kubectl apply -f utilities/busybox/clear-pvc-pod.yaml
kubectl exec -it busybox -n ${APIC_NAMESPACE} -- /bin/sh
```

## Package Information

- **Package**: v12.1.0.1-v3
- **APIC Version**: 12.1.0.1
- **Created**: 2026-02-19
- **Approach**: Environment Variable Parameterization
- **Generated**: Based on v12.1.0.1-local source

## Next Steps

1. [OK] Review `config.env` - Verify all values
2. [OK] Source configuration - `source config.env`
3. [OK] Create secrets - Configure registry and admin passwords
4. [OK] Deploy core - Follow `core/DEPLOY-CORE.txt`
5. [OK] Deploy components - Follow sub-component guides
6. [OK] Deploy ingress - Follow `ingress/COMMANDS.txt`
7. [OK] Register services - Follow service registration guide

## Support

For issues or questions about this deployment package:
- Review `00-START-HERE.txt` for quickstart
- Review `00-CONFIGURE.txt` for configuration details
- Check IBM API Connect documentation

## Version History

- **v3** (2026-02-19): Parameterized package for k8s.adp.example.com
- **v2** (2026-02-19): Reference parameterized package
- **v1** (base): Static configuration package
