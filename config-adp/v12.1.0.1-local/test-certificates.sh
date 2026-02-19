#!/bin/bash

echo "========================================="
echo "API Connect v12.1.0.1 Certificate Verification"
echo "========================================="

# Set KUBECONFIG
export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml

echo ""
echo "1. Checking Certificate Authorities (CAs)"
echo "-----------------------------------------"
for ca in ingress-ca management-ca analytics-ca portal-ca wmapigw-ca nanogw-ca; do
    echo -n "  $ca: "
    if kubectl get secret $ca -n apic &>/dev/null; then
        subject=$(kubectl get secret $ca -n apic -o jsonpath='{.data.ca\.crt}' | base64 -d | openssl x509 -noout -subject 2>/dev/null | cut -d= -f2-)
        echo "✓ ($subject)"
    else
        echo "✗ MISSING"
    fi
done

echo ""
echo "2. Checking mTLS Client Certificates"
echo "------------------------------------"

echo "  Management -> webMethods:"
cert_subject=$(kubectl get secret wmapigateway-mgmt-client -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject 2>/dev/null | cut -d= -f2-)
expected="CN=management-client"
if [[ "$cert_subject" == *"$expected"* ]]; then
    echo "    ✓ wmapigateway-mgmt-client: $cert_subject (matches expected)"
else
    echo "    ✗ wmapigateway-mgmt-client: $cert_subject (expected: $expected)"
fi

echo "  Management -> DataPower:"
cert_subject=$(kubectl get secret gateway-client-client -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject 2>/dev/null | cut -d= -f2-)
echo "    ✓ gateway-client-client: $cert_subject"

echo "  Management -> Nano Gateway:"
cert_subject=$(kubectl get secret nano-gateway-mgmt-client -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject 2>/dev/null | cut -d= -f2-)
echo "    ✓ nano-gateway-mgmt-client: $cert_subject"

echo ""
echo "3. Checking HTTPProxy Backend Validation"
echo "----------------------------------------"

echo "  webMethods HTTPProxy:"
ca_secret=$(kubectl get httpproxy wmapigw-mgmt -n apic -o jsonpath='{.spec.routes[0].services[0].validation.caSecret}')
subject_name=$(kubectl get httpproxy wmapigw-mgmt -n apic -o jsonpath='{.spec.routes[0].services[0].validation.subjectName}')
if [[ "$ca_secret" == "wmapigw-ca" ]]; then
    echo "    ✓ CA: $ca_secret (correct)"
else
    echo "    ✗ CA: $ca_secret (should be wmapigw-ca)"
fi
echo "    Subject: $subject_name"

echo "  DataPower HTTPProxy:"
ca_secret=$(kubectl get httpproxy gwv6-gateway -n apic -o jsonpath='{.spec.routes[0].services[0].validation.caSecret}' 2>/dev/null || echo "N/A")
subject_name=$(kubectl get httpproxy gwv6-gateway -n apic -o jsonpath='{.spec.routes[0].services[0].validation.subjectName}' 2>/dev/null || echo "N/A")
echo "    CA: $ca_secret"
echo "    Subject: $subject_name"

echo ""
echo "4. Checking Certificate Expiry"
echo "------------------------------"
for cert in wmapigateway-mgmt-client management-client gateway-service analytics-client portal-client; do
    if kubectl get secret $cert -n apic &>/dev/null; then
        expiry=$(kubectl get secret $cert -n apic -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
        echo "  $cert: $expiry"
    fi
done

echo ""
echo "5. Checking Pod Status"
echo "----------------------"
echo "  Management:"
kubectl get pods -n apic -l app.kubernetes.io/name=apim --no-headers | awk '{printf "    %-50s %s\n", $1, $2}'

echo "  webMethods Gateway:"
kubectl get pods -n apic | grep wmapigw | awk '{printf "    %-50s %s\n", $1, $2}'

echo "  DataPower Gateway:"
kubectl get pods -n apic | grep gwv6 | awk '{printf "    %-50s %s\n", $1, $2}'

echo "  Nano Gateway:"
kubectl get pods -n apic | grep nanogw | awk '{printf "    %-50s %s\n", $1, $2}'

echo ""
echo "6. Testing Gateway Endpoints"
echo "----------------------------"
for endpoint in wmapigw-ui.apic.demo01.mea-presales.org gwv6-manager.apic.demo01.mea-presales.org nanogw.apic.demo01.mea-presales.org; do
    echo -n "  https://$endpoint: "
    if curl -k -s -o /dev/null -w "%{http_code}" https://$endpoint/health 2>/dev/null | grep -q "200\|404\|503"; then
        code=$(curl -k -s -o /dev/null -w "%{http_code}" https://$endpoint/health 2>/dev/null)
        echo "✓ (HTTP $code)"
    else
        echo "✗ (unreachable)"
    fi
done

echo ""
echo "========================================="
echo "Certificate Verification Complete"
echo "========================================="