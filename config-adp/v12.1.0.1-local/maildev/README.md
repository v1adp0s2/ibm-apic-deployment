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
- `maildev-deployment.yaml` - Kubernetes Deployment and Services
- `contour-httpproxy-maildev.yaml` - HTTPProxy for web UI access

## Deployment

### 1. Load the image (if needed)

```bash
docker load -i maildev-2.2.1-amd64.tar.gz
```

### 2. Tag and push to Harbor registry (if using private registry)

```bash
docker tag maildev/maildev:2.2.1 harbor.talos.zebra-cloud.net/apic/maildev:2.2.1
docker push harbor.talos.zebra-cloud.net/apic/maildev:2.2.1
```

The deployment is already configured to use Harbor: `harbor.talos.zebra-cloud.net/apic/maildev:2.2.1`

### 3. Deploy to Kubernetes

```bash
kubectl apply -f maildev-deployment.yaml
kubectl apply -f contour-httpproxy-maildev.yaml
```

### 4. Verify deployment

```bash
kubectl get pods -n apic -l app=maildev
kubectl get svc -n apic -l app=maildev
```

## Access

- **Web UI**: http://maildev-apic.talos-pc.zebra-cloud.net
- **SMTP Server** (internal): maildev-smtp.apic.svc.cluster.local:25

## Configure API Connect

In Cloud Manager UI (Resources → Notifications):

```
Title: MailDev Test Server
Host: maildev-smtp.apic.svc.cluster.local
Port: 25
Secure Connection: No
Authentication: No
Email Address: noreply@apic.local
```

## Ports

- **Port 1025**: SMTP server (accepts all emails)
- **Port 1080**: Web UI to view captured emails

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
curl http://maildev-apic.talos-pc.zebra-cloud.net/email

# Get specific email
curl http://maildev-apic.talos-pc.zebra-cloud.net/email/{id}

# Delete all emails
curl -X DELETE http://maildev-apic.talos-pc.zebra-cloud.net/email/all
```

## Use Cases

Perfect for testing:
- Password reset emails
- User invitation emails
- API Connect notifications
- Developer Portal emails
- Catalog subscription confirmations

All emails are captured and displayed without actually sending to real addresses!
