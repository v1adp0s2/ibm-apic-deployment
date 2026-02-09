k create ns apic

# Download cert-manager

From `https://github.com/cert-manager/cert-manager/releases/download/v1.19.2/cert-manager.yaml`


    scp '/Users/vladimir/Downloads/cert-manager (1).yaml' demo01:/home/administrator/git/demos/apic-deployment/cert-manager/cert-manager-1.19.2.yaml


# create secret

    source .env

    k create secret docker-registry apic-registry-secret \
    --docker-server=$IBM_IMAGE_SERVER \
    --docker-username=cp \
    --docker-password=$IBM_ENTITLEMENT_KEY \
    --docker-email=$IBM_USER \
    --namespace $APIC_NAMESPACE \
    --dry-run=client -o yaml | k apply -f -

    k create secret docker-registry datapower-docker-local-cred \
    --docker-server=$IBM_IMAGE_SERVER \
    --docker-username=cp \
    --docker-password=$IBM_ENTITLEMENT_KEY \
    --docker-email=$IBM_USER \
    --namespace $APIC_NAMESPACE \
    --dry-run=client -o yaml | k apply -f -

    k create secret generic datapower-admin-credentials \
    --from-literal=password=$APIC_ADMIN_PWD \
    --namespace $APIC_NAMESPACE \
    --dry-run=client -o yaml | k apply -f -

# Install the ibm-apiconnect CRDs

    k apply --server-side --force-conflicts -f apiconnect-operator/ibm-apiconnect-crds.yaml

    kubectl apply -f apiconnect-operator/ibm-apiconnect.yaml --namespace $APIC_NAMESPACE

    kubectl apply -f apiconnect-operator/ibm-datapower.yaml --namespace $APIC_NAMESPACE


# Install the ingress-ca Issuer to be used by cert-manager

    kubectl apply -f apiconnect-operator/helper_files/ingress-issuer-v1.yaml -n $APIC_NAMESPACE