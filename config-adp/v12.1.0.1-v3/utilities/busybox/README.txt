================================================================================
UTILITY: PVC Cleanup (Busybox)
================================================================================
Use this to reset a subsystem by clearing its Persistent Volume Claims.
WARNING: This deletes all data in the PVC. Only use for full resets.

================================================================================
USAGE: RESET MANAGEMENT DATABASE
================================================================================

# Step 1: Find the Management PVC names
kubectl get pvc -n ${APIC_NAMESPACE} | grep management

# Example output:
# management-99543590-db-1      Bound  50Gi   nfs-ssd
# management-99543590-db-1-wal  Bound  2Gi    nfs-ssd

# Step 2: Scale down Management
kubectl scale deployment -n ${APIC_NAMESPACE} --replicas=0 \
  management-apim management-lur management-ui management-analytics-ui \
  management-analytics-proxy management-portal-proxy management-websocket-proxy \
  management-api-studio management-audit-logging management-client-downloads-server \
  management-consumer-catalog management-juhu management-ldap management-taskmanager

# Step 3: Delete the PostgreSQL cluster
kubectl delete cluster -n ${APIC_NAMESPACE} management-<CLUSTER-ID>-db

# Step 4: Edit clear-pvc-pod.yaml.template — set the PVC names:
#   claimName: management-<CLUSTER-ID>-db-1
#   claimName: management-<CLUSTER-ID>-db-1-wal

# Step 5: Apply busybox pod (using envsubst to replace variables)
envsubst < clear-pvc-pod.yaml.template | kubectl apply -f -

# Step 6: Watch until pod is Completed
kubectl get pod busybox-clear-pvc -n ${APIC_NAMESPACE} -w

# Step 7: Check logs to confirm cleared
kubectl logs -n ${APIC_NAMESPACE} busybox-clear-pvc

# Step 8: Delete busybox pod
kubectl delete pod busybox-clear-pvc -n ${APIC_NAMESPACE}

# Step 9: Delete the PVCs
kubectl delete pvc -n ${APIC_NAMESPACE} management-<CLUSTER-ID>-db-1
kubectl delete pvc -n ${APIC_NAMESPACE} management-<CLUSTER-ID>-db-1-wal

# Step 10: Re-apply Management CR (will recreate DB from scratch)
envsubst < ../../core/03-management/06-management-cr.yaml.template | kubectl apply -f -
kubectl get managementcluster -n ${APIC_NAMESPACE} -w

================================================================================
IMAGE REQUIRED
================================================================================

The busybox image must be available in your registry:
  ${APIC_IMAGE_REGISTRY}/busybox:1.37

See the v12.1.0.1-local/busybox/ directory for the image tar file.

================================================================================
