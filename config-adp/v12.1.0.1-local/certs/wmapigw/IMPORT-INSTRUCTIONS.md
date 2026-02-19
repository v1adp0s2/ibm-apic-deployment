# Import Certificate to Brave on macOS

## Option 1: Using Keychain Access (GUI)

1. **Open Keychain Access**:
   - Press `Cmd + Space` and search for "Keychain Access"
   - Or go to Applications → Utilities → Keychain Access

2. **Import the certificate**:
   - In Keychain Access, go to File → Import Items...
   - Navigate to: `/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/config-adp/v12.1.0.1-local/certs/wmapigw/`
   - Select `wmapigw-client.p12`
   - Password: `changeit`
   - Click "Add"

3. **Trust the certificate** (if needed):
   - Find the certificate in Keychain (search for "wmapigw")
   - Double-click it
   - Expand "Trust" section
   - Set "When using this certificate" to "Always Trust"
   - Close and enter your password to save

4. **Restart Brave** and access:
   - https://wmapigw-ui.apic.demo01.mea-presales.org
   - Brave should automatically use the certificate

## Option 2: Direct Access via Port Forward

Since you already have port-forward running on localhost:5543, you can try:

1. Access: http://localhost:5543
2. This bypasses the HTTPProxy certificate requirement

## Option 3: Use Firefox Instead

Firefox has its own certificate store:
1. Open Firefox
2. Go to Settings → Privacy & Security → Certificates → View Certificates
3. Click "Your Certificates" tab → Import
4. Select `wmapigw-client.p12`
5. Password: `changeit`

## Login Credentials

Once you can access the UI:
- **Username**: Administrator
- **Password**: Admin123!

## Troubleshooting

If certificate doesn't work:
1. Clear Brave's cache and cookies
2. Check if certificate appears in: brave://settings/certificates
3. Try incognito mode
4. Check Keychain Access to see if certificate was imported