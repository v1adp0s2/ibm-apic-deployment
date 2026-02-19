Test an APIC deployment package by executing its instructions step by step against the default Kubernetes cluster.

## Input
Package name or path: $ARGUMENTS

## Your Task

You are an automated deployment tester. Your job is to read the package index, follow the instructions it references, verify the cluster state, and produce a written report.

### Step 1 — Resolve the package path

The argument `$ARGUMENTS` can be:
- An absolute path to a package directory
- A package name resolved against the repo's `config-adp/` directory (e.g. `v12.1.0.1-v2`)

Resolve to an absolute path:
1. Run `.claude/scripts/get-repo-root.sh` — this script is located alongside this command file and uses `git rev-parse --show-toplevel` anchored to its own directory, so it works on any machine regardless of clone location
2. The config-adp base is: `<repo-root>/config-adp/`
3. If `$ARGUMENTS` is already an absolute path, use it as-is; otherwise prepend the config-adp base

Verify the resolved path exists and contains `INDEX.yaml`. If not found, abort and tell the user.

### Step 2 — Read the package index

Read `<package>/INDEX.yaml`. This file is the authoritative map of the package — it lists every phase, its human-readable label, the instruction file to read, and any dependencies between phases. It also declares the `namespace` and `busybox` utility path.

Do not assume any fixed set of phases, file paths, or namespace names. Everything is driven by what `INDEX.yaml` declares. The index also points to `start_here` and `configure` files — read both for context before proceeding.

### Step 3 — Prepare the report file

- Create directory `<package>/deployment/` if it does not exist
- Report file path: `<package>/deployment/report_<YYYY-MM-DD_HHMMSS>.txt`
- Write the header immediately:

```
================================================================================
APIC PACKAGE TEST REPORT
================================================================================
Package:    <resolved path>
Index:      <INDEX.yaml contents summary — package name, description, phase count>
Date/Time:  <current datetime>
Cluster:    <kubectl config current-context>
User:       <kubectl config view --minify -o jsonpath='{.users[0].name}'>
================================================================================
```

### Step 4 — Execute a Prerequisites check

Before iterating over index phases, verify the cluster baseline:
- `kubectl get pods -n cert-manager` — expect all Running
- `kubectl get svc envoy -n projectcontour` — expect EXTERNAL-IP present
- `kubectl get storageclass` — note available storage classes

Record as `[PASS]` / `[FAIL]` / `[WARN]`. Write to report.

### Step 5 — Iterate over phases from the index

For each phase declared in `INDEX.yaml` (in the order listed):

1. **Read the instruction file** at `<package>/<phase.instructions>`
   - If the file does not exist, record `[SKIP]` with a note and continue
2. **Locate the GET-DEPLOYMENT STATUS section** in that file
   - Run every `kubectl` command found in that section
   - Do NOT run DEPLOY, DESTROY, or any mutating commands
3. **Evaluate results** using these rules:
   - CR phase check: `.status.phase` must be `Running` → `[PASS]` or `[FAIL]`
   - HTTPProxy check: `.status.currentStatus` must be `valid` → `[PASS]` or `[FAIL]`
   - Pod check: all pods must be `Running` or `Completed` → `[PASS]` / `[WARN]` / `[FAIL]`
   - curl endpoint check: HTTP 200 or 302 → `[PASS]` or `[FAIL]`
   - If the CR is not found at all (not yet deployed): record `[SKIP]`
4. **Check dependencies**: if a phase has `depends_on` and the dependency phase was `[SKIP]` or `[FAIL]`, mark this phase `[SKIP]` with a note explaining why
5. **Append phase result to the report** before moving to the next phase

For the `registration` phase specifically:
- Obtain a bearer token using the credentials found in the instruction file
- If token acquisition fails, mark all registration checks `[FAIL]`
- For each service: look for `"status": "online"` in the API response

### Step 6 — Write the summary

After all phases, append to the report:

```
================================================================================
SUMMARY
================================================================================
[PASS/FAIL/WARN/SKIP]  <phase.id>  —  <phase.label>
... one line per phase from INDEX.yaml ...
--------------------------------------------------------------------------------
OVERALL:  PASS / FAIL
--------------------------------------------------------------------------------
<If FAIL: list each failed check with command and truncated output>
================================================================================
```

Overall is `PASS` only if every non-SKIP phase passed.

### Step 7 — Tell the user

Print to the user:
- Overall result (PASS or FAIL)
- Report file path
- One-line summary per failed check
- Any instructions observed to be incorrect, missing, or outdated

### Rules

- Use `kubectl` with the default cluster config
- Do NOT run DEPLOY, DESTROY, or any mutating commands
- Do NOT modify any package files
- Drive all navigation from `INDEX.yaml` — no hardcoded paths or phase names
- Write to the report incrementally after each phase, not only at the end
- Capture full command output for every `[FAIL]` entry in the report
