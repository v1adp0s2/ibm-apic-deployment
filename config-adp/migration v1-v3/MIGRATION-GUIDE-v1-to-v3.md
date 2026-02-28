# IBM API Connect v12.1.0.1 — Migration Guide: v1 → v3 Package

> **Versions covered:**
> - **Source:** `config-adp/v12.1.0.1` (referred to as **v1**)
> - **Target:** `config-adp/v12.1.0.1-v3` (referred to as **v3**)

---

## Overview

The v3 package is a complete architectural rework of the v1 package for the same IBM API Connect `12.1.0.1` release. The APIC software version does **not** change — what changes is how the deployment is structured, configured, and executed.

### What Changed at a Glance

| Aspect | v1 | v3 |
|---|---|---|
| Configuration method | `sed` commands on static YAML files | `envsubst` on `.yaml.template` files |
| Single config source | No (scattered placeholders) | Yes (`config.env`) |
| File organization | Flat (all YAMLs in root) | Hierarchical (`core/`, `sub-components/`, `ingress/`, `utilities/`) |
| Template format | `NAMESPACE_PLACEHOLDER`, `DNS_PLACEHOLDER` | `${APIC_NAMESPACE}`, `${APIC_DOMAIN_BASE}` |
| DNS hostname pattern | `admin.example.com` | `admin-apic.example.com` |
| cert-manager version | v1.13.2 (pre-downloaded) | v1.19.2 (online install) |
| Management profile | `n3xc4.m16` | `n1xc4.m16` |
| CI/CD automation | Moderate | High |
| AI Gateway support | No | Yes |
| webMethods Gateway support | No | Yes |
| Maildev email utility | No | Yes |
| Service registration guides | Manual | Step-by-step guided utilities |

---

## Pre-Migration Checklist

Before starting, complete these checks:

- [ ] You have a **backup** of your current v1 configuration (YAML files with actual values)
- [ ] You know your current values for: namespace, domain, registry, storage class, passwords
- [ ] Your cluster is accessible (`kubectl cluster-info` or `oc whoami` succeeds)
- [ ] The existing APIC deployment is healthy (or you are doing a fresh migration)
- [ ] You have the v3 package directory available at `config-adp/v12.1.0.1-v3/`

---

## Step 1 — Understand the New Directory Structure

The v3 package introduces a hierarchical structure. Map your v1 files to their v3 equivalents:

### v1 → v3 File Mapping

| v1 File | v3 Equivalent | Notes |
|---|---|---|
| `00-CONFIGURE.txt` | `00-CONFIGURE.txt` | Updated for env var approach |
| `DEPLOYMENT-GUIDE.txt` | `core/DEPLOY-CORE.txt` + per-component `COMMANDS.txt` | Split into modular guides |
| `01-ibm-apiconnect-crds.yaml` | `core/01-operators/01-ibm-apiconnect-crds.yaml` | Static, unchanged |
| `02-ibm-apiconnect-operator.yaml` | `core/01-operators/02-apiconnect-operator.yaml.template` | Now a template |
| `03-ibm-datapower-operator.yaml` | `core/01-operators/03-datapower-operator.yaml.template` | Now a template |
| `04-ingress-issuer.yaml` | `core/02-prerequisites/04-ingress-issuer.yaml` | Static, unchanged |
| `09-contour-ingressclass.yaml` | `core/02-prerequisites/05-contour-ingressclass.yaml` | Static, unchanged |
| `05-management-cr.yaml` | `core/03-management/06-management-cr.yaml.template` | Template, profile changed |
| `06-apigateway-cr.yaml` | `sub-components/03-wm-gateway/wm-gateway-cr.yaml.template` | Replaced by wM Gateway |
| `07-portal-cr.yaml` | `sub-components/02-wm-devportal/devportal-cr.yaml.template` | Now a template |
| `08-analytics-cr.yaml` | `sub-components/01-analytics/analytics-cr.yaml.template` | Now a template |
| `10-httpproxy-management.yaml` | `ingress/contour-httpproxy-management.yaml.template` | Now a template |
| `11-httpproxy-gateway.yaml` | `ingress/contour-httpproxy-gateway.yaml.template` | Now a template |
| `12-httpproxy-portal.yaml` | `ingress/contour-httpproxy-devportal.yaml.template` | Now a template |
| `13-httpproxy-analytics.yaml` | `ingress/contour-httpproxy-analytics.yaml.template` | Now a template |
| `cert-manager/cert-manager-v1.13.2.yaml` | `utilities/cert-manager/cert-manager-v1.19.2.yaml.template` | Version updated |
| `busybox/clear-pvc-pod.yaml` | `utilities/busybox/clear-pvc-pod.yaml.template` | Now a template |
| _(not present)_ | `sub-components/04-ai-gateway/` | **New**: AI Gateway |
| _(not present)_ | `utilities/maildev/` | **New**: Email testing utility |
| _(not present)_ | `utilities/register-services/` | **New**: Service registration guides |

---

## Step 2 — Understand the Configuration Approach Change

### v1: sed-based Placeholder Replacement

In v1 you ran `sed` commands to replace tokens directly inside YAML files:

```bash
# v1 approach — modifies files in place
export NAMESPACE="apic"
export DNS_DOMAIN="adp.example.com"
export REGISTRY="harbor.example.com/apic"

find . -type f -name "*.yaml" -exec sed -i \
  -e "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" \
  -e "s/DNS_PLACEHOLDER/$DNS_DOMAIN/g" \
  -e "s|REGISTRY_PLACEHOLDER|$REGISTRY|g" \
  {} \;
```

**Problems with this approach:**
- Irreversibly modifies files (produces `.bak` files)
- Easy to miss a placeholder
- Environment-specific values end up in version control
- Multiple sed calls required, order matters

### v3: Environment Variable + envsubst Approach

In v3 all configuration lives in a single `config.env` file. Templates are processed at deploy time using the standard `envsubst` tool:

```bash
# v3 approach — files are never modified
source /path/to/v12.1.0.1-v3/config.env

# Deploy a component by substituting variables at apply time
envsubst < core/03-management/06-management-cr.yaml.template | kubectl apply -f -
```

**Advantages:**
- Templates stay pristine in version control
- Single file to edit: `config.env`
- Standard POSIX tool (`envsubst`) — no custom scripts
- CI/CD and GitOps friendly

---

## Step 3 — Collect Your Current v1 Values

Before setting up v3 configuration, record what you used in v1. Use this table:

| v1 Placeholder | Your Current Value | v3 Variable Name |
|---|---|---|
| `NAMESPACE_PLACEHOLDER` | _________________ | `APIC_NAMESPACE` |
| `DNS_PLACEHOLDER` | _________________ | `APIC_DOMAIN_BASE` |
| `REGISTRY_PLACEHOLDER` | _________________ | `APIC_IMAGE_REGISTRY` |
| `PULL_SECRET_PLACEHOLDER` | _________________ | `APIC_IMAGE_PULL_SECRET` |
| `STORAGE_CLASS_PLACEHOLDER` | _________________ | `APIC_STORAGE_CLASS` |
| `INGRESS_CLASS_PLACEHOLDER` | _________________ | `APIC_INGRESS_CLASS` |
| Admin password (from secret) | _________________ | `APIC_MGMT_ADMIN_PASSWORD` |
| DataPower admin password | _________________ | `APIC_DATAPOWER_ADMIN_PASSWORD` |

---

## Step 4 — Create Your `config.env`

Navigate to the v3 directory and copy the template:

```bash
cd /path/to/config-adp/v12.1.0.1-v3/

cp config.env.template config.env
```

Edit `config.env` and fill in your values. The minimum required variables are:

```bash
# ── Core ──────────────────────────────────────────────────────────────
APIC_NAMESPACE="apic"                          # Kubernetes namespace
APIC_DOMAIN_BASE="adp.example.com"             # Base domain (no wildcard)
APIC_IMAGE_REGISTRY="harbor.example.com/apic"  # Container image registry
APIC_IMAGE_PULL_SECRET="apic-registry-secret"  # Image pull secret name
APIC_STORAGE_CLASS="nfs-ssd"                   # StorageClass for PVCs
APIC_INGRESS_CLASS="contour"                   # IngressClass name

# ── Secrets ───────────────────────────────────────────────────────────
APIC_MGMT_ADMIN_PASSWORD="<your-admin-password>"
APIC_DATAPOWER_ADMIN_PASSWORD="<your-dp-password>"
APIC_WM_GATEWAY_ADMIN_PASSWORD="<your-wm-gw-password>"   # if using wM Gateway
APIC_DEVPORTAL_ENC_KEY=""    # leave empty to auto-generate
APIC_WM_GATEWAY_ENC_KEY=""   # leave empty to auto-generate

# ── Registry Credentials ───────────────────────────────────────────────
APIC_REGISTRY_SERVER="harbor.example.com"
APIC_REGISTRY_USERNAME="<username>"
APIC_REGISTRY_PASSWORD="<password>"
```

The config.env template contains full documentation for every variable. Review all sections before deploying.

### Verify Configuration

Source the file and check that all required variables are set:

```bash
source config.env
# The config.env file includes a validate_config() function
validate_config
```

---

## Step 5 — Understand the DNS Hostname Change

> **Important:** v3 renames all public endpoints. DNS records and any API consumer bookmarks must be updated.

### Hostname Mapping (v1 → v3)

| Service | v1 Hostname | v3 Hostname |
|---|---|---|
| Cloud Manager UI | `admin.DNS_PLACEHOLDER` | `admin-apic.${APIC_DOMAIN_BASE}` |
| API Manager UI | `manager.DNS_PLACEHOLDER` | `manager-apic.${APIC_DOMAIN_BASE}` |
| Platform API | `api.DNS_PLACEHOLDER` | `api-apic.${APIC_DOMAIN_BASE}` |
| Consumer API | `consumer.DNS_PLACEHOLDER` | `consumer-apic.${APIC_DOMAIN_BASE}` |
| Consumer Catalog | `consumer-catalog.DNS_PLACEHOLDER` | `consumer-catalog-apic.${APIC_DOMAIN_BASE}` |
| Analytics Ingestion | `ai.DNS_PLACEHOLDER` | `ai-apic.${APIC_DOMAIN_BASE}` |
| DataPower Gateway | `rgw.DNS_PLACEHOLDER` | _(replaced by wM Gateway)_ |
| DataPower Gateway Director | `rgwd.DNS_PLACEHOLDER` | _(replaced by wM Gateway)_ |
| Dev Portal Admin | `api.portal.DNS_PLACEHOLDER` | `admin-devportal-apic.${APIC_DOMAIN_BASE}` |
| Dev Portal UI | `portal.DNS_PLACEHOLDER` | `devportal-apic.${APIC_DOMAIN_BASE}` |
| wM API Gateway | _(not in v1)_ | `wmapigw-apic.${APIC_DOMAIN_BASE}` |
| wM API Gateway UI | _(not in v1)_ | `wmapigw-ui-apic.${APIC_DOMAIN_BASE}` |
| AI Gateway | _(not in v1)_ | `ai-rgw-apic.${APIC_DOMAIN_BASE}` |
| AI Gateway Director | _(not in v1)_ | `ai-rgwd-apic.${APIC_DOMAIN_BASE}` |
| Maildev | _(not in v1)_ | `maildev-apic.${APIC_DOMAIN_BASE}` |

Update your DNS wildcard record or individual A/CNAME records to include the new hostnames before proceeding.

---

## Step 6 — Upgrade cert-manager (v1.13.2 → v1.19.2)

v1 shipped with a pre-downloaded cert-manager `v1.13.2`. v3 uses `v1.19.2`.

### Check Current cert-manager Version

```bash
kubectl get deployment cert-manager -n cert-manager \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Upgrade cert-manager

```bash
source config.env

# Apply the v3 cert-manager template
envsubst < utilities/cert-manager/cert-manager-v1.19.2.yaml.template | kubectl apply -f -

# Wait for cert-manager pods to be ready
kubectl rollout status deployment/cert-manager -n cert-manager
kubectl rollout status deployment/cert-manager-webhook -n cert-manager
kubectl rollout status deployment/cert-manager-cainjector -n cert-manager
```

Verify:
```bash
kubectl get pods -n cert-manager
cmctl version   # should report v1.19.2 server
```

---

## Step 7 — Note the Management Profile Change

> **Breaking change:** The `ManagementCluster` resource profile changed between v1 and v3.

| Setting | v1 | v3 |
|---|---|---|
| `spec.profile` | `n3xc4.m16` | `n1xc4.m16` |

`n1xc4.m16` uses fewer nodes (1 instead of 3) which is more appropriate for demo/non-production environments. If your environment requires `n3xc4.m16` (production sizing), edit `core/03-management/06-management-cr.yaml.template` before deploying:

```yaml
# core/03-management/06-management-cr.yaml.template
spec:
  profile: n3xc4.m16   # override if needed
```

---

## Step 8 — New Client Secrets in Management CR

The v3 `ManagementCluster` adds new `clientSubsystems` secrets that were not present in v1. These enable the new sub-components (wM Gateway, AI Gateway, DevPortal). They are automatically created by the deployment templates.

New secrets added in v3:
- `wm-devportal-admin-client` — webMethods Developer Portal integration
- `wm-gateway-mgmt-client` — webMethods API Gateway management
- `ai-gateway-mgmt-client` — AI Gateway management
- `federatedapimanagement-admin-client` — Federated API Management

No manual action is required — these are handled by the templates.

---

## Step 9 — Deploy Core Components

With configuration ready, deploy the core stack using the v3 modular approach.

```bash
cd /path/to/config-adp/v12.1.0.1-v3/
source config.env
```

### 9.1 — Namespace and Registry Secret

```bash
kubectl create namespace ${APIC_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret docker-registry ${APIC_IMAGE_PULL_SECRET} \
  --docker-server=${APIC_REGISTRY_SERVER} \
  --docker-username=${APIC_REGISTRY_USERNAME} \
  --docker-password=${APIC_REGISTRY_PASSWORD} \
  --namespace=${APIC_NAMESPACE} \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 9.2 — Operators

```bash
# CRDs (static — apply directly)
kubectl apply -f core/01-operators/01-ibm-apiconnect-crds.yaml

# API Connect Operator (templated)
envsubst < core/01-operators/02-apiconnect-operator.yaml.template | kubectl apply -f -

# DataPower Operator (templated)
envsubst < core/01-operators/03-datapower-operator.yaml.template | kubectl apply -f -

# Wait for operators to be ready
kubectl rollout status deployment/ibm-apiconnect -n ${APIC_NAMESPACE}
kubectl rollout status deployment/datapower-operator -n ${APIC_NAMESPACE}
```

### 9.3 — Prerequisites (Ingress Issuer + IngressClass)

```bash
# Static files — apply directly
kubectl apply -f core/02-prerequisites/04-ingress-issuer.yaml
kubectl apply -f core/02-prerequisites/05-contour-ingressclass.yaml

# Wait for CA certificate to be issued
kubectl wait --for=condition=Ready certificate/ingress-ca \
  -n ${APIC_NAMESPACE} --timeout=120s
```

### 9.4 — Management Subsystem

```bash
envsubst < core/03-management/06-management-cr.yaml.template | kubectl apply -f -

# Monitor — takes 10-20 minutes on first install
kubectl get managementcluster -n ${APIC_NAMESPACE} -w
```

Wait until `STATUS` shows `Ready` before continuing.

### 9.5 — Management Ingress (HTTPProxy)

```bash
envsubst < ingress/contour-httpproxy-management.yaml.template | kubectl apply -f -
```

Verify management is reachable:
```bash
curl -k https://admin-apic.${APIC_DOMAIN_BASE}/
```

---

## Step 10 — Deploy Analytics (Required for DevPortal)

```bash
source config.env   # if in a new shell

envsubst < sub-components/01-analytics/analytics-cr.yaml.template | kubectl apply -f -

# Monitor
kubectl get analyticscluster -n ${APIC_NAMESPACE} -w
```

Wait until `STATUS` shows `Ready`.

Deploy Analytics ingress:
```bash
envsubst < ingress/contour-httpproxy-analytics.yaml.template | kubectl apply -f -
```

Refer to `sub-components/01-analytics/COMMANDS.txt` for full command reference.

---

## Step 11 — Deploy Developer Portal

> **Depends on:** Analytics must be `Ready` first (Step 10).

```bash
envsubst < sub-components/02-wm-devportal/devportal-cr.yaml.template | kubectl apply -f -

# Monitor
kubectl get portalcluster -n ${APIC_NAMESPACE} -w
```

Wait until `STATUS` shows `Ready`, then deploy ingress:
```bash
envsubst < ingress/contour-httpproxy-devportal.yaml.template | kubectl apply -f -
```

Refer to `sub-components/02-wm-devportal/COMMANDS.txt` for the full command reference.

---

## Step 12 — Deploy Gateway

> v1 used a DataPower `GatewayCluster`. v3 uses the **webMethods API Gateway** by default.

```bash
envsubst < sub-components/03-wm-gateway/wm-gateway-cr.yaml.template | kubectl apply -f -

# Monitor
kubectl get gatewaycluster -n ${APIC_NAMESPACE} -w
```

Wait until `STATUS` shows `Ready`, then deploy ingress:
```bash
envsubst < ingress/contour-httpproxy-gateway.yaml.template | kubectl apply -f -
```

Refer to `sub-components/03-wm-gateway/COMMANDS.txt` for the full command reference.

---

## Step 13 — Deploy AI Gateway (New in v3, Optional)

The AI Gateway is a new component not present in v1. Deploy it only if you need AI-enhanced routing.

```bash
envsubst < sub-components/04-ai-gateway/ai-gateway-cr.yaml.template | kubectl apply -f -

# Monitor
kubectl get gatewaycluster -n ${APIC_NAMESPACE} -w
```

Deploy ingress:
```bash
envsubst < ingress/contour-httpproxy-ai-gateway.yaml.template | kubectl apply -f -
```

Refer to `sub-components/04-ai-gateway/COMMANDS.txt` for the full command reference.

---

## Step 14 — Deploy Maildev (New in v3, Optional)

Maildev is a new email testing utility for development environments. It captures emails sent by the Management and DevPortal subsystems.

```bash
cd utilities/maildev/

envsubst < maildev-deployment.yaml.template | kubectl apply -f -
envsubst < contour-httpproxy-maildev.yaml.template | kubectl apply -f -
```

Access the Maildev UI at: `https://maildev-apic.${APIC_DOMAIN_BASE}`

Refer to `utilities/maildev/DEPLOY-MAILDEV.txt` for configuration details.

---

## Step 15 — Register Services with Management

After all components are `Ready`, register them with the Management subsystem. v3 provides guided utilities for this (not available in v1).

Follow the guides in order:

```
utilities/register-services/
├── REGISTER-SERVICES.txt          ← Start here (overview)
├── 01-REGISTER-ANALYTICS.txt      ← Register Analytics
├── 02-REGISTER-DEVPORTAL.txt      ← Register Developer Portal
├── 03-REGISTER-WM-GATEWAY.txt     ← Register webMethods Gateway
├── 04-REGISTER-AI-GATEWAY.txt     ← Register AI Gateway (if deployed)
└── 05-PROVIDER-ORG-AND-API-MANAGER.txt  ← Create Provider Org
```

Execute each guide's commands sequentially.

---

## Step 16 — Verify Full Deployment

```bash
source config.env

# Check all APIC custom resources
kubectl get managementcluster,analyticscluster,portalcluster,gatewaycluster \
  -n ${APIC_NAMESPACE}

# All pods should be Running
kubectl get pods -n ${APIC_NAMESPACE}

# Ingress / HTTPProxy routes
kubectl get httpproxy -n ${APIC_NAMESPACE}

# Certificate status
kubectl get certificate -n ${APIC_NAMESPACE}
```

Expected output — all resources should show `Ready` or `Running`.

### Access URLs (v3)

Replace `${APIC_DOMAIN_BASE}` with your actual domain:

| Component | URL |
|---|---|
| Cloud Manager | `https://admin-apic.${APIC_DOMAIN_BASE}` |
| API Manager | `https://manager-apic.${APIC_DOMAIN_BASE}` |
| Developer Portal | `https://devportal-apic.${APIC_DOMAIN_BASE}` |
| wM API Gateway | `https://wmapigw-apic.${APIC_DOMAIN_BASE}` |
| wM API Gateway UI | `https://wmapigw-ui-apic.${APIC_DOMAIN_BASE}` |
| AI Gateway | `https://ai-rgw-apic.${APIC_DOMAIN_BASE}` |
| Maildev | `https://maildev-apic.${APIC_DOMAIN_BASE}` |

---

## Rollback Procedure

If anything goes wrong and you need to revert to v1:

```bash
# Save v3 state for debugging
kubectl get all -n ${APIC_NAMESPACE} > v3-state-$(date +%Y%m%d).txt

# Remove v3 components in reverse order
kubectl delete gatewaycluster --all -n ${APIC_NAMESPACE}
kubectl delete portalcluster --all -n ${APIC_NAMESPACE}
kubectl delete analyticscluster --all -n ${APIC_NAMESPACE}
kubectl delete managementcluster --all -n ${APIC_NAMESPACE}

# Wait for cleanup, then redeploy v1 using your backed-up configured YAMLs
```

---

## Troubleshooting

### Certificate Not Issuing

```bash
kubectl describe certificate -n ${APIC_NAMESPACE}
kubectl get challenges -n ${APIC_NAMESPACE}
kubectl logs -n cert-manager -l app=cert-manager --tail=50
```

### ManagementCluster Stuck

```bash
kubectl describe managementcluster -n ${APIC_NAMESPACE}
kubectl get events -n ${APIC_NAMESPACE} --sort-by='.lastTimestamp' | tail -20
kubectl logs -n ${APIC_NAMESPACE} -l app.kubernetes.io/name=ibm-apiconnect --tail=50
```

### envsubst Leaves Unexpanded Variables

```bash
# Check which variables are missing
envsubst < core/03-management/06-management-cr.yaml.template | grep '\${APIC'

# List all variables expected by a template
grep -oP '\$\{[^}]+\}' core/03-management/06-management-cr.yaml.template | sort -u
```

### PVC Issues / Storage

Refer to `utilities/busybox/` for PVC cleanup procedures and `TROUBLESHOOTING-STORAGE.txt` in the v3 root.

---

## Summary of Changes by Category

### Configuration
- **Before:** Multiple `sed` commands modifying YAML files in place
- **After:** Edit `config.env` once, source it, use `envsubst` at deploy time

### Files
- **Before:** 13 static YAML files in a flat directory
- **After:** 10+ `.yaml.template` files organized in `core/`, `sub-components/`, `ingress/`, `utilities/`

### DNS
- **Before:** Short names (`admin.domain`, `manager.domain`)
- **After:** Scoped names (`admin-apic.domain`, `manager-apic.domain`)

### cert-manager
- **Before:** v1.13.2, pre-downloaded (45 MB in repo)
- **After:** v1.19.2, online install via template

### Management Sizing
- **Before:** Profile `n3xc4.m16` (3-node)
- **After:** Profile `n1xc4.m16` (1-node, non-production default)

### New Capabilities
- webMethods API Gateway sub-component
- AI Gateway sub-component
- Maildev email testing utility
- Guided service registration utilities
- Deployment logging (`deployment/` directory with timestamped logs)
