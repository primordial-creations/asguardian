"""
Curated SHA pin-map for well-known GitHub Actions.

Mutable tag references (``actions/checkout@v4``) are a supply-chain attack
vector: tags can be force-pushed to point at malicious commits (see the
March 2026 TeamPCP tag-poisoning incident against trivy-action). Every
``uses:`` reference the generator emits is therefore resolved to a full
40-character commit SHA, with the human-readable tag preserved as a
trailing comment.

The pin map below is curated data refreshed at release time (pair the
generated workflows with the Renovate config snippet from
``renovate_pin_config()`` to keep pins current). Unknown actions supplied
by the user are passed through unchanged and surface as a
``VOL-CICD-0002`` finding unless already SHA-pinned or suppressed.
"""

import re
from typing import Dict, Optional, Tuple

# tag-ref -> (full commit SHA, resolved version comment)
# NOTE: refreshed at release time; see module docstring.
KNOWN_ACTION_PINS: Dict[str, Tuple[str, str]] = {
    "actions/checkout@v4": ("11bd71901bbe5b1630ceea73d27597364c9af683", "v4.2.2"),
    "actions/checkout@v5": ("08c6903cd8c0fde910a37f88322edcfb5dd907a8", "v5.0.0"),
    "actions/setup-python@v5": ("a26af69be951a213d495a4c3e4e4022e16d87065", "v5.6.0"),
    "actions/setup-node@v4": ("49933ea5288caeca8642d1e84afbd3f7d6820020", "v4.4.0"),
    "actions/cache@v4": ("5a3ec84eff668545956fd18022155c47e93e2684", "v4.2.3"),
    "actions/upload-artifact@v4": ("ea165f8d65b6e75b540449e92b4886f43607fa02", "v4.6.2"),
    "actions/download-artifact@v4": ("d3f86a106a0bac45b974a628896c90dbdf5c8093", "v4.3.0"),
    "actions/attest-build-provenance@v2": ("e8998f949152b193b063cb0ec769d69d929409be", "v2.4.0"),
    "docker/build-push-action@v5": ("4a13e500e55cf31b7a5d59a38ab2040ab0f42f56", "v5.1.0"),
    "docker/build-push-action@v6": ("263435318d21b8e681c14492fe198d362a7d2c83", "v6.18.0"),
    "docker/login-action@v3": ("74a5d142397b4f367a81961eba4e8cd7edddf772", "v3.4.0"),
    "docker/setup-buildx-action@v3": ("b5ca514318bd6ebac0fb2aedd5d36ec1b5c232a2", "v3.10.0"),
    "aws-actions/configure-aws-credentials@v4": ("b47578312673ae6fa5b5096b330d9fbac3d116df", "v4.2.1"),
    "google-github-actions/auth@v2": ("ba79af03959ebeac9769e648f473a284504d9193", "v2.1.10"),
    "azure/login@v2": ("a457da9ea143d694b1b9c7c869ebb04ebe844ef5", "v2.3.0"),
    "hashicorp/vault-action@v3": ("7709c609789c5e27b757a85817483caadbb5939a", "v3.3.0"),
    "step-security/harden-runner@v2": ("0634a2670c59f64b4a01f0f96f84700a4088b9f0", "v2.12.0"),
    "anchore/sbom-action@v0": ("e11c554f704a0b820cbf8c51673f6945e0731532", "v0.20.0"),
}

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def is_sha_pinned(uses: str) -> bool:
    """True if the ``uses:`` reference is pinned to a full commit SHA."""
    if "@" not in uses:
        return False
    ref = uses.rsplit("@", 1)[1]
    return bool(_SHA_RE.match(ref.lower()))


def resolve_action_ref(uses: str) -> Tuple[str, Optional[str]]:
    """Resolve a ``uses:`` reference against the curated pin map.

    Returns ``(pinned_ref, version_comment)``. Local actions (``./...``),
    docker refs, and already-SHA-pinned refs pass through unchanged
    (comment ``None``). Known mutable tags are rewritten to their SHA with
    the tag returned as the version comment. Unknown mutable tags pass
    through unchanged (the validation engine flags them as VOL-CICD-0002).
    """
    if uses.startswith("./") or uses.startswith("docker://"):
        return uses, None
    if is_sha_pinned(uses):
        return uses, None
    pin = KNOWN_ACTION_PINS.get(uses)
    if pin is None:
        return uses, None
    sha, version = pin
    action = uses.rsplit("@", 1)[0]
    return f"{action}@{sha}", version


def pinned(action_tag: str) -> str:
    """Return the SHA-pinned form of a known action tag (for generator use)."""
    ref, _ = resolve_action_ref(action_tag)
    return ref


def version_comment(action_tag: str) -> Optional[str]:
    """Return the version comment for a known action tag, if any."""
    pin = KNOWN_ACTION_PINS.get(action_tag)
    return pin[1] if pin else None


def annotate_pinned_uses(rendered_yaml: str) -> str:
    """Append ``# vX.Y.Z`` comments to SHA-pinned ``uses:`` lines.

    PyYAML cannot emit comments, so the version-comment half of the
    pinning contract is applied as a post-processing pass over the
    rendered text.
    """
    sha_to_version = {
        sha: (tag.rsplit("@", 1)[0], version)
        for tag, (sha, version) in KNOWN_ACTION_PINS.items()
    }
    out_lines = []
    for line in rendered_yaml.splitlines():
        stripped = line.strip()
        if stripped.startswith("uses:") or stripped.startswith("- uses:"):
            for sha, (action, version) in sha_to_version.items():
                if f"{action}@{sha}" in line and "#" not in line:
                    line = f"{line}  # {version}"
                    break
        out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if rendered_yaml.endswith("\n") else "")


def renovate_pin_config() -> str:
    """Renovate config snippet keeping SHA pins current (paired output)."""
    return (
        '{\n'
        '  "$schema": "https://docs.renovatebot.com/renovate-schema.json",\n'
        '  "extends": ["config:best-practices", "helpers:pinGitHubActionDigests"],\n'
        '  "packageRules": [\n'
        '    {\n'
        '      "matchManagers": ["github-actions"],\n'
        '      "pinDigests": true\n'
        '    }\n'
        '  ]\n'
        '}\n'
    )
