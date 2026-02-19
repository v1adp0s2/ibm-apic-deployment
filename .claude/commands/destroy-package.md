Completely remove an APIC deployment from the Kubernetes cluster — all CRs, operators, CRDs, PVCs (data wiped via busybox), secrets, and the namespace itself. No trace left behind.

## Input
Package name or path: $ARGUMENTS

## Your Task

You are an automated deployment destroyer. This is **irreversible**. Your job is to tear down every resource created by the package in the correct reverse order, wipe all PVC data using busybox, and confirm the cluster is clean.

### Step 1 — Resolve the package path

Same logic as test-package:
1. Run `.claude/scripts/get-repo-root.sh` to get the repo root
2. config-adp base: `<repo-root>/config-adp/`
3. Absolute path → use as-is; package name → prepend config-adp base

Verify the resolved path exists and contains `INDEX.yaml`. If not found, abort.

### Step 2 — Read the package index

Read `<package>/INDEX.yaml`. Extract:
- All phases (id, label, instructions path) — you will process them in **reverse order**
- The `start_here` file — read it to confirm the namespace (look for `Namespace:` field)
- The busybox template: `<package>/utilities/busybox/clear-pvc-pod.yaml` — read it to get the busybox image name and imagePullSecrets

### Step 3 — Confirm with the user

**STOP. Before executing anything destructive, ask the user to confirm.**

Print clearly:
```
WARNING: This will permanently destroy the following deployment:
  Package:    <package path>
  Namespace:  <namespace from index/start_here>
  Cluster:    <kubectl config current-context>

This will:
  ✗ Delete all sub-component CRs (<list from index phases in reverse>)
  ✗ Wipe and delete ALL PVCs (all data permanently lost)
  ✗ Delete all HTTPProxy ingress resources
  ✗ Delete Management cluster and PostgreSQL database
  ✗ Delete APIC operators and all CRDs
  ✗ Delete all secrets created by the deployment
  ✗ Delete the namespace entirely

Type the package name to confirm:
```

Wait for the user to type the package name (e.g. `v12.1.0.1-v2`). If it does not match, abort. Do not proceed without a match.

### Step 4 — Prepare the destroy log

- Create `<package>/deployment/` if it does not exist
- Log file: `<package>/deployment/destroy_<YYYY-MM-DD_HHMMSS>.txt`
- Write header with package, datetime, cluster context
- Write every command and its output to the log as you execute

### Step 5 — Delete sub-components in reverse phase order

Read the phases from `INDEX.yaml`. Exclude `core` and `ingress` and `registration` phases — handle those separately below. Process the remaining sub-component phases in **reverse order** (last phase first).

For each sub-component phase:
1. Read its `<phase.instructions>` file
2. Find the **DESTROY** section
3. Execute every command in that section, in order
   - Skip `kubectl wait --for=delete` if the CR was already absent
   - Use `--ignore-not-found` where applicable to avoid errors on already-missing resources
4. Log each command and output with `[OK]` or `[WARN]` (warn if resource was not found, that is acceptable)

### Step 6 — Delete all ingress resources

```
kubectl delete httpproxy --all -n <namespace> --ignore-not-found
```

Log result.

### Step 7 — Wipe PVC data with busybox

Before deleting PVCs, mount and wipe each one using busybox to ensure the underlying NFS/storage volume is cleared and reusable.

1. Get the list of all remaining PVCs:
   ```
   kubectl get pvc -n <namespace> -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
   ```

2. Read the busybox image name and imagePullSecrets from `utilities/busybox/clear-pvc-pod.yaml`

3. For each PVC, generate and apply a busybox pod spec on the fly:
   ```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: busybox-wipe-<pvc-name>
     namespace: <namespace>
   spec:
     restartPolicy: Never
     imagePullSecrets:
       - name: <imagePullSecrets from template>
     containers:
       - name: wipe
         image: <busybox image from template>
         command: ["sh", "-c", "rm -rf /pvc/* /pvc/.* 2>/dev/null; echo done"]
         volumeMounts:
           - name: vol
             mountPath: /pvc
         securityContext:
           runAsUser: 0
           runAsGroup: 0
     volumes:
       - name: vol
         persistentVolumeClaim:
           claimName: <pvc-name>
   ```

4. Wait for each pod to complete (`kubectl wait pod/busybox-wipe-<pvc-name> --for=condition=Succeeded -n <namespace> --timeout=120s`)
5. Log the pod output (`kubectl logs busybox-wipe-<pvc-name> -n <namespace>`)
6. Delete the pod (`kubectl delete pod busybox-wipe-<pvc-name> -n <namespace>`)

If a PVC fails to mount (pod stays Pending), log `[WARN]`, skip that PVC, and continue — it will still be deleted in the next step.

### Step 8 — Delete all PVCs

```
kubectl delete pvc --all -n <namespace> --ignore-not-found
```

Wait for all PVCs to be gone:
```
kubectl wait pvc --all -n <namespace> --for=delete --timeout=120s
```

### Step 9 — Delete core (Management CR and PostgreSQL)

From `core/DEPLOY-CORE.txt`, find the **DESTROY** section and execute its commands:
- Delete ManagementCluster and wait for deletion
- Delete PostgreSQL cluster (`kubectl delete cluster -n <namespace> --all`)

Use `--ignore-not-found` on all delete commands.

### Step 10 — Delete operators and CRDs

From `core/DEPLOY-CORE.txt` DESTROY section, execute:
- Delete API Connect operator
- Delete DataPower operator
- Delete all APIC CRDs

**Important:** Run CRD deletion last — it cascades and removes any remaining CR instances cluster-wide.

### Step 11 — Delete prerequisites

From `core/DEPLOY-CORE.txt` DESTROY section:
- Delete cert-manager issuers and certificates (`02-prerequisites/04-ingress-issuer.yaml`)

### Step 12 — Delete the namespace

```
kubectl delete namespace <namespace> --ignore-not-found
kubectl wait namespace/<namespace> --for=delete --timeout=120s
```

### Step 13 — Final verification

Confirm nothing remains:

```
kubectl get all -n <namespace> 2>&1
kubectl get pvc -n <namespace> 2>&1
kubectl get crd | grep apiconnect
kubectl get crd | grep datapower
kubectl get crd | grep webmethods
```

All commands should return "not found" or empty. Log each result as `[CLEAN]` or `[LEFTOVER]`.

### Step 14 — Write summary and tell the user

Append to the log:
```
================================================================================
DESTROY SUMMARY
================================================================================
[OK/WARN]  <phase.id>  —  <phase.label>
... one line per phase processed ...
[CLEAN/LEFTOVER]  Namespace
[CLEAN/LEFTOVER]  PVCs
[CLEAN/LEFTOVER]  CRDs
--------------------------------------------------------------------------------
RESULT:  CLEAN / LEFTOVERS DETECTED
--------------------------------------------------------------------------------
<If LEFTOVERS: list each with the kubectl output>
================================================================================
```

Print to the user:
- Overall result (CLEAN or LEFTOVERS DETECTED)
- Log file path
- List any resources that could not be removed with instructions to clean them manually

### Rules

- Do NOT proceed past Step 3 without explicit user confirmation matching the package name
- Use `--ignore-not-found` on all delete commands — missing resources are acceptable during destroy
- Write every command and output to the log file as you go
- Do not modify any package files
- Namespace is always read from the package — never hardcoded in this command
