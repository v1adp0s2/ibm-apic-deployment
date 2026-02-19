#!/bin/bash

echo "========================================="
echo "webMethods API Gateway Access Options"
echo "========================================="

export KUBECONFIG=/Volumes/Data/Users/vladimir/git/ibm/demos/ibm-apic-deployment/talos/talos02-kubeconfig.yaml

echo ""
echo "Option 1: Direct pod access (bypass all proxies)"
echo "-------------------------------------------------"
echo "Starting port-forward to webMethods Integration Server..."
kubectl port-forward pod/wmapigw-apigateway-0 -n apic 5555:5555 &
PF1=$!
sleep 2

echo "Starting port-forward to webMethods API Gateway..."
kubectl port-forward pod/wmapigw-apigateway-0 -n apic 9072:9072 &
PF2=$!
sleep 2

echo ""
echo "✅ Access URLs:"
echo "   Integration Server: http://localhost:5555"
echo "   API Gateway UI: http://localhost:9072/apigatewayui"
echo ""
echo "📝 Login credentials:"
echo "   Username: Administrator"
echo "   Password: Admin123!"
echo "   Mode: System"
echo ""
echo "Press Ctrl+C to stop port forwarding..."
wait $PF1 $PF2