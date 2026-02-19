# APIC v12.1.0.1-v3 Package Fix Report
**Date:** 2026-02-19
**Purpose:** Analysis and fixes applied based on deployment log issues from deploy_2026-02-19_195012.txt

## Summary
Analyzed 8 issues from the deployment log. Found that 2 issues were already fixed, and applied fixes for the remaining 6 issues.

## Issue Analysis and Fixes

### 1. Missing consumer-endpoint Certificate
**Status:** ✅ ALREADY FIXED
**Location:** `/core/02-prerequisites/04-ingress-issuer.yaml`
**Finding:** The consumer-endpoint certificate is present (lines 412-443)
**Action Taken:** Updated documentation in DEPLOY-CORE.txt to reflect correct count (13 certificates, not 15)
**Files Modified:**
- `/core/DEPLOY-CORE.txt` (line 91)

### 2. Missing Hostnames in Management CR
**Status:** ✅ PARTIALLY FIXED → COMPLETED
**Location:** `/core/03-management/06-management-cr.yaml.template`
**Finding:** File was already a .yaml.template with proper variables, but deployment command was incorrect
**Action Taken:** Fixed deployment command to use envsubst
**Files Modified:**
- `/core/DEPLOY-CORE.txt` (line 104) - Changed from `kubectl apply -f` to `envsubst < ... | kubectl apply -f -`

### 3. wM Gateway Encryption Secret Key Mismatch
**Status:** ❌ NEEDED FIX → ✅ FIXED
**Location:** `/sub-components/03-wm-gateway/COMMANDS.txt`
**Problem:** Secret created with `--from-literal=encryptionKey=` but pod expects `--from-literal=password=`
**Action Taken:** Fixed secret creation command
**Files Modified:**
- `/sub-components/03-wm-gateway/COMMANDS.txt` (line 21)

### 4. AI Gateway Certificate Name Mismatch
**Status:** ✅ ALREADY FIXED (CR) / ❌ DOCS NEEDED FIX → ✅ FIXED
**Location:** `/sub-components/04-ai-gateway/`
**Finding:** The CR already uses correct certificate names (gateway-service, gateway-peering)
**Action Taken:** Fixed documentation that incorrectly referenced ai-gateway-service and ai-gateway-peering
**Files Modified:**
- `/sub-components/04-ai-gateway/COMMANDS.txt` (lines 23-25)

### 5. DevPortal Missing Encryption Secret
**Status:** ❌ NEEDED FIX → ✅ FIXED
**Location:** `/sub-components/02-wm-devportal/COMMANDS.txt`
**Problem:** Secret created with wrong key name `encryptionKey` instead of `encryption_secret`
**Action Taken:** Fixed secret creation commands to use correct key name
**Files Modified:**
- `/sub-components/02-wm-devportal/COMMANDS.txt` (lines 27, 46)

### 6. Analytics devPortalMode Not Enabled
**Status:** ❌ NEEDED FIX → ✅ FIXED
**Location:** `/sub-components/01-analytics/analytics-cr.yaml.template`
**Problem:** devPortalMode was set to false, preventing DevPortal deployment
**Action Taken:**
1. Changed devPortalMode from false to true in CR template
2. Updated deployment command to use envsubst
**Files Modified:**
- `/sub-components/01-analytics/analytics-cr.yaml.template` (line 31)
- `/sub-components/01-analytics/COMMANDS.txt` (line 27)

### 7. HTTPProxy Backend TLS Validation Namespace Mismatch (Management/Analytics)
**Status:** ❌ NEEDED FIX → ✅ FIXED
**Location:** `/ingress/*.yaml.template` files
**Problem:** Backend validation subjectName used hardcoded "apic" namespace instead of ${APIC_NAMESPACE}
**Action Taken:** Replaced all occurrences of `.apic.svc.cluster.local` with `.${APIC_NAMESPACE}.svc.cluster.local`
**Files Modified:**
- `/ingress/contour-httpproxy-management.yaml.template` (5 occurrences)
- `/ingress/contour-httpproxy-analytics.yaml.template` (1 occurrence)
- `/ingress/contour-httpproxy-gateway.yaml.template` (2 occurrences)
- `/ingress/contour-httpproxy-devportal.yaml.template` (1 occurrence)

### 8. DevPortal HTTPProxy Backend Validation
**Status:** ✅ FIXED (same as Issue #7)
**Location:** `/ingress/contour-httpproxy-devportal.yaml.template`
**Problem:** Same namespace mismatch as Issue #7
**Action Taken:** Fixed as part of Issue #7 resolution

## Verification Steps

After applying these fixes, future deployments should:

1. **Use envsubst properly:** All .yaml.template files must be processed with envsubst before applying
2. **Create secrets with correct keys:**
   - wmapigateway-enc-key: `password` key
   - devportal-enc-key: `encryption_secret` key
3. **Have Analytics configured correctly:** devPortalMode enabled by default
4. **Use dynamic namespace references:** All HTTPProxy backend validation uses ${APIC_NAMESPACE}

## Files Modified Summary

### Core Components
- `/core/DEPLOY-CORE.txt` - Fixed certificate count and Management CR deployment command

### Sub-components
- `/sub-components/01-analytics/analytics-cr.yaml.template` - Enabled devPortalMode
- `/sub-components/01-analytics/COMMANDS.txt` - Added envsubst to deployment
- `/sub-components/02-wm-devportal/COMMANDS.txt` - Fixed encryption secret key name
- `/sub-components/03-wm-gateway/COMMANDS.txt` - Fixed encryption secret key name
- `/sub-components/04-ai-gateway/COMMANDS.txt` - Fixed certificate documentation

### Ingress
- `/ingress/contour-httpproxy-management.yaml.template` - Fixed namespace references
- `/ingress/contour-httpproxy-analytics.yaml.template` - Fixed namespace reference
- `/ingress/contour-httpproxy-gateway.yaml.template` - Fixed namespace references
- `/ingress/contour-httpproxy-devportal.yaml.template` - Fixed namespace reference

## Recommendations

1. **Test deployment:** Run a fresh deployment with these fixes to verify all issues are resolved
2. **Update deployment automation:** Ensure any deployment scripts use envsubst for all .yaml.template files
3. **Document secret requirements:** Consider adding a central SECRET-REQUIREMENTS.md file listing all required secrets with their exact key names
4. **Validate templates:** Add a validation script to check all .yaml.template files use ${APIC_NAMESPACE} instead of hardcoded namespaces

## Notes

- The AI Gateway HTTPProxy files don't use backend TLS validation, so they were unaffected by the namespace issue
- All fixes maintain backward compatibility with the variable names defined in config.env
- The deployment pattern of using envsubst piped to kubectl is consistent with the MailDev utility pattern