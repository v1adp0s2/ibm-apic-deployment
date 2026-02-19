# Contour Ingress Controller - API Connect Endpoints

## Overview

API Connect v12.1.0.1 on Talos cluster is now configured to use **Contour ingress controller** alongside nginx.

### Ingress Controller Details

| Controller | LoadBalancer IP | DNS Pattern | Status |
|------------|----------------|-------------|---------|
| **Contour** | `10.20.221.222` | `*.demo01.mea-presales.org` | ✅ Active (Management, Gateway, Portal, Analytics) |
| nginx | `10.20.221.220` | `*.talos-nginx.zebra-cloud.net` | ⚠️ Inactive (replaced by Contour) |

## DNS Configuration Required

Configure your DNS server with wildcard A records:

```
*.demo01.mea-presales.org  A  10.20.221.222
```

## API Connect Endpoints (Contour)

### Management Subsystem

| Endpoint | URL | TLS Certificate |
|----------|-----|-----------------|
| Cloud Manager | `https://admin.apic.demo01.mea-presales.org/admin` | ✅ cert-manager (cm-endpoint) |
| API Manager | `https://manager.apic.demo01.mea-presales.org/manager` | ✅ cert-manager (apim-endpoint) |
| Platform API | `https://api.apic.demo01.mea-presales.org/` | ✅ cert-manager (api-endpoint) |
| Consumer API | `https://consumer.apic.demo01.mea-presales.org/` | ✅ cert-manager (consumer-endpoint) |
| Consumer Catalog | `https://consumer-catalog.apic.demo01.mea-presales.org/` | ✅ cert-manager (consumer-catalog-endpoint) |

### Gateway Subsystem

| Endpoint | URL | TLS Certificate |
|----------|-----|-----------------|
| API Gateway | `https://rgw.apic.demo01.mea-presales.org/` | ✅ cert-manager (gwv6-endpoint) |
| Gateway Manager | `https://rgwd.apic.demo01.mea-presales.org/` | ✅ cert-manager (gwv6-manager-endpoint) |

### Portal Subsystem

| Endpoint | URL | TLS Certificate |
|----------|-----|-----------------|
| Portal Admin | `https://api.portal.apic.demo01.mea-presales.org/` | ✅ cert-manager (portal-admin) |
| Portal UI | `https://portal.apic.demo01.mea-presales.org/` | ✅ cert-manager (portal-web) |

### Analytics Subsystem

| Endpoint | URL | TLS Certificate |
|----------|-----|-----------------|
| Analytics Ingestion | `https://ai.apic.demo01.mea-presales.org/` | ✅ cert-manager (analytics-ai-endpoint) |

## Contour Configuration

### IngressClass

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: contour
spec:
  controller: projectcontour.io/ingress-controller
```

### cert-manager Integration

Contour automatically integrates with cert-manager using the annotation:

```yaml
annotations:
  cert-manager.io/issuer: ingress-issuer
```

## Verify Contour Installation

### Check Contour Pods

```bash
kubectl get pods -n projectcontour
```

Expected output:
```
NAME                            READY   STATUS      RESTARTS   AGE
contour-697c75758b-m7pgg        1/1     Running     0          Xm
contour-697c75758b-nlwg8        1/1     Running     0          Xm
contour-certgen-v1-33-1-dlj4x   0/1     Completed   0          Xm
```

### Check Contour Service

```bash
kubectl get svc -n projectcontour
```

Expected output:
```
NAME      TYPE           CLUSTER-IP       EXTERNAL-IP     PORT(S)                      AGE
contour   ClusterIP      10.110.248.210   <none>          8001/TCP                     Xm
envoy     LoadBalancer   10.107.27.190    10.20.221.222   80:30311/TCP,443:30395/TCP   Xm
```

### Check Ingresses

```bash
kubectl get ingress -n apic -o wide
```

All Management ingresses should show:
- **CLASS**: `contour`
- **ADDRESS**: `10.20.221.222`

## Testing Contour Endpoints

### Test Cloud Manager

```bash
curl -k -I https://admin.apic.demo01.mea-presales.org/admin
```

Expected: HTTP 200 or redirect to login page

### Test Certificate

```bash
openssl s_client -connect admin.apic.demo01.mea-presales.org:443 -servername admin.apic.demo01.mea-presales.org < /dev/null 2>&1 | grep -A 2 "subject="
```

Expected: Certificate issued by ingress-issuer

## Switching Between Ingress Controllers

### Current Configuration

- **Management**: ✅ Contour (talos-pc.zebra-cloud.net)
- **Gateway**: ✅ Contour (talos-pc.zebra-cloud.net)
- **Portal**: ✅ Contour (talos-pc.zebra-cloud.net)
- **Analytics**: ✅ Contour (talos-pc.zebra-cloud.net)

### To Revert to nginx

Edit the subsystem CRs and change:
- `ingressClassName: contour` → `ingressClassName: nginx`
- Update hostnames to use `talos-nginx.zebra-cloud.net`

Then apply:
```bash
kubectl patch managementcluster management -n apic --type=merge --patch '{"spec":{"cloudManagerEndpoint":{"ingressClassName":"nginx"}}}'
```

## Troubleshooting

### Ingress not getting LoadBalancer IP

Check Contour envoy service:
```bash
kubectl get svc envoy -n projectcontour
```

### Certificate not being issued

Check certificate status:
```bash
kubectl describe certificate cm-endpoint -n apic
```

Check cert-manager logs:
```bash
kubectl logs -n cert-manager -l app=cert-manager
```

### Contour pods not running

Check pod status:
```bash
kubectl describe pod -n projectcontour -l app=contour
```

Check events:
```bash
kubectl get events -n projectcontour --sort-by='.lastTimestamp'
```

## Completed Steps

1. ✅ Contour installed and configured
2. ✅ Management subsystem using Contour
3. ✅ Gateway subsystem using Contour
4. ✅ Portal subsystem using Contour
5. ✅ Analytics subsystem using Contour
6. ✅ Configure DNS wildcard for `*.demo01.mea-presales.org`
7. ✅ All certificates issued and ready
8. ⏳ Test all endpoints (waiting for DNS propagation)
