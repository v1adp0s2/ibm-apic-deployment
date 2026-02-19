# MailDev Test Mail Server

MailDev is a simple email testing tool for developers. Built with Node.js, it catches all outgoing emails and provides a modern web interface to view them without actually sending emails to real addresses.

## Features

- **Modern UI**: Clean, responsive web interface
- **Attachment Support**: View email attachments inline
- **Auto-update**: Web UI auto-refreshes when new emails arrive
- **REST API**: Programmatic access to emails
- **Multiple formats**: View HTML and plain text versions

## Files in this directory

- `maildev-2.2.1-amd64.tar.gz` - Docker image archive for amd64 (57 MB compressed)
- `maildev-deployment.yaml.template` - Kubernetes Deployment, Services, and PVC (template)
- `contour-httpproxy-maildev.yaml.template` - HTTPProxy for web UI access (template)
- `DEPLOY-MAILDEV.txt` - Complete deployment guide with step-by-step instructions

## Deployment Pattern

This utility uses the **envsubst piped to kubectl** pattern, consistent with the v12.1.0.1-v3 package:

```bash
envsubst < template.yaml.template | kubectl apply -f -
```

**Benefits:**
- No intermediate files created
- Environment variables substituted at deployment time
- Idempotent (safe to run multiple times)
- Consistent with core deployment pattern

**Required Environment Variables:**
- `APIC_NAMESPACE` - Kubernetes namespace (e.g., ibm-apic)
- `APIC_DOMAIN_BASE` - Base domain (e.g., demo01.mea-presales.org)
- `APIC_IMAGE_REGISTRY` - Container registry (e.g., harbor.talos.zebra-cloud.net/apic)
- `APIC_STORAGE_CLASS` - Storage class (e.g., nfs-ssd)

## Quick Start

See **DEPLOY-MAILDEV.txt** for complete deployment instructions.

### 1. Load the image (if needed)

```bash
docker load -i maildev-2.2.1-amd64.tar.gz
docker tag maildev/maildev:2.2.1 ${APIC_IMAGE_REGISTRY}/maildev:2.2.1
docker push ${APIC_IMAGE_REGISTRY}/maildev:2.2.1
```

### 2. Deploy to Kubernetes

```bash
cd utilities/maildev

# Set environment variables
export APIC_NAMESPACE=ibm-apic
export APIC_DOMAIN_BASE=demo01.mea-presales.org
export APIC_IMAGE_REGISTRY=harbor.talos.zebra-cloud.net/apic
export APIC_STORAGE_CLASS=nfs-ssd

# Deploy MailDev
envsubst < maildev-deployment.yaml.template | kubectl apply -f -
envsubst < contour-httpproxy-maildev.yaml.template | kubectl apply -f -
```

### 3. Verify deployment

```bash
kubectl get pods -n ibm-apic -l app=maildev
kubectl get svc -n ibm-apic -l app=maildev
kubectl get httpproxy -n ibm-apic maildev-web
```

## Access

- **Web UI**: http://maildev-apic.${APIC_DOMAIN_BASE}
- **SMTP Server** (internal): maildev-smtp.${APIC_NAMESPACE}.svc.cluster.local:25

## Configure API Connect

In Cloud Manager UI (Resources → Notifications → Create):

```
Title: MailDev Test Server
Host: maildev-smtp.ibm-apic.svc.cluster.local
Port: 25
Secure Connection: No
Authentication: No
Email Address: noreply@apic.local
Display Name: API Connect
```

Click "Test connection" then "Save" and "Set as default".

## Ports

- **Port 1025**: SMTP server (accepts all emails)
- **Port 1080**: Web UI to view captured emails
- **Port 25**: SMTP alias (for standard mail client compatibility)

## Web UI Features

The MailDev web interface provides:

- **Email List**: All captured emails with subject, sender, recipient
- **Email Preview**: Click to view full email with HTML rendering
- **Attachments**: Download or view attachments inline
- **Source View**: View raw email source
- **Delete**: Remove individual emails or clear all
- **REST API**: Access emails programmatically at `/email`

## REST API Examples

```bash
# Get all emails
curl http://maildev-apic.${APIC_DOMAIN_BASE}/email

# Get specific email
curl http://maildev-apic.${APIC_DOMAIN_BASE}/email/{id}

# Delete all emails
curl -X DELETE http://maildev-apic.${APIC_DOMAIN_BASE}/email/all
```

## Use Cases

Perfect for testing:
- Password reset emails
- User invitation emails
- API Connect notifications
- Developer Portal emails
- Catalog subscription confirmations

All emails are captured and displayed without actually sending to real addresses!

## Resource Usage

- **Storage**: 5Gi PVC (nfs-ssd storage class)
- **Memory**: 128Mi request, 256Mi limit
- **CPU**: 100m request, 200m limit
- **Replicas**: 1 (development tool only)

## Important Notes

⚠️  **WARNING: MailDev is for DEVELOPMENT/TESTING ONLY!**

DO NOT use in production environments:
- No authentication or security
- Emails stored locally, not delivered
- No TLS/SSL encryption
- Single replica only (no HA)

For production, use a real SMTP server (SendGrid, Amazon SES, etc.)

## Uninstall

```bash
kubectl delete httpproxy maildev-web -n ibm-apic
kubectl delete deployment maildev -n ibm-apic
kubectl delete service maildev maildev-smtp -n ibm-apic
kubectl delete pvc maildev-data -n ibm-apic
```

## Documentation

For complete deployment instructions, configuration, testing procedures, and troubleshooting, see:
- **DEPLOY-MAILDEV.txt** - Comprehensive deployment guide
