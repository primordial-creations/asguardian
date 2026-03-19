"""
Kustomize Base Generator Service

Generates Kustomize base configurations with resources,
transformers, and generators.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    KustomizeConfig,
    KustomizeBase,
)


class BaseGenerator:
    """Generates Kustomize base configurations."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the base generator.

        Args:
            output_dir: Directory for saving generated configurations
        """
        self.output_dir = output_dir or "kustomize"

    def generate(self, config: KustomizeConfig) -> GeneratedKustomization:
        """
        Generate Kustomize base configuration.

        Args:
            config: Kustomize configuration

        Returns:
            GeneratedKustomization with all generated files
        """
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        kustomization_id = f"{config.base.name}-{config_hash}"

        files: Dict[str, str] = {}

        # Generate base resources
        if config.generate_deployment:
            files["base/deployment.yaml"] = self._generate_deployment(config)

        if config.generate_service:
            files["base/service.yaml"] = self._generate_service(config)

        if config.generate_hpa:
            files["base/hpa.yaml"] = self._generate_hpa(config)

        if config.generate_networkpolicy:
            files["base/networkpolicy.yaml"] = self._generate_networkpolicy(config)

        # Generate base kustomization.yaml
        files["base/kustomization.yaml"] = self._generate_base_kustomization(config, files)

        validation_results = self._validate_base(files, config)
        best_practice_score = self._calculate_best_practice_score(files, config)

        return GeneratedKustomization(
            id=kustomization_id,
            config_hash=config_hash,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def _generate_deployment(self, config: KustomizeConfig) -> str:
        """Generate deployment.yaml for base."""
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": config.base.name,
                "labels": {"app": config.base.name},
            },
            "spec": {
                "replicas": config.replicas,
                "selector": {
                    "matchLabels": {"app": config.base.name},
                },
                "template": {
                    "metadata": {
                        "labels": {"app": config.base.name},
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": config.base.name,
                                "image": config.image,
                                "ports": [
                                    {
                                        "containerPort": config.container_port,
                                        "name": "http",
                                        "protocol": "TCP",
                                    }
                                ],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "512Mi"},
                                },
                                "securityContext": {
                                    "runAsNonRoot": True,
                                    "runAsUser": 1000,
                                    "readOnlyRootFilesystem": True,
                                    "allowPrivilegeEscalation": False,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": "http"},
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/ready", "port": "http"},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ],
                        "securityContext": {
                            "fsGroup": 2000,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                    },
                },
            },
        }

        return cast(str, yaml.dump(deployment, default_flow_style=False, sort_keys=False))

    def _generate_service(self, config: KustomizeConfig) -> str:
        """Generate service.yaml for base."""
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": config.base.name,
                "labels": {"app": config.base.name},
            },
            "spec": {
                "type": "ClusterIP",
                "ports": [
                    {
                        "port": 80,
                        "targetPort": "http",
                        "protocol": "TCP",
                        "name": "http",
                    }
                ],
                "selector": {"app": config.base.name},
            },
        }

        return cast(str, yaml.dump(service, default_flow_style=False, sort_keys=False))

    def _generate_hpa(self, config: KustomizeConfig) -> str:
        """Generate hpa.yaml for base."""
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": config.base.name,
                "labels": {"app": config.base.name},
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": config.base.name,
                },
                "minReplicas": 1,
                "maxReplicas": 10,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 80},
                        },
                    }
                ],
            },
        }

        return cast(str, yaml.dump(hpa, default_flow_style=False, sort_keys=False))

    def _generate_networkpolicy(self, config: KustomizeConfig) -> str:
        """Generate networkpolicy.yaml for base."""
        networkpolicy = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{config.base.name}-policy",
                "labels": {"app": config.base.name},
            },
            "spec": {
                "podSelector": {"matchLabels": {"app": config.base.name}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {
                        "from": [{"podSelector": {}}],
                        "ports": [{"protocol": "TCP", "port": config.container_port}],
                    }
                ],
                "egress": [
                    {
                        "to": [{"namespaceSelector": {}}],
                        "ports": [
                            {"protocol": "UDP", "port": 53},
                            {"protocol": "TCP", "port": 53},
                        ],
                    }
                ],
            },
        }

        return cast(str, yaml.dump(networkpolicy, default_flow_style=False, sort_keys=False))

    def _generate_base_kustomization(
        self, config: KustomizeConfig, files: Dict[str, str]
    ) -> str:
        """Generate kustomization.yaml for base."""
        # Extract resource filenames from generated files
        resources = []
        for path in files.keys():
            if path.startswith("base/") and path != "base/kustomization.yaml":
                resources.append(path.replace("base/", ""))

        kustomization: Dict[str, Any] = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": sorted(resources),
        }

        if config.base.namespace != "default":
            kustomization["namespace"] = config.base.namespace

        if config.base.common_labels:
            kustomization["commonLabels"] = config.base.common_labels

        if config.base.common_annotations:
            kustomization["commonAnnotations"] = config.base.common_annotations

        if config.base.name_prefix:
            kustomization["namePrefix"] = config.base.name_prefix

        if config.base.name_suffix:
            kustomization["nameSuffix"] = config.base.name_suffix

        if config.base.images:
            kustomization["images"] = []
            for img in config.base.images:
                img_entry: Dict[str, str] = {"name": img.name}
                if img.new_name:
                    img_entry["newName"] = img.new_name
                if img.new_tag:
                    img_entry["newTag"] = img.new_tag
                if img.digest:
                    img_entry["digest"] = img.digest
                kustomization["images"].append(img_entry)

        if config.base.config_map_generators:
            kustomization["configMapGenerator"] = []
            for cm in config.base.config_map_generators:
                cm_entry: Dict[str, Any] = {"name": cm.name}
                if cm.files:
                    cm_entry["files"] = cm.files
                if cm.literals:
                    cm_entry["literals"] = cm.literals
                if cm.envs:
                    cm_entry["envs"] = cm.envs
                kustomization["configMapGenerator"].append(cm_entry)

        if config.base.secret_generators:
            kustomization["secretGenerator"] = []
            for secret in config.base.secret_generators:
                secret_entry: Dict[str, Any] = {"name": secret.name, "type": secret.type}
                if secret.files:
                    secret_entry["files"] = secret.files
                if secret.literals:
                    secret_entry["literals"] = secret.literals
                if secret.envs:
                    secret_entry["envs"] = secret.envs
                kustomization["secretGenerator"].append(secret_entry)

        return cast(str, yaml.dump(kustomization, default_flow_style=False, sort_keys=False))

    def _validate_base(
        self, files: Dict[str, str], config: KustomizeConfig
    ) -> List[str]:
        """Validate the generated base configuration."""
        issues: List[str] = []

        if "base/kustomization.yaml" not in files:
            issues.append("Missing base kustomization.yaml")

        if config.generate_deployment and "base/deployment.yaml" not in files:
            issues.append("Missing deployment.yaml in base")

        if config.generate_service and "base/service.yaml" not in files:
            issues.append("Missing service.yaml in base")

        kustomization = files.get("base/kustomization.yaml", "")
        if "resources:" not in kustomization:
            issues.append("kustomization.yaml has no resources defined")

        return issues

    def _calculate_best_practice_score(
        self, files: Dict[str, str], config: KustomizeConfig
    ) -> float:
        """Calculate a best practice score for the generated base."""
        score = 0.0
        max_score = 0.0

        # kustomization.yaml present
        max_score += 20
        if "base/kustomization.yaml" in files:
            score += 20

        # Deployment present
        max_score += 20
        if "base/deployment.yaml" in files:
            score += 20
            deployment = files["base/deployment.yaml"]
            # Check for security context
            max_score += 15
            if "securityContext:" in deployment and "runAsNonRoot:" in deployment:
                score += 15
            # Check for resource limits
            max_score += 15
            if "resources:" in deployment and "limits:" in deployment:
                score += 15
            # Check for health probes
            max_score += 15
            if "livenessProbe:" in deployment and "readinessProbe:" in deployment:
                score += 15

        # Service present
        max_score += 10
        if "base/service.yaml" in files:
            score += 10

        # NetworkPolicy for security
        max_score += 5
        if "base/networkpolicy.yaml" in files:
            score += 5

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_directory(
        self, kustomization: GeneratedKustomization, output_dir: Optional[str] = None
    ) -> str:
        """
        Save generated Kustomize configuration to directory.

        Args:
            kustomization: Generated kustomization to save
            output_dir: Override output directory

        Returns:
            Path to the saved configuration directory
        """
        target_dir = output_dir or self.output_dir

        for file_path, content in kustomization.files.items():
            full_path = os.path.join(target_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
