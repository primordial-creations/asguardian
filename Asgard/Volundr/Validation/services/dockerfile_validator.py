"""
Dockerfile Validator Service

Validates Dockerfiles for best practices, security issues,
and common misconfigurations (hadolint-style).
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.dockerfile_validator_helpers import (
    build_report,
    check_run_consolidation,
    validate_instruction,
)


class DockerfileValidator:
    """Validates Dockerfiles for best practices."""

    FROM_PATTERN = re.compile(r'^FROM\s+(.+?)(?:\s+AS\s+(\w+))?$', re.IGNORECASE)
    RUN_PATTERN = re.compile(r'^RUN\s+(.+)$', re.IGNORECASE | re.DOTALL)
    COPY_PATTERN = re.compile(r'^COPY\s+(.+)$', re.IGNORECASE)
    ADD_PATTERN = re.compile(r'^ADD\s+(.+)$', re.IGNORECASE)
    ENV_PATTERN = re.compile(r'^ENV\s+(.+)$', re.IGNORECASE)
    EXPOSE_PATTERN = re.compile(r'^EXPOSE\s+(.+)$', re.IGNORECASE)
    USER_PATTERN = re.compile(r'^USER\s+(.+)$', re.IGNORECASE)
    WORKDIR_PATTERN = re.compile(r'^WORKDIR\s+(.+)$', re.IGNORECASE)
    CMD_PATTERN = re.compile(r'^CMD\s+(.+)$', re.IGNORECASE)
    ENTRYPOINT_PATTERN = re.compile(r'^ENTRYPOINT\s+(.+)$', re.IGNORECASE)
    HEALTHCHECK_PATTERN = re.compile(r'^HEALTHCHECK\s+(.+)$', re.IGNORECASE)
    LABEL_PATTERN = re.compile(r'^LABEL\s+(.+)$', re.IGNORECASE)
    ARG_PATTERN = re.compile(r'^ARG\s+(.+)$', re.IGNORECASE)

    INSECURE_IMAGES = {
        "python:latest",
        "node:latest",
        "ruby:latest",
        "php:latest",
        "java:latest",
        "nginx:latest",
    }

    def __init__(self, context: Optional[ValidationContext] = None):
        self.context = context or ValidationContext()

    def validate_file(self, file_path: str) -> ValidationReport:
        start_time = time.time()
        results: List[ValidationResult] = []

        if not os.path.exists(file_path):
            results.append(ValidationResult(
                rule_id="DL0001",
                message=f"File not found: {file_path}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return build_report([file_path], results, start_time, self.context)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            results.append(ValidationResult(
                rule_id="DL0002",
                message=f"Error reading file: {e}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return build_report([file_path], results, start_time, self.context)

        results.extend(self._validate_content(content, file_path))
        return build_report([file_path], results, start_time, self.context)

    def validate_directory(self, directory: str) -> ValidationReport:
        start_time = time.time()
        results: List[ValidationResult] = []
        files_validated: List[str] = []

        path = Path(directory)
        if not path.exists():
            results.append(ValidationResult(
                rule_id="DL0001",
                message=f"Directory not found: {directory}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
            ))
            return build_report([], results, start_time, self.context)

        for file_path in path.rglob("Dockerfile*"):
            files_validated.append(str(file_path))
            file_results = self.validate_file(str(file_path))
            results.extend(file_results.results)

        return build_report(files_validated, results, start_time, self.context)

    def validate_content(self, content: str, source: str = "Dockerfile") -> ValidationReport:
        start_time = time.time()
        results = self._validate_content(content, source)
        return build_report([source], results, start_time, self.context)

    def _validate_content(self, content: str, file_path: str) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        lines = content.split("\n")

        has_from = False
        has_user = False
        has_healthcheck = False
        last_user = "root"
        from_count = 0
        run_commands: List[Tuple[int, str]] = []
        copy_commands: List[Tuple[int, str]] = []

        line_num = 0
        current_instruction = ""

        for i, line in enumerate(lines):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.endswith("\\"):
                current_instruction += stripped[:-1] + " "
                continue
            else:
                current_instruction += stripped
                instruction = current_instruction
                current_instruction = ""
                line_num = i + 1

            results.extend(validate_instruction(
                instruction, file_path, line_num,
                has_from, last_user, run_commands, copy_commands,
                self.FROM_PATTERN, self.RUN_PATTERN, self.COPY_PATTERN,
                self.ADD_PATTERN, self.EXPOSE_PATTERN, self.WORKDIR_PATTERN,
                self.CMD_PATTERN, self.INSECURE_IMAGES,
            ))

            if self.FROM_PATTERN.match(instruction):
                has_from = True
                from_count += 1
            elif self.USER_PATTERN.match(instruction):
                has_user = True
                match = self.USER_PATTERN.match(instruction)
                if match:
                    last_user = match.group(1).strip()
            elif self.HEALTHCHECK_PATTERN.match(instruction):
                has_healthcheck = True
            elif self.RUN_PATTERN.match(instruction):
                match = self.RUN_PATTERN.match(instruction)
                if match:
                    run_commands.append((line_num, match.group(1)))
            elif self.COPY_PATTERN.match(instruction):
                match = self.COPY_PATTERN.match(instruction)
                if match:
                    copy_commands.append((line_num, match.group(1)))

        if not has_from:
            results.append(ValidationResult(
                rule_id="DL3000",
                message="Dockerfile must start with a FROM instruction",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))

        if not has_user and from_count > 0:
            results.append(ValidationResult(
                rule_id="DL3002",
                message="Last USER should not be root",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                file_path=file_path,
                suggestion="Add USER instruction with non-root user",
            ))

        if last_user.lower() == "root" and has_user:
            results.append(ValidationResult(
                rule_id="DL3002",
                message="Last USER should not be root",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                file_path=file_path,
                suggestion="Change to a non-root user before CMD/ENTRYPOINT",
            ))

        if not has_healthcheck and from_count > 0:
            results.append(ValidationResult(
                rule_id="DL3055",
                message="No HEALTHCHECK defined",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                suggestion="Add HEALTHCHECK instruction for container health monitoring",
            ))

        results.extend(check_run_consolidation(run_commands, file_path))

        return results
