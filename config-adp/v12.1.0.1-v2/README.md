# IBM API Connect v12.1.0.1-v2 - Parameterized Deployment Package

## Overview

This is a **parameterized deployment package** for IBM API Connect v12.1.0.1 that uses environment variables for all environment-specific configuration, similar to Helm's values approach.

## Package Naming Convention

- **Format**: `v<APIC_VERSION>-v<PACKAGE_ITERATION>`
- **Example**: `v12.1.0.1-v2`
  - `v12.1.0.1` = IBM API Connect product version
  - `-v2` = Package iteration/revision number (v1, v2, v3, etc.)

## Key Features

### 1. Environment Variable Configuration
All environment-specific values are defined as variables in a single configuration file:

```bash
# config.env
export APIC_DOMAIN_BASE="k8s.adp.example.com"
export APIC_IMAGE_REGISTRY="harbor.adp.example.com/apic"
export APIC_STORAGE_CLASS="nfs-ssd"
export APIC_NAMESPACE="apic"
# ... 50+ more variables
```

### 2. Template-Based YAML Files
YAML manifests use `${VAR_NAME}` placeholders:

```yaml
# Example: core/03-management/06-management-cr.yaml.template
apiVersion: management.apiconnect.ibm.com/v1beta1
kind: ManagementCluster
metadata:
  name: management
  namespace: ${APIC_NAMESPACE}
spec:
  imageRegistry: ${APIC_IMAGE_REGISTRY}
  cloudManagerEndpoint:
    ingressClassName: ${APIC_INGRESS_CLASS}
    hosts:
    - name: ${APIC_MGMT_ADMIN_HOST}
  databaseVolumeClaimTemplate:
    storageClassName: ${APIC_STORAGE_CLASS}
```

### 3. Helper Scripts
- **`utilities/envsubst-yaml.sh`** - Substitutes environment variables in templates
- **`utilities/create-secrets.sh`** - Creates all required Kubernetes secrets
- **`utilities/deploy.sh`** - Deployment wrapper that sources config and applies templates

## Quick Start

### 1. Configure
```bash
cd v12.1.0.1-v2
cp config.env.template config.env
vi config.env  # Edit with your environment values
```

### 2. Load Configuration
```bash
source config.env
```

### 3. Verify Configuration
```bash
env | grep APIC_
```

### 4. Deploy
```bash
# Deploy using template substitution
utilities/envsubst-yaml.sh core/03-management/06-management-cr.yaml.template | kubectl apply -f -

# Or follow step-by-step instructions
cat core/DEPLOY-CORE.txt
```

## Configuration Variables

Variables are organized into categories:

### Core Configuration
- `APIC_PACKAGE_NAME` - Package name
- `APIC_PACKAGE_VERSION` - APIC version (12.1.0.1)
- `APIC_NAMESPACE` - Kubernetes namespace

### Network Configuration
- `APIC_DOMAIN_BASE` - Base DNS domain for all services
- `APIC_INGRESS_CLASS` - Ingress controller class (contour)
- `APIC_LOADBALANCER_IP` - LoadBalancer IP address
- `APIC_MGMT_ADMIN_HOST` - Cloud Manager hostname
- `APIC_MGMT_MANAGER_HOST` - API Manager hostname
- ... and more service endpoints

### Container Registry
- `APIC_IMAGE_REGISTRY` - Container image registry path
- `APIC_IMAGE_PULL_SECRET` - Pull secret name
- `APIC_REGISTRY_SERVER` - Registry server
- `APIC_REGISTRY_USERNAME` - Registry username
- `APIC_REGISTRY_PASSWORD` - Registry password

### Storage
- `APIC_STORAGE_CLASS` - Default storage class
- `APIC_BACKUP_STORAGE_CLASS` - Backup storage class

### Certificates
- `APIC_CERT_ISSUER_NAME` - cert-manager issuer name
- `APIC_CERT_ISSUER_KIND` - Issuer type (ClusterIssuer/Issuer)

### Secrets
- `APIC_MGMT_ADMIN_PASSWORD` - Management admin password
- `APIC_DATAPOWER_ADMIN_PASSWORD` - DataPower admin password
- `APIC_WM_GATEWAY_ADMIN_PASSWORD` - wM Gateway admin password
- `APIC_WM_GATEWAY_ENC_KEY` - wM Gateway encryption key
- `APIC_DEVPORTAL_ENC_KEY` - DevPortal encryption key

### Component Configuration
- `APIC_MGMT_REPLICAS` - Management replica count
- `APIC_ANALYTICS_REPLICAS` - Analytics replica count
- `APIC_WM_GATEWAY_REPLICAS` - wM Gateway replica count
- `APIC_AI_GATEWAY_REPLICAS` - AI Gateway replica count
- ... and license acceptance flags

### Deployment Options
- `APIC_DEPLOY_CORE` - Deploy management cluster
- `APIC_DEPLOY_ANALYTICS` - Deploy analytics
- `APIC_DEPLOY_DEVPORTAL` - Deploy developer portal
- `APIC_DEPLOY_WM_GATEWAY` - Deploy wM API Gateway
- `APIC_DEPLOY_AI_GATEWAY` - Deploy AI DataPower Gateway

See `config.env.template` for the complete list with documentation.

## Benefits

✓ **Single Source of Truth** - All configuration in one file
✓ **Environment Switching** - Easy to create dev/test/prod configs
✓ **Version Control Friendly** - Commit templates, not actual values
✓ **Automation Ready** - Perfect for CI/CD pipelines
✓ **No Hardcoding** - All environment-specific values are variables
✓ **Helm-like Experience** - Familiar values-based approach

## File Structure

```
v12.1.0.1-v2/
├── config.env.template         # Template with all variables documented
├── config.env                  # Your actual configuration (git-ignored)
├── 00-START-HERE.txt          # Quick start guide
├── 00-CONFIGURE.txt           # Configuration guide
├── INDEX.yaml                 # Package index with phases
├── core/                      # Core deployment
│   ├── 01-operators/          # Operators and CRDs
│   ├── 02-prerequisites/      # Prerequisites (cert-manager, ingress)
│   ├── 03-management/         # Management cluster
│   └── DEPLOY-CORE.txt       # Core deployment instructions
├── sub-components/            # Optional components
│   ├── 01-analytics/         # Analytics
│   ├── 02-wm-devportal/      # wM Developer Portal
│   ├── 03-wm-gateway/        # wM API Gateway
│   └── 04-ai-gateway/        # AI DataPower Gateway
├── ingress/                   # Contour HTTPProxy resources
└── utilities/                 # Helper scripts and tools
    ├── busybox/              # PVC cleanup utility
    ├── register-services/    # Service registration guides
    ├── envsubst-yaml.sh      # Template processor
    └── create-secrets.sh     # Secret creation helper
```

## Creating New Packages

Use the `/create-package` command to create new deployment packages based on this structure:

```bash
/create-package
```

The command will:
1. Auto-detect the next available version (e.g., v3, v4, v5)
2. Ask for configuration values (domain, registry, storage, etc.)
3. Copy files from v12.1.0.1-local source
4. Convert to parameterized templates
5. Generate config.env with your values
6. Create all helper scripts
7. Generate documentation

## Version Tracking

Package versions are tracked in `config-adp/.package-versions`:

```
v12.1.0.1-v2|2026-02-19|IBM API Connect v12.1.0.1 parameterized reference package
v12.1.0.1-v3|2026-02-19|IBM API Connect v12.1.0.1 deployment package
```

## Deployment Workflow

### Option 1: Manual Step-by-Step
```bash
source config.env
utilities/envsubst-yaml.sh core/03-management/06-management-cr.yaml.template | kubectl apply -f -
```

### Option 2: Using Helper Scripts
```bash
source config.env
utilities/deploy.sh core/
utilities/deploy.sh sub-components/01-analytics/
```

### Option 3: Follow Instructions
```bash
source config.env
# Follow step-by-step instructions in DEPLOY-CORE.txt
cat core/DEPLOY-CORE.txt
```

## Testing Packages

Use the `/test-package` command to validate a deployment package:

```bash
/test-package v12.1.0.1-v2
```

This will execute all status checks and generate a test report.

## Documentation

- **00-START-HERE.txt** - Quick start guide
- **00-CONFIGURE.txt** - Detailed configuration guide
- **config.env.template** - Comprehensive variable reference
- **core/DEPLOY-CORE.txt** - Core deployment instructions
- **sub-components/*/COMMANDS.txt** - Component-specific instructions
- **utilities/register-services/REGISTER-SERVICES.txt** - Service registration guide

## Author

Generated by Claude Code `/create-package` command

## Version

Package: v12.1.0.1-v2
APIC Version: 12.1.0.1
Created: 2026-02-19
