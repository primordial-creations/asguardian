"""
Container/IaC compliance control mapping (plan 07.8, RESEARCH_08).

Maps each ``ContainerFindingType`` to a normalization-engine
``mechanism_id`` (plan 06) plus CIS Docker Benchmark and NIST SP 800-190
control references, extending the compliance-mapping approach already
used by ``Security/Compliance``. Applied as a post-processing pass over a
finished finding list (``apply_compliance_mapping``) so every check
function across dockerfile/compose sources gets consistent metadata
without having to be edited individually.

Control-ID mappings are the commonly-cited CIS Docker Benchmark v1.6.0
section numbers / NIST SP 800-190 section numbers for each check; treat
them as an aid for compliance reporting, not a certified audit mapping.
"""

from typing import Dict, Optional, Tuple

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerFinding,
    ContainerFindingType,
)

# finding_type -> (mechanism_id, CIS Docker Benchmark id, NIST SP 800-190 ref)
_MAPPING: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {
    ContainerFindingType.ROOT_USER.value: (
        "container.root_user", "CIS-Docker-4.1", "NIST-800-190-4.1.2",
    ),
    ContainerFindingType.LATEST_TAG.value: (
        "container.latest_tag", "CIS-Docker-4.2", "NIST-800-190-4.1.1",
    ),
    ContainerFindingType.SECRETS_IN_IMAGE.value: (
        "container.secrets_in_image", "CIS-Docker-4.10", "NIST-800-190-4.1.4",
    ),
    ContainerFindingType.EXPOSED_PORTS.value: (
        "container.exposed_ports", "CIS-Docker-5.9", "NIST-800-190-4.4.2",
    ),
    ContainerFindingType.PRIVILEGED_MODE.value: (
        "container.privileged_mode", "CIS-Docker-5.4", "NIST-800-190-4.3.1",
    ),
    ContainerFindingType.CHMOD_777.value: (
        "container.chmod_777", "CIS-Docker-4.1", "NIST-800-190-4.1.2",
    ),
    ContainerFindingType.APT_INSTALL_SUDO.value: (
        "container.apt_install_sudo", "CIS-Docker-4.1", "NIST-800-190-4.1.2",
    ),
    ContainerFindingType.MISSING_HEALTHCHECK.value: (
        "container.missing_healthcheck", "CIS-Docker-4.6", "NIST-800-190-4.4.4",
    ),
    ContainerFindingType.ADD_INSTEAD_OF_COPY.value: (
        "container.add_instead_of_copy", "CIS-Docker-4.9", "NIST-800-190-4.1.3",
    ),
    ContainerFindingType.CURL_PIPE_BASH.value: (
        "container.curl_pipe_bash", "CIS-Docker-4.1", "NIST-800-190-4.1.2",
    ),
    ContainerFindingType.HARDCODED_SECRET.value: (
        "container.hardcoded_secret", "CIS-Docker-4.10", "NIST-800-190-4.1.4",
    ),
    ContainerFindingType.INSECURE_REGISTRY.value: (
        "container.insecure_registry", "CIS-Docker-2.4", "NIST-800-190-4.1.1",
    ),
    ContainerFindingType.HOST_NETWORK.value: (
        "container.host_network", "CIS-Docker-5.9", "NIST-800-190-4.3.4",
    ),
    ContainerFindingType.HOST_PID.value: (
        "container.host_pid", "CIS-Docker-5.15", "NIST-800-190-4.3.4",
    ),
    ContainerFindingType.CAP_SYS_ADMIN.value: (
        "container.cap_sys_admin", "CIS-Docker-5.3", "NIST-800-190-4.3.2",
    ),
    ContainerFindingType.UNRESTRICTED_VOLUME.value: (
        "container.unrestricted_volume", "CIS-Docker-5.5", "NIST-800-190-4.3.3",
    ),
    ContainerFindingType.NO_SECURITY_OPT.value: (
        "container.no_security_opt", "CIS-Docker-5.21", "NIST-800-190-4.3.2",
    ),
    ContainerFindingType.WRITABLE_ROOT_FS.value: (
        "container.writable_root_fs", "CIS-Docker-5.12", "NIST-800-190-4.3.3",
    ),
    ContainerFindingType.ADD_REMOTE_URL.value: (
        "container.add_remote_url", "CIS-Docker-4.9", "NIST-800-190-4.1.3",
    ),
}


def apply_compliance_mapping(findings) -> None:
    """Mutate a list of ContainerFinding in place, filling mechanism_id/CIS/NIST fields."""
    for f in findings:
        key = f.finding_type.value if hasattr(f.finding_type, "value") else str(f.finding_type)
        mapped = _MAPPING.get(key)
        if mapped is None:
            f.mechanism_id = f.mechanism_id or f"container.{key}"
            continue
        mechanism_id, cis_id, nist_ref = mapped
        f.mechanism_id = mechanism_id
        f.cis_docker_benchmark = cis_id
        f.nist_800_190 = nist_ref
