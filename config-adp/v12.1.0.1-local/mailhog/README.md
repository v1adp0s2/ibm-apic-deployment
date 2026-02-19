# MailHog Test Mail Server

MailHog is an email testing tool for developers. It catches all outgoing emails and provides a web interface to view them without actually sending emails to real addresses.

## Files in this directory

- `mailhog-v1.0.1.tar.gz` - Docker image archive (138 MB compressed)
- `mailhog-deployment.yaml` - Kubernetes Deployment and Services
- `contour-httpproxy-mailhog.yaml` - HTTPProxy for web UI access

## Deployment

### 1. Load the image (if needed)

```bash
docker load -i mailhog-v1.0.1.tar.gz
```

### 2. Tag and push to Harbor registry (if using private registry)

```bash
docker tag mailhog/mailhog:v1.0.1 harbor.talos.zebra-cloud.net/apic/mailhog:v1.0.1
docker push harbor.talos.zebra-cloud.net/apic/mailhog:v1.0.1
```

Then update `mailhog-deployment.yaml` to use the Harbor image.

### 3. Deploy to Kubernetes

```bash
kubectl apply -f mailhog-deployment.yaml
kubectl apply -f contour-httpproxy-mailhog.yaml
```

### 4. Verify deployment

```bash
kubectl get pods -n apic -l app=mailhog
kubectl get svc -n apic -l app=mailhog
```

## Access

- **Web UI**: http://mailhog-apic.talos-pc.zebra-cloud.net
- **SMTP Server** (internal): mailhog-smtp.apic.svc.cluster.local:25

## Configure API Connect

In Cloud Manager UI (Resources → Notifications):

```
Title: MailHog Test Server
Host: mailhog-smtp.apic.svc.cluster.local
Port: 25
Secure Connection: No
Authentication: No
Email Address: noreply@apic.local
```

## Features

- **Port 1025/25**: SMTP server (accepts all emails)
- **Port 8025**: Web UI to view captured emails
- **In-memory storage**: Emails are stored in memory (lost on pod restart)
- **No authentication**: Perfect for testing environments

## View Emails

Access the web UI to see all emails sent by API Connect:
- Password reset emails
- User invitations
- Notifications
- Developer Portal emails

All emails are captured and displayed with full content, headers, and attachments.
