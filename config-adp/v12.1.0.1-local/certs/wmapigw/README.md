# webMethods API Gateway Client Certificates

## Files
- `ca.crt` - webMethods CA certificate
- `client.crt` - Client certificate for authentication
- `client.key` - Client private key
- `wmapigw-client.p12` - PKCS12 bundle for browser import

## Import Certificate to Brave Browser

### Steps to Import:
1. Open Brave browser
2. Go to Settings → Privacy and security → Security → Manage certificates
   - Or navigate to: `brave://settings/certificates`
3. Click on "Your certificates" tab
4. Click "Import"
5. Select file: `wmapigw-client.p12`
6. Enter password: `changeit`
7. Click "OK"

### Access webMethods GUI:
Once the certificate is imported, you can access:
- **Management UI**: https://wmapigw-ui.apic.talos-pc.zebra-cloud.net
- **Login credentials**:
  - Username: `Administrator`
  - Password: `Admin123!`

### If prompted for certificate:
Brave will ask which certificate to use when accessing the site. Select the certificate with:
- Subject: `CN=wmapigw-client`

## Troubleshooting

If you still can't access the UI:
1. Restart Brave browser after importing the certificate
2. Make sure to select the correct certificate when prompted
3. Clear browser cache and cookies for the domain

## Alternative Access (curl)
```bash
curl -k --cert client.crt --key client.key \
  https://wmapigw-ui.apic.talos-pc.zebra-cloud.net
```