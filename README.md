# IBM API Connect 10.0.8.6 - Kubernetes Deployment

Kubernetes deployment manifests and configuration for IBM API Connect platform, including API Gateway (DataPower), Developer Portal, Management, and Analytics subsystems.

## Repository Structure

```
apic-deployment/
├── .env                        # Environment variables (registry credentials, namespace)
├── DEPLOYMENT-GUIDE.md         # Detailed step-by-step deployment instructions
├── README.md                   # This file
├── steps.md                    # Quick reference commands
├── cert-manager/               # cert-manager installation files
│   └── cert-manager-1.19.2.yaml
├── apiconnect-operator/        # IBM operator release files (working directory)
│   ├── apiconnect-operator-release-files_10.0.8.6.zip
│   ├── ibm-apiconnect-crds.yaml
│   ├── ibm-apiconnect.yaml
│   ├── ibm-datapower.yaml
│   └── helper_files/           # CR templates and cert-manager configs
│       ├── ingress-issuer-v1.yaml
│       ├── management_cr.yaml
│       ├── apigateway_cr.yaml
│       ├── portal_cr.yaml
│       ├── analytics_cr.yaml
│       └── ...
└── config-adp/                 # Ready-to-deploy package (example.com domain)
    ├── README.md
    ├── 01-ibm-apiconnect-crds.yaml
    ├── 02-ibm-apiconnect-operator.yaml
    ├── 03-ibm-datapower-operator.yaml
    ├── 04-ingress-issuer.yaml
    ├── 05-management-cr.yaml
    ├── 06-apigateway-cr.yaml
    ├── 07-portal-cr.yaml
    └── 08-analytics-cr.yaml
```

## Architecture

IBM API Connect consists of four subsystems deployed as Kubernetes Custom Resources:

| Subsystem | CR Kind | Description |
|-----------|---------|-------------|
| Management | `ManagementCluster` | Cloud Manager UI, API Manager UI, Platform API |
| Gateway | `GatewayCluster` | DataPower API Gateway for runtime traffic |
| Portal | `PortalCluster` | Developer Portal for API consumers |
| Analytics | `AnalyticsCluster` | API analytics and monitoring |

Two operators manage the lifecycle of these subsystems:
- **ibm-apiconnect operator** - manages Management, Portal, and Analytics
- **datapower-operator** - manages the DataPower Gateway

## Prerequisites

- Kubernetes cluster (1.27+)
- Ingress controller (Traefik, NGINX, or similar)
- cert-manager (v1.16+)
- Storage class with ReadWriteOnce support (e.g. `nfs-ssd`)
- IBM entitlement key from [My IBM Container Software Library](https://myibm.ibm.com/products-services/containerlibrary)
- Private container registry (Harbor, Docker Hub, etc.)

## Image Mirroring

APIC images must be mirrored to a private registry before deployment. They cannot be pulled directly from `cp.icr.io` at runtime for subsystem components.

1. Download `apiconnect-image-tool-10.0.8.6.tar.gz` from [IBM Fix Central](https://www.ibm.com/support/fixcentral/)
2. Load the tool: `docker load < apiconnect-image-tool-10.0.8.6.tar.gz`
3. Upload to your registry:
   ```bash
   # Harbor
   docker run --rm apiconnect-image-tool-10.0.8.6 upload \
     harbor.example.com/apic \
     --username <USER> --password <PASSWORD> --tls-verify=false

   # Docker Hub
   docker run --rm apiconnect-image-tool-10.0.8.6 upload \
     docker.io/<USERNAME> \
     --username <USERNAME> --password <TOKEN>
   ```

**Important:** The image-tool version must match the operator-release-files version (both `10.0.8.6`).

## Deployment

### Option 1: Use the ready-made config package

The `config-adp/` directory contains fully configured manifests with `adp.example.com` as the domain. Replace with your actual domain and registry, then apply in order. See [config-adp/README.md](config-adp/README.md).

### Option 2: Configure from operator release files

Use the raw templates in `apiconnect-operator/helper_files/` and replace the `$PLACEHOLDER` variables. See [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) for the full step-by-step process.

### Deployment Order

```
1. cert-manager
2. CRDs (--server-side --force-conflicts)
3. API Connect operator
4. DataPower operator
5. Ingress issuer
6. Management subsystem (wait 10-15 min)
7. Gateway subsystem
8. Portal subsystem
9. Analytics subsystem
```

## Configuration Reference

### Environment Variables (.env)

| Variable | Description |
|----------|-------------|
| `IBM_ENTITLEMENT_KEY` | IBM Container Library entitlement key |
| `IBM_IMAGE_SERVER` | IBM registry (`cp.icr.io`) |
| `APIC_NAMESPACE` | Target Kubernetes namespace |
| `APIC_ADMIN_PWD` | DataPower admin password |
| `REGISTRY_SERVER` | Private registry hostname |
| `REGISTRY_PROJECT` | Registry project/org name |
| `REGISTRY_USERNAME` | Registry credentials |
| `REGISTRY_USERPWD` | Registry credentials |

### Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `version` | APIC product version | `10.0.8.6` |
| `profile` | Resource profile | `n1xc4.m16` (small), `n3xc4.m16` (HA) |
| `imageRegistry` | Private registry path | `harbor.example.com/apic` |
| `imagePullSecrets` | K8s docker-registry secret | `harbor-registry-secret` |
| `storageClassName` | K8s storage class | `nfs-ssd` |
| `ingressClassName` | Ingress controller | `traefik` |
| `license.license` | IBM license ID | `L-HTFS-UAXYM3` |

### Endpoints Pattern

All endpoints follow `<service>.apic.<domain>`:

| Endpoint | Hostname |
|----------|----------|
| Cloud Manager | `admin.apic.<domain>` |
| API Manager | `manager.apic.<domain>` |
| Platform API | `api.apic.<domain>` |
| Consumer API | `consumer.apic.<domain>` |
| Consumer Catalog | `consumer-catalog.apic.<domain>` |
| Gateway | `rgw.apic.<domain>` |
| Gateway Manager | `rgwd.apic.<domain>` |
| Portal UI | `portal.apic.<domain>` |
| Portal Admin | `api.portal.apic.<domain>` |
| Analytics | `ai.apic.<domain>` |

DNS: Create a wildcard record `*.apic.<domain>` pointing to your cluster ingress IP.

## Known Issues

- **CRDs require `--server-side --force-conflicts`** since 10.0.8.0 due to increased CRD sizes
- **DataPower operator YAML ships with `namespace: default`** in RoleBinding subjects - must be updated to match your target namespace
- **IBM Entitled Registry (`cp.icr.io`) username must be `cp`**, not your IBM ID email
- **EDB operator image** may fail to pull from `cp.icr.io` directly - use a private registry with `apiconnect-image-tool`

## References

- [IBM API Connect 10.0.8 LTS Documentation](https://www.ibm.com/docs/en/api-connect/10.0.8_lts)
- [IBM Fix Central](https://www.ibm.com/support/fixcentral/)
- [IBM Container Software Library](https://myibm.ibm.com/products-services/containerlibrary)
- [API Connect Licenses](https://www.ibm.com/docs/en/api-connect/10.0.8_lts?topic=connect-api-licenses)
