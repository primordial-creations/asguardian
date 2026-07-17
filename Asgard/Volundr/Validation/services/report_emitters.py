"""
Standard-format report emitters: SARIF 2.1.0 and JUnit XML.

SARIF rules[] metadata is populated from the rule registry, including
``help.markdown`` remediation snippets, so IDE/CI SARIF viewers render
actionable findings.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    default_registry,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)

_SARIF_LEVELS = {
    ValidationSeverity.ERROR: "error",
    ValidationSeverity.WARNING: "warning",
    ValidationSeverity.INFO: "note",
    ValidationSeverity.HINT: "none",
}


def _sarif_rule(rule_id: str, registry: RuleRegistry) -> Dict[str, Any]:
    rule = registry.get(rule_id)
    entry: Dict[str, Any] = {"id": rule_id}
    if rule is not None:
        entry["name"] = rule.name
        entry["shortDescription"] = {"text": rule.description}
        entry["help"] = {
            "text": rule.remediation or rule.description,
            "markdown": rule.remediation or rule.description,
        }
        entry["defaultConfiguration"] = {
            "level": _SARIF_LEVELS[rule.severity.to_validation_severity()]
        }
        if rule.documentation_url:
            entry["helpUri"] = rule.documentation_url
        if rule.framework_mappings:
            entry["properties"] = {"frameworkMappings": rule.framework_mappings}
    else:
        entry["shortDescription"] = {"text": rule_id}
        entry["help"] = {"text": rule_id, "markdown": rule_id}
    return entry


def _sarif_result(result: ValidationResult) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "ruleId": result.rule_id,
        "level": _SARIF_LEVELS[result.severity],
        "message": {"text": result.message},
    }
    if result.file_path:
        location: Dict[str, Any] = {
            "physicalLocation": {
                "artifactLocation": {"uri": result.file_path},
            }
        }
        if result.line_number:
            region: Dict[str, Any] = {"startLine": result.line_number}
            if result.column:
                region["startColumn"] = result.column
            location["physicalLocation"]["region"] = region
        entry["locations"] = [location]
    return entry


def to_sarif(
    report: ValidationReport, registry: Optional[RuleRegistry] = None
) -> Dict[str, Any]:
    """Emit a SARIF 2.1.0 log dict from a ValidationReport."""
    registry = registry or default_registry()
    rule_ids = sorted({r.rule_id for r in report.results})
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Volundr",
                        "informationUri": "https://github.com/asgard/asguardian",
                        "rules": [_sarif_rule(rid, registry) for rid in rule_ids],
                    }
                },
                "results": [_sarif_result(r) for r in report.results],
            }
        ],
    }


def to_junit_xml(report: ValidationReport) -> str:
    """Emit a JUnit XML string from a ValidationReport.

    Each finding becomes a failed testcase; a clean report emits one
    passing case per validated file so CI shows explicit successes.
    """
    failures = [
        r for r in report.results
        if r.severity in (ValidationSeverity.ERROR, ValidationSeverity.WARNING)
    ]
    suite = ET.Element(
        "testsuite",
        name=report.title,
        tests=str(max(len(failures), report.total_files, 1)),
        failures=str(sum(
            1 for r in failures if r.severity == ValidationSeverity.WARNING
        )),
        errors=str(sum(
            1 for r in failures if r.severity == ValidationSeverity.ERROR
        )),
        time=str((report.duration_ms or 0) / 1000.0),
    )
    if failures:
        for result in failures:
            case = ET.SubElement(
                suite, "testcase",
                classname=result.file_path or report.validator,
                name=result.rule_id,
            )
            tag = (
                "error" if result.severity == ValidationSeverity.ERROR
                else "failure"
            )
            elem = ET.SubElement(case, tag, message=result.message)
            elem.text = result.location or ""
    else:
        for summary in report.file_summaries or [None]:
            name = summary.file_path if summary else "validation"
            ET.SubElement(
                suite, "testcase", classname=report.validator, name=name
            )
    return ET.tostring(suite, encoding="unicode", xml_declaration=True)
