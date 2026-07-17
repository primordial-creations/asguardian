"""
Kustomize Models for Configuration Generation

Provides Pydantic models for configuring and generating Kustomize
bases, overlays, and patches with best practices.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatchType(str, Enum):
    """Kustomize patch types."""
    STRATEGIC_MERGE = "strategic_merge"
    JSON6902 = "json6902"


class PatchTarget(BaseModel):
    """Target for JSON6902 patches."""
    group: Optional[str] = Field(default=None, description="API group")
    version: str = Field(default="v1", description="API version")
    kind: str = Field(description="Resource kind")
    name: str = Field(description="Resource name")
    namespace: Optional[str] = Field(default=None, description="Resource namespace")


class JsonPatchOperation(BaseModel):
    """JSON6902 patch operation."""
    op: str = Field(description="Operation type (add, remove, replace)")
    path: str = Field(description="JSON path")
    value: Optional[Any] = Field(default=None, description="Value for add/replace")


class KustomizePatch(BaseModel):
    """Kustomize patch configuration."""
    name: str = Field(description="Patch name")
    patch_type: PatchType = Field(default=PatchType.STRATEGIC_MERGE, description="Patch type")
    target: Optional[PatchTarget] = Field(default=None, description="Target for JSON6902 patches")
    patch_content: Optional[str] = Field(default=None, description="Patch YAML content")
    operations: List[JsonPatchOperation] = Field(default_factory=list, description="JSON6902 operations")


class ConfigMapGenerator(BaseModel):
    """ConfigMap generator configuration."""
    name: str = Field(description="ConfigMap name")
    files: List[str] = Field(default_factory=list, description="Files to include")
    literals: List[str] = Field(default_factory=list, description="Literal key=value pairs")
    envs: List[str] = Field(default_factory=list, description="Env files to include")
    behavior: str = Field(default="create", description="Behavior (create, replace, merge)")
    options: Dict[str, Any] = Field(default_factory=dict, description="Generator options")


class SecretGenerator(BaseModel):
    """Secret generator configuration."""
    name: str = Field(description="Secret name")
    type: str = Field(default="Opaque", description="Secret type")
    files: List[str] = Field(default_factory=list, description="Files to include")
    literals: List[str] = Field(default_factory=list, description="Literal key=value pairs")
    envs: List[str] = Field(default_factory=list, description="Env files to include")
    behavior: str = Field(default="create", description="Behavior (create, replace, merge)")
    options: Dict[str, Any] = Field(default_factory=dict, description="Generator options")


class ReplacementSource(BaseModel):
    """Source of a Kustomize v5 replacement (never `vars` — RESEARCH_09)."""
    kind: str = Field(description="Source resource kind")
    name: str = Field(description="Source resource name")
    version: Optional[str] = Field(default=None, description="API version")
    field_path: str = Field(
        default="metadata.name", description="Dot-path to the source value"
    )


class ReplacementTargetSelect(BaseModel):
    """Target selector for a replacement."""
    kind: Optional[str] = Field(default=None, description="Target kind")
    name: Optional[str] = Field(default=None, description="Target name")
    group: Optional[str] = Field(default=None, description="Target API group")
    version: Optional[str] = Field(default=None, description="Target API version")


class ReplacementTarget(BaseModel):
    """A replacement target: where the source value is written.

    Field paths should address arrays by semantic key
    (``spec.containers.[name=app].image``), never by index (RESEARCH_09).
    """
    select: ReplacementTargetSelect = Field(description="Target selector")
    field_paths: List[str] = Field(description="Field paths to rewrite")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Options (delimiter, index, create)"
    )


class Replacement(BaseModel):
    """Kustomize v5 replacement (the `vars` successor)."""
    source: ReplacementSource = Field(description="Value source")
    targets: List[ReplacementTarget] = Field(description="Write targets")


class ImageTransformer(BaseModel):
    """Image transformer configuration."""
    name: str = Field(description="Original image name")
    new_name: Optional[str] = Field(default=None, description="New image name")
    new_tag: Optional[str] = Field(default=None, description="New image tag")
    digest: Optional[str] = Field(default=None, description="Image digest")


class ReplicaTransformer(BaseModel):
    """Replica count transformer configuration."""
    name: str = Field(description="Resource name")
    count: int = Field(description="Replica count")


class KustomizeComponent(BaseModel):
    """Kustomize component configuration."""
    name: str = Field(description="Component name")
    resources: List[str] = Field(default_factory=list, description="Resources to include")
    patches: List[KustomizePatch] = Field(default_factory=list, description="Patches to apply")
    config_map_generators: List[ConfigMapGenerator] = Field(
        default_factory=list, description="ConfigMap generators"
    )
    secret_generators: List[SecretGenerator] = Field(default_factory=list, description="Secret generators")


class KustomizeBase(BaseModel):
    """Kustomize base configuration."""
    name: str = Field(description="Application name")
    namespace: str = Field(default="default", description="Namespace")
    resources: List[str] = Field(default_factory=list, description="Resource files")
    common_labels: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Labels applied via the v5 `labels` transformer with "
            "includeSelectors: false (never `commonLabels`, which mutates "
            "immutable selectors — VOL-KUST-COMMONLABELS)"
        ),
    )
    labels_include_selectors: bool = Field(
        default=False,
        description=(
            "Set includeSelectors on the labels transformer. Selector "
            "labels are immutable on live workloads; only enable for a "
            "brand-new base that has never been applied"
        ),
    )
    replacements: List[Replacement] = Field(
        default_factory=list, description="Kustomize v5 replacements (never vars)"
    )
    openapi_path: Optional[str] = Field(
        default=None,
        description=(
            "Path to an OpenAPI schema file (`openapi: {path: ...}`) so CRD "
            "strategic-merge patches keep their merge keys (RESEARCH_09)"
        ),
    )
    common_annotations: Dict[str, str] = Field(default_factory=dict, description="Common annotations")
    name_prefix: str = Field(default="", description="Name prefix")
    name_suffix: str = Field(default="", description="Name suffix")
    images: List[ImageTransformer] = Field(default_factory=list, description="Image transformers")
    config_map_generators: List[ConfigMapGenerator] = Field(
        default_factory=list, description="ConfigMap generators"
    )
    secret_generators: List[SecretGenerator] = Field(default_factory=list, description="Secret generators")
    patches: List[KustomizePatch] = Field(default_factory=list, description="Patches")
    components: List[str] = Field(default_factory=list, description="Component paths")


class KustomizeOverlay(BaseModel):
    """Kustomize overlay configuration."""
    name: str = Field(description="Overlay name (e.g., 'production', 'staging')")
    bases: List[str] = Field(default_factory=lambda: ["../../base"], description="Base paths")
    namespace: Optional[str] = Field(default=None, description="Override namespace")
    name_prefix: str = Field(default="", description="Name prefix")
    name_suffix: str = Field(default="", description="Name suffix")
    common_labels: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Labels applied via the v5 `labels` transformer with "
            "includeSelectors: false (never `commonLabels`)"
        ),
    )
    replacements: List[Replacement] = Field(
        default_factory=list, description="Kustomize v5 replacements (never vars)"
    )
    openapi_path: Optional[str] = Field(
        default=None, description="OpenAPI schema passthrough (`openapi: {path: ...}`)"
    )
    common_annotations: Dict[str, str] = Field(default_factory=dict, description="Additional annotations")
    images: List[ImageTransformer] = Field(default_factory=list, description="Image overrides")
    replicas: List[ReplicaTransformer] = Field(default_factory=list, description="Replica overrides")
    config_map_generators: List[ConfigMapGenerator] = Field(
        default_factory=list, description="ConfigMap generators"
    )
    secret_generators: List[SecretGenerator] = Field(default_factory=list, description="Secret generators")
    patches: List[KustomizePatch] = Field(default_factory=list, description="Patches")
    patch_files: List[str] = Field(default_factory=list, description="External patch files")
    components: List[str] = Field(default_factory=list, description="Component paths")
    resources: List[str] = Field(default_factory=list, description="Additional resources")


class KustomizeConfig(BaseModel):
    """Complete Kustomize configuration for base and overlays."""
    base: KustomizeBase = Field(description="Base configuration")
    overlays: List[KustomizeOverlay] = Field(default_factory=list, description="Environment overlays")
    components: List[KustomizeComponent] = Field(default_factory=list, description="Reusable components")
    generate_deployment: bool = Field(default=True, description="Generate deployment resource")
    generate_service: bool = Field(default=True, description="Generate service resource")
    generate_hpa: bool = Field(default=False, description="Generate HPA resource")
    generate_networkpolicy: bool = Field(default=False, description="Generate NetworkPolicy resource")
    image: str = Field(description="Container image")
    container_port: int = Field(default=8080, description="Container port")
    replicas: int = Field(default=1, description="Default replica count")


class GeneratedKustomization(BaseModel):
    """Result of Kustomize configuration generation."""
    id: str = Field(description="Unique configuration ID")
    config_hash: str = Field(description="Hash of the configuration")
    files: Dict[str, str] = Field(description="Generated files (path -> content)")
    validation_results: List[str] = Field(default_factory=list, description="Validation issues found")
    best_practice_score: float = Field(ge=0, le=100, description="Best practice compliance score")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    output_path: Optional[str] = Field(default=None, description="Path where files were saved")

    @property
    def has_issues(self) -> bool:
        """Check if there are validation issues."""
        return len(self.validation_results) > 0

    @property
    def file_count(self) -> int:
        """Get the number of generated files."""
        return len(self.files)
