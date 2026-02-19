# API Connect v12.1.0.1 Certificate Architecture

## Certificate Authority Hierarchy

### 1. Root CAs (Self-Signed)
- **ingress-ca**: External-facing certificates for ingress endpoints
- **management-ca**: Internal management subsystem certificates
- **analytics-ca**: Analytics subsystem certificates
- **portal-ca**: Developer portal certificates
- **wmapigw-ca**: webMethods API Gateway internal certificates
- **nanogw-ca**: Nano Gateway certificates

### 2. Certificate Issuers
- **selfsigning-issuer**: Creates self-signed root CAs
- **ingress-issuer**: Issues certificates signed by ingress-ca

## Subsystem Certificate Configuration

### Management Subsystem
**CA**: management-ca
**Server Certificate**: management-server (CN=management-server)
**Client Certificate**: management-client (CN=management-client)
**Database Certificates**:
- management-db-client-apicuser (CN=apicuser)
- management-db-client-postgres (CN=postgres)

### Analytics Subsystem
**CA**: analytics-ca
**Server Certificate**: analytics-server (CN=analytics-server)
**Client Certificate**: analytics-client (CN=analytics-client)
**Admin Certificate**: analytics-admin (CN=analytics-admin)
**Ingestion Client**: analytics-ingestion-client (issued by ingress-ca)

### Portal Subsystem
**CA**: portal-ca
**Server Certificate**: portal-server (CN=portal-server)
**Client Certificate**: portal-client (CN=portal-client)
**Admin Client**: portal-admin-client (issued by ingress-ca)

### DataPower Gateway (AI Gateway - gwv6)
**CA**: Uses management-ca for management plane communication
**Endpoint Certificates**: Issued by ingress-issuer
**Important Configuration**:
```yaml
mgmtPlatformEndpointCASecret:
  secretName: management-ca  # NOT ingress-ca
```

### webMethods API Gateway (wmapigw)
**CA**: wmapigw-ca (self-signed)
**Server Certificate**: wmapigw-server (CN=wmapigw-server)
**Client Certificate**: wmapigw-client (CN=wmapigw-client)
**Management Client**: wmapigateway-mgmt-client (CN=management-client, issued by ingress-ca)
**Important Configuration**:
```yaml
mgmtClientSubjectDN: CN=management-client
```

### Nano Gateway (nanogw)
**CA**: nanogw-ca (issued by ingress-ca)
**Server Certificate**: nanogw-server (CN=nanogw-server)
**Client Certificate**: nanogw-client (CN=nanogw-client)
**Analytics Collector**:
- nanogw-nanogw-analytics-collector-server
- nanogw-nanogw-analytics-collector-client

### Valkey (Redis)
**TLS Certificate**: valkey-tls (includes CA, cert, and key)
**Password Secret**: valkey-secret

## HTTPProxy Configuration

### Correct Backend Validation
Each HTTPProxy must validate the backend using the correct CA:

**webMethods Gateway**:
```yaml
validation:
  caSecret: wmapigw-ca  # NOT ingress-ca
  subjectName: wmapigw-server
```

**DataPower Gateway**:
```yaml
validation:
  caSecret: management-ca
  subjectName: gwv6.apic.svc
```

**Nano Gateway**:
```yaml
validation:
  caSecret: ingress-ca
  subjectName: nanogw-mgmt.apic.svc
```

## Common Certificate Issues and Solutions

### Issue 1: Certificate Subject Mismatch
**Error**: "Certificate subject ineligible"
**Solution**: Ensure the client certificate CN matches what the server expects
**Example**: webMethods expects CN=management-client, not CN=wmapigw-client

### Issue 2: Wrong CA for Validation
**Error**: "CERTIFICATE_VERIFY_FAILED"
**Solution**: Use the correct CA secret in HTTPProxy validation
**Example**: webMethods uses wmapigw-ca, not ingress-ca

### Issue 3: CA Certificate Mismatch
**Error**: "unknown ca"
**Solution**: Ensure the certificate is signed by the expected CA
**Example**: Management client certificates should be signed by appropriate CA

## Certificate Renewal Commands

### Check Certificate Details
```bash
kubectl get secret <secret-name> -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject -issuer -dates
```

### Force Certificate Renewal
```bash
kubectl delete certificate <certificate-name> -n apic
kubectl delete secret <secret-name> -n apic
# cert-manager will recreate them
```

### Restart Pods After Certificate Update
```bash
kubectl rollout restart deployment/<deployment-name> -n apic
```

## Verification Checklist

- [ ] All CAs are properly created and valid
- [ ] Each subsystem has correct server and client certificates
- [ ] HTTPProxy resources use correct CA for backend validation
- [ ] Client certificate subjects match server expectations
- [ ] All certificates are signed by the correct CA
- [ ] Pods have been restarted after certificate updates
- [ ] No certificate expiry warnings in logs

## Test Registration Commands

### webMethods Gateway
```bash
curl -k https://wmapigw-ui.apic.talos-pc.zebra-cloud.net/health
```

### DataPower Gateway
```bash
curl -k https://gwv6-manager.apic.talos-pc.zebra-cloud.net/health
```

### Nano Gateway
```bash
curl -k https://nanogw.apic.talos-pc.zebra-cloud.net/health
```