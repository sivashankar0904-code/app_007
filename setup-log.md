# app_007 — Setup Log

## Local Kubernetes Setup

### Date: 2026-04-19

---

### Step 1 — Verify kubectl and Docker Desktop

**Check cluster connection:**
```bash
kubectl config current-context
# Expected output: docker-desktop
```

**Check nodes:**
```bash
kubectl get nodes
# Expected output:
# NAME                    STATUS   ROLES           AGE   VERSION
# desktop-control-plane   Ready    control-plane   32s   v1.35.1
```

---

### Step 2 — Create Kind Cluster via Docker Desktop

- Opened Docker Desktop → Kubernetes → Create cluster
- Cluster type: **kind**
- Nodes: **1** (single node — control-plane + worker)
- Version: v1.35.1

---

### Step 3 — Create App Namespace

```bash
kubectl create namespace app007
```

- Isolates all app resources from default K8s system pods
- Professional practice: never deploy to `default` namespace

---

## Key Concepts Covered

| Concept | Decision | Reason |
|---|---|---|
| Local K8s vs Docker Compose | K8s | Recruiter-facing, production parity |
| Postgres placement | K8s (not standalone Docker) | Networking — K8s internal DNS |
| Deployment vs StatefulSet | StatefulSet for Postgres/Redis | Stable identity + ordered restarts |
| kubeadm vs kind | kind | Lightweight local dev tool |
| Namespace | app007 | Isolate from system pods |

---

---

## K8s Manifest Files — Purpose Reference

### Dependency Order
```
secret.yaml → pvc.yaml → statefulset.yaml → service.yaml
```

### secret.yaml
- Stores sensitive values — DB password, username, DB name
- K8s encrypts these separately from other configs
- StatefulSet references this — credentials never hardcoded
- Production replacement: AWS Secrets Manager / HashiCorp Vault

### pvc.yaml (PersistentVolumeClaim)
- Requests a chunk of disk storage from K8s
- Postgres data lives here — survives pod restarts and crashes
- Without this, every pod restart wipes all data
- Think of it as: "reserve me X GB of disk"

### statefulset.yaml
- Tells K8s to run your Postgres container
- References PVC (storage) and Secret (credentials)
- Gives Postgres a stable, predictable pod name — e.g. `postgres-0`
- Manages startup/shutdown order — critical for databases

### service.yaml
- Creates an internal DNS entry inside the K8s cluster
- Other pods connect to Postgres by service name — e.g. `postgres-service.app007.svc.cluster.local`
- Without this, pods can't find each other (dynamic IPs)
- Think of it as: "give this pod a stable address"

---

## Project Folder Structure

```
infra/
  k8s/
    postgres/
    redis/
    core-api/
    ai-service/
    ingress/
  docker/
    postgres/
      Dockerfile
```

---

## Next Steps

- [ ] Write Dockerfile for Postgres + pgvector
- [ ] Write K8s manifests for Postgres (StatefulSet + PVC + Service + Secret)
- [ ] Apply manifests and verify DB connection
- [ ] Set up Redis in K8s
- [ ] Set up Django service
- [ ] Set up FastAPI service
