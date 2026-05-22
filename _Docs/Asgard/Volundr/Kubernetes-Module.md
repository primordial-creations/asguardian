# Volundr - Kubernetes Module

## Overview

The Kubernetes module generates production-ready Kubernetes manifests with security best practices, resource management, and high-availability configurations.

## Models

### WorkloadType

Supported workload types:
- `DEPLOYMENT` - Standard deployments with rolling updates
- `STATEFULSET` - Stateful applications with persistent identity
- `DAEMONSET` - Node-level services
- `JOB` - One-time batch jobs
- `CRONJOB` - Scheduled recurring jobs

### SecurityProfile

Security configuration levels:
- `RESTRICTED` - Most secure (non-root, read-only, no privileges)
- `BASELINE` - Standard security (non-root, controlled capabilities)
- `PRIVILEGED` - Minimal restrictions (for system-level workloads)

### EnvironmentType

Target environment:
- `DEVELOPMENT` - Relaxed limits, single replica
- `STAGING` - Production-like, moderate resources
- `PRODUCTION` - Full HA, strict limits, complete security

### ManifestConfig

Main configuration model:

```python
from Volundr.Kubernetes import ManifestConfig, WorkloadType, SecurityProfile

config = ManifestConfig(
    name="myapp",                              # Required
    image="nginx:latest",                      # Required
    workload_type=WorkloadType.DEPLOYMENT,     # Default
    replicas=3,
    namespace="default",
    labels={"app": "myapp", "tier": "frontend"},
    annotations={},

    # Resources
    resources=ResourceRequirements(
        requests={"cpu": "100m", "memory": "128Mi"},
        limits={"cpu": "500m", "memory": "512Mi"}
    ),

    # Probes
    liveness_probe=ProbeConfig(
        http_path="/health",
        port=8080,
        initial_delay_seconds=10,
        period_seconds=30
    ),
    readiness_probe=ProbeConfig(
        http_path="/ready",
        port=8080,
        initial_delay_seconds=5,
        period_seconds=10
    ),

    # Ports
    ports=[PortConfig(container_port=8080, service_port=80, protocol="TCP")],

    # Security
    security_profile=SecurityProfile.BASELINE,
    security_context=SecurityContext(
        run_as_non_root=True,
        run_as_user=1000,
        read_only_root_filesystem=True
    ),

    # Features
    create_service=True,
    create_configmap=True,
    create_secret=False,
    create_network_policy=True,
    create_pdb=True,

    # Environment
    env={"LOG_LEVEL": "info"},
    env_from_secrets=["myapp-secrets"],
    env_from_configmaps=["myapp-config"],

    # Service Account
    service_account="myapp-sa",

    # Scheduling
    node_selector={"kubernetes.io/os": "linux"},
    tolerations=[],
    affinity={}
)
```

## Service: ManifestGenerator

### Basic Usage

```python
from Volundr.Kubernetes import ManifestConfig, ManifestGenerator

# Create configuration
config = ManifestConfig(
    name="myapp",
    image="nginx:latest",
    replicas=3
)

# Generate manifest
generator = ManifestGenerator()
manifest = generator.generate(config)

# Access generated content
print(manifest.yaml_content)           # Full YAML
print(manifest.workload_manifest)      # Deployment/StatefulSet
print(manifest.service_manifest)       # Service
print(manifest.configmap_manifest)     # ConfigMap
print(manifest.secret_manifest)        # Secret
print(manifest.network_policy_manifest)# NetworkPolicy
print(manifest.pdb_manifest)           # PodDisruptionBudget

# Check quality
print(f"Best Practice Score: {manifest.best_practice_score}/100")
print(f"Issues: {manifest.validation_results}")

# Save to file
generator.save_to_file(manifest, output_dir="./k8s")
```

### Generated Resources

For a typical deployment, the generator produces:

1. **Deployment/StatefulSet/DaemonSet/Job**
   - Container specification with image and resources
   - Liveness and readiness probes
   - Security context
   - Environment variables

2. **Service** (if `create_service=True`)
   - ClusterIP by default
   - Port mappings
   - Label selectors

3. **ConfigMap** (if `create_configmap=True`)
   - Environment variable data
   - Configuration files

4. **Secret** (if `create_secret=True`)
   - Sensitive data (base64 encoded)

5. **NetworkPolicy** (if `create_network_policy=True`)
   - Ingress rules
   - Egress restrictions

6. **PodDisruptionBudget** (if `create_pdb=True`)
   - Minimum availability during disruptions

### Example Output

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: default
  labels:
    app: myapp
    managed-by: volundr
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: myapp
          image: nginx:latest
          ports:
            - containerPort: 8080
              protocol: TCP
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: myapp
  namespace: default
spec:
  selector:
    app: myapp
  ports:
    - port: 80
      targetPort: 8080
      protocol: TCP
  type: ClusterIP
```

## Best Practice Score

The generator calculates a score (0-100) based on:

| Criteria | Weight | Description |
|----------|--------|-------------|
| Resource Limits | 20 | CPU and memory limits defined |
| Liveness Probe | 15 | Health check configured |
| Readiness Probe | 15 | Ready check configured |
| Security Context | 20 | Non-root, read-only filesystem |
| Network Policy | 15 | Network segmentation |
| PDB | 15 | High availability |

## CLI Usage

```bash
# Basic deployment
python -m Volundr k8s generate --name myapp --image nginx:latest

# With options
python -m Volundr kubernetes generate \
  --name myapp \
  --image nginx:latest \
  --replicas 3 \
  --namespace production \
  --type deployment \
  --output ./k8s
```

## Related

- [01-Overview.md](01-Overview.md) - Package overview
- [06-CLI-Reference.md](06-CLI-Reference.md) - CLI commands
