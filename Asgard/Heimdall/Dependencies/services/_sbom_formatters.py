"""
Heimdall SBOM Generator - Format Converters

Standalone functions for converting SBOMDocument instances to
SPDX 2.3 and CycloneDX 1.4 JSON representations.
"""

from datetime import datetime
from typing import Any, Dict

from Asgard.Heimdall.Dependencies.models.sbom_models import (
    SBOMComponent,
    SBOMDocument,
)

import re


def to_spdx_json(document: SBOMDocument) -> Dict[str, Any]:
    """
    Convert an SBOMDocument to a valid SPDX 2.3 JSON representation.

    Args:
        document: The SBOM document to convert.

    Returns:
        Dictionary conforming to the SPDX 2.3 JSON schema.
    """
    packages = []
    for component in document.components:
        name = component.name if isinstance(component, SBOMComponent) else component["name"]
        version = component.version if isinstance(component, SBOMComponent) else component["version"]
        license_id = component.license_id if isinstance(component, SBOMComponent) else component.get("license_id", "")
        purl = component.purl if isinstance(component, SBOMComponent) else component.get("purl", "")

        spdx_id = f"SPDXRef-Package-{re.sub(r'[^a-zA-Z0-9.-]', '-', name)}"
        concluded_license = license_id if license_id else "NOASSERTION"

        package: Dict[str, Any] = {
            "SPDXID": spdx_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": concluded_license,
            "licenseDeclared": concluded_license,
            "copyrightText": "NOASSERTION",
        }
        if purl:
            package["externalRefs"] = [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": purl,
                }
            ]
        packages.append(package)

    doc_id = document.document_id if isinstance(document.document_id, str) else str(document.document_id)
    created_at = document.created_at if isinstance(document.created_at, datetime) else datetime.fromisoformat(str(document.created_at))
    project_name = document.project_name if isinstance(document.project_name, str) else str(document.project_name)
    document_name = document.document_name if isinstance(document.document_name, str) else str(document.document_name)
    creator_tool = document.creator_tool if isinstance(document.creator_tool, str) else str(document.creator_tool)

    result: Dict[str, Any] = {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "creationInfo": {
            "created": created_at.isoformat() + "Z",
            "creators": [
                f"Tool: {creator_tool}",
            ],
        },
        "name": document_name,
        "dataLicense": "CC0-1.0",
        "documentNamespace": f"https://spdx.org/spdxdocs/{project_name}-{doc_id}",
        "packages": packages,
    }
    return result


def to_cyclonedx_json(document: SBOMDocument) -> Dict[str, Any]:
    """
    Convert an SBOMDocument to a valid CycloneDX 1.4 JSON representation.

    Args:
        document: The SBOM document to convert.

    Returns:
        Dictionary conforming to the CycloneDX 1.4 JSON schema.
    """
    components = []
    for component in document.components:
        name = component.name if isinstance(component, SBOMComponent) else component["name"]
        version = component.version if isinstance(component, SBOMComponent) else component["version"]
        purl = component.purl if isinstance(component, SBOMComponent) else component.get("purl", "")
        license_id = component.license_id if isinstance(component, SBOMComponent) else component.get("license_id", "")
        comp_type = "library"

        cdx_component: Dict[str, Any] = {
            "type": comp_type,
            "name": name,
            "version": version,
        }
        if purl:
            cdx_component["purl"] = purl
        if license_id:
            cdx_component["licenses"] = [{"license": {"id": license_id}}]
        components.append(cdx_component)

    doc_id = document.document_id if isinstance(document.document_id, str) else str(document.document_id)
    created_at = document.created_at if isinstance(document.created_at, datetime) else datetime.fromisoformat(str(document.created_at))
    creator_tool = document.creator_tool if isinstance(document.creator_tool, str) else str(document.creator_tool)

    result: Dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{doc_id}",
        "version": 1,
        "metadata": {
            "timestamp": created_at.isoformat() + "Z",
            "tools": [
                {
                    "name": creator_tool,
                }
            ],
        },
        "components": components,
    }
    return result
