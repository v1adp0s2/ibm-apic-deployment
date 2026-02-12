# IBM API Connect 12.1.0.1 - Image Mirroring Guide

This guide covers downloading the API Connect image tool and mirroring all images to your private Harbor registry.

## Prerequisites

- Docker installed on your workstation
- Access to IBM Fix Central for downloading the image tool
- Harbor registry running and accessible
- Harbor project `apic` created

## Step 1: Download apiconnect-image-tool

Download from [IBM Fix Central](https://www.ibm.com/support/fixcentral/):
- Product: IBM API Connect → 12.1.0.1
- Platform: All supported platforms
- File: `apiconnect-image-tool-12.1.0.1.tar.gz`

### Option A: Download on Windows

Using PowerShell or Command Prompt:

    curl.exe -L -C - -o E:\apic\apiconnect-image-tool-12.1.0.1.tar.gz --retry 999 --retry-delay 5 --retry-all-errors --create-dirs <DOWNLOAD_URL>

Then transfer to your deployment server:

    scp E:\apic\apiconnect-image-tool-12.1.0.1.tar.gz user@server:/path/to/deployment/

### Option B: Download on Linux

    curl -L -C - -o apiconnect-image-tool-12.1.0.1.tar.gz --retry 999 --retry-delay 5 --retry-all-errors <DOWNLOAD_URL>

### Using s3cmd for Large File Transfers (Optional)

For large file transfers, `s3cmd` can be used with S3-compatible storage (DigitalOcean Spaces, AWS S3, MinIO, etc.) as an alternative to `scp`.

**Install s3cmd:**

    sudo apt install s3cmd

**Configure (DigitalOcean Spaces example):**

    s3cmd --configure \
      --host=ams3.digitaloceanspaces.com \
      --host-bucket="%(bucket)s.ams3.digitaloceanspaces.com" \
      --access_key=YOUR_ACCESS_KEY \
      --secret_key=YOUR_SECRET_KEY

This saves a config file at `~/.s3cfg`. To use a named config (e.g., for multiple providers):

    s3cmd --configure -c ~/do-tor1.s3cfg

**Upload to S3:**

    s3cmd -c ~/do-tor1.s3cfg put --progress \
      apiconnect-image-tool-12.1.0.1.tar.gz \
      s3://bucket-name/apic/apiconnect-image-tool-12.1.0.1.tar.gz

**Download from S3:**

    s3cmd -c ~/do-tor1.s3cfg get --progress \
      s3://bucket-name/apic/apiconnect-image-tool-12.1.0.1.tar.gz \
      ./apiconnect-image-tool-12.1.0.1.tar.gz

**Other useful s3cmd commands:**

    # List buckets
    s3cmd -c ~/do-tor1.s3cfg ls

    # List files in bucket
    s3cmd -c ~/do-tor1.s3cfg ls s3://bucket-name/apic/

    # Upload a directory recursively
    s3cmd -c ~/do-tor1.s3cfg put -r --progress ./artifacts/ s3://bucket-name/apic/

    # For large files, use multipart upload with larger chunks
    s3cmd -c ~/do-tor1.s3cfg put --progress --multipart-chunk-size-mb=50 \
      largefile.tar.gz s3://bucket-name/apic/

## Step 2: Load Image Tool into Docker

On your deployment server with Docker:

    cd /path/to/deployment
    docker load < apiconnect-image-tool-12.1.0.1.tar.gz

Expected output:

    Loaded image: apiconnect-image-tool:12.1.0.1

## Step 3: List All Images (Optional)

To see all images that will be mirrored:

    docker run --rm apiconnect-image-tool:12.1.0.1 version --images

This will display approximately 60-70 images including:
- Operator images
- Management subsystem images
- Gateway subsystem images
- Portal subsystem images
- Analytics subsystem images
- Supporting service images (PostgreSQL, Redis, NATS, etc.)

## Step 4: Create Harbor Project

Before uploading images, create a project in Harbor:

1. Open Harbor UI: https://harbor.adp.example.com
2. Log in with admin credentials
3. Click "Projects" → "New Project"
4. Project Name: `apic`
5. Access Level: Private (recommended)
6. Click "OK"

## Step 5: Upload Images to Harbor

**Important Notes:**
- This process takes 1-3 hours depending on network speed
- Approximately 25-35 GB of images will be uploaded
- Ensure sufficient disk space in Harbor storage

### Upload Command

    docker run --rm apiconnect-image-tool:12.1.0.1 upload \
      harbor.adp.example.com/apic \
      --username <HARBOR_USER> \
      --password <HARBOR_PASSWORD> \
      --tls-verify=false

**Parameters:**
- `harbor.adp.example.com/apic`: Target registry and project
- `--username`: Harbor username (or robot account)
- `--password`: Harbor password (or robot account token)
- `--tls-verify=false`: Required for self-signed certificates

### Using Harbor Robot Accounts (Recommended)

For better security, create a robot account in Harbor:

1. Harbor UI → Projects → `apic` → Robot Accounts
2. Click "New Robot Account"
3. Name: `apic-upload`
4. Permissions: Push Repository, Pull Repository
5. Click "Add"
6. Copy the token (shown once)

Use the robot account credentials:

    docker run --rm apiconnect-image-tool:12.1.0.1 upload \
      harbor.adp.example.com/apic \
      --username 'robot$apic-upload' \
      --password <ROBOT_TOKEN> \
      --tls-verify=false

**Note:** The username format is `robot$<account-name>` with the dollar sign.

## Step 6: Verify Upload

After upload completes, verify in Harbor UI:

1. Navigate to Projects → `apic` → Repositories
2. You should see approximately 60-70 repositories
3. Check key images:
   - `ibm-apiconnect-operator`
   - `datapower-operator`
   - `ibm-apiconnect-management-*`
   - `ibm-apiconnect-gateway-*`
   - `ibm-apiconnect-portal-*`
   - `ibm-apiconnect-analytics-*`

### Verify from Command Line

    # Count repositories
    curl -u admin:password https://harbor.adp.example.com/api/v2.0/projects/apic/repositories | jq '. | length'

    # List all repositories
    curl -u admin:password https://harbor.adp.example.com/api/v2.0/projects/apic/repositories | jq '.[].name'

## Troubleshooting

### Upload Fails: "unauthorized"

**Cause:** Invalid credentials or insufficient permissions

**Solution:**
- Verify Harbor credentials are correct
- Ensure the user/robot account has push permissions to `apic` project
- Check project exists and name matches exactly

### Upload Fails: "x509: certificate signed by unknown authority"

**Cause:** Harbor uses self-signed certificate and TLS verification is enabled

**Solution:** Add `--tls-verify=false` flag to the upload command

### Upload Hangs or Times Out

**Cause:** Network issues or firewall blocking Docker registry protocol

**Solution:**
- Check firewall allows HTTPS (443) to Harbor
- Verify Harbor is accessible: `curl -k https://harbor.adp.example.com/api/v2.0/systeminfo`
- Try uploading from a different network location

### Upload Succeeds but Images Missing

**Cause:** Upload completed with errors that were not displayed

**Solution:**
- Re-run the upload command (it will skip existing images)
- Check Harbor logs: `docker logs <harbor-registry-container>`
- Verify Harbor has sufficient disk space

### "no space left on device"

**Cause:** Harbor storage backend is full

**Solution:**
- Check Harbor storage: `df -h`
- Clean up old/unused images in Harbor UI
- Expand Harbor storage volume
- For NFS: verify NFS server has sufficient space

## Next Steps

After images are successfully mirrored to Harbor:

1. Return to DEPLOYMENT-GUIDE.md
2. Continue with Step 8: Deploy Management Subsystem
3. All subsequent deployments will pull images from Harbor

## Storage Requirements

| Component | Approximate Size |
|-----------|-----------------|
| Operator images | ~2 GB |
| Management images | ~15 GB |
| Gateway images | ~5 GB |
| Portal images | ~5 GB |
| Analytics images | ~5 GB |
| Supporting images | ~3 GB |
| **Total** | **~35 GB** |

**Note:** Actual sizes may vary by version. Ensure Harbor has at least 50 GB free space for API Connect images.
