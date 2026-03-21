import hashlib
import re
import time
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Volundr.Validation.models.validation_models import (
    FileValidationSummary,
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)


def validate_instruction(
    instruction: str,
    file_path: str,
    line_num: int,
    has_from: bool,
    last_user: str,
    run_commands: List[Tuple[int, str]],
    copy_commands: List[Tuple[int, str]],
    from_pattern: re.Pattern,  # type: ignore[type-arg]
    run_pattern: re.Pattern,  # type: ignore[type-arg]
    copy_pattern: re.Pattern,  # type: ignore[type-arg]
    add_pattern: re.Pattern,  # type: ignore[type-arg]
    expose_pattern: re.Pattern,  # type: ignore[type-arg]
    workdir_pattern: re.Pattern,  # type: ignore[type-arg]
    cmd_pattern: re.Pattern,  # type: ignore[type-arg]
    insecure_images: Set[str],
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    from_match = from_pattern.match(instruction)
    if from_match:
        image = from_match.group(1).strip()

        if ":latest" in image or (":" not in image and "@" not in image):
            results.append(ValidationResult(
                rule_id="DL3007",
                message=f"Using latest or untagged image: {image}",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                suggestion="Pin to a specific version tag",
            ))

        if image.lower() in insecure_images:
            results.append(ValidationResult(
                rule_id="DL3008",
                message=f"Consider using a more specific or slim variant: {image}",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                suggestion="Use -slim or -alpine variant for smaller images",
            ))

        return results

    if not has_from:
        if not instruction.upper().startswith("ARG"):
            results.append(ValidationResult(
                rule_id="DL3001",
                message="Only ARG instructions may appear before FROM",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
                line_number=line_num,
            ))
            return results

    run_match = run_pattern.match(instruction)
    if run_match:
        cmd = run_match.group(1)
        results.extend(validate_run_instruction(cmd, file_path, line_num))
        return results

    copy_match = copy_pattern.match(instruction)
    if copy_match:
        args = copy_match.group(1)
        results.extend(validate_copy_instruction(args, file_path, line_num))
        return results

    add_match = add_pattern.match(instruction)
    if add_match:
        args = add_match.group(1)
        if not any(x in args for x in ["http://", "https://", ".tar", ".gz", ".bz2", ".xz"]):
            results.append(ValidationResult(
                rule_id="DL3020",
                message="Use COPY instead of ADD for files and folders",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                suggestion="Replace ADD with COPY unless you need auto-extraction",
            ))
        return results

    expose_match = expose_pattern.match(instruction)
    if expose_match:
        ports = expose_match.group(1)
        for port in ports.split():
            port_num = port.replace("/tcp", "").replace("/udp", "")
            try:
                if int(port_num) < 1024 and last_user.lower() != "root":
                    results.append(ValidationResult(
                        rule_id="DL3011",
                        message=f"Privileged port {port_num} requires root or CAP_NET_BIND_SERVICE",
                        severity=ValidationSeverity.INFO,
                        category=ValidationCategory.SECURITY,
                        file_path=file_path,
                        line_number=line_num,
                    ))
            except ValueError:
                pass
        return results

    workdir_match = workdir_pattern.match(instruction)
    if workdir_match:
        path = workdir_match.group(1)
        if not path.startswith("/"):
            results.append(ValidationResult(
                rule_id="DL3000",
                message="WORKDIR should use absolute path",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
            ))
        return results

    cmd_match = cmd_pattern.match(instruction)
    if cmd_match:
        cmd = cmd_match.group(1)
        if not cmd.strip().startswith("["):
            results.append(ValidationResult(
                rule_id="DL3025",
                message="Use JSON notation for CMD",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                suggestion='Use CMD ["executable", "param1", "param2"]',
            ))
        return results

    return results


def validate_run_instruction(
    cmd: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    cmd_lower = cmd.lower()

    if "apt-get install" in cmd_lower and " -y" not in cmd_lower and "-y " not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL3014",
            message="Use apt-get with -y flag",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
        ))

    if "apt-get" in cmd_lower and "rm -rf /var/lib/apt/lists" not in cmd_lower:
        if "apt-get update" in cmd_lower or "apt-get install" in cmd_lower:
            results.append(ValidationResult(
                rule_id="DL3009",
                message="Delete apt-get lists after installing packages",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                suggestion="Add && rm -rf /var/lib/apt/lists/*",
            ))

    if "pip install" in cmd_lower and "--no-cache-dir" not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL3042",
            message="Avoid cache when installing packages",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
            suggestion="Add --no-cache-dir to pip install",
        ))

    if "curl " in cmd_lower and " -f" not in cmd_lower and "--fail" not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL4001",
            message="Use curl with -f flag to fail on HTTP errors",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.RELIABILITY,
            file_path=file_path,
            line_number=line_num,
            suggestion="Add -f or --fail to curl command",
        ))

    if "wget " in cmd_lower and " -O " not in cmd_lower and " --output-document" not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL4002",
            message="Consider using wget with -O to specify output file",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
        ))

    if "sudo " in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL3004",
            message="Do not use sudo as it leads to unpredictable behavior",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            suggestion="Use USER instruction to switch users instead",
        ))

    if "yum install" in cmd_lower and "yum clean" not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL3032",
            message="yum clean all missing after yum install",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
        ))

    if "npm install" in cmd_lower and "npm ci" not in cmd_lower:
        results.append(ValidationResult(
            rule_id="DL3016",
            message="Consider using npm ci instead of npm install for reproducible builds",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
        ))

    return results


def validate_copy_instruction(
    args: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if ". ." in args or "./ ./" in args or ". /" in args:
        results.append(ValidationResult(
            rule_id="DL3045",
            message="Copying entire context may include unnecessary files",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
            suggestion="Use .dockerignore and copy specific files/directories",
        ))

    if "--chown" not in args:
        results.append(ValidationResult(
            rule_id="DL3046",
            message="Consider using --chown to set file ownership",
            severity=ValidationSeverity.HINT,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
        ))

    return results


def check_run_consolidation(
    run_commands: List[Tuple[int, str]], file_path: str
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if len(run_commands) > 5:
        results.append(ValidationResult(
            rule_id="DL3059",
            message=f"Multiple RUN instructions ({len(run_commands)}) could be consolidated",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            suggestion="Combine related RUN commands with && to reduce layers",
        ))

    return results


def build_report(
    files: List[str],
    results: List[ValidationResult],
    start_time: float,
    context: ValidationContext,
) -> ValidationReport:
    duration_ms = int((time.time() - start_time) * 1000)

    error_count = sum(1 for r in results if r.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
    info_count = sum(1 for r in results if r.severity in (ValidationSeverity.INFO, ValidationSeverity.HINT))

    score = 100.0
    score -= error_count * 10
    score -= warning_count * 3
    score -= info_count * 1
    score = max(0.0, score)

    file_summaries = []
    results_by_file: Dict[str, List[ValidationResult]] = {}
    for result in results:
        fp = result.file_path or "(no file)"
        if fp not in results_by_file:
            results_by_file[fp] = []
        results_by_file[fp].append(result)

    for fp in files:
        file_results = results_by_file.get(fp, [])
        file_errors = sum(1 for r in file_results if r.severity == ValidationSeverity.ERROR)
        file_warnings = sum(1 for r in file_results if r.severity == ValidationSeverity.WARNING)
        file_info = sum(1 for r in file_results if r.severity in (ValidationSeverity.INFO, ValidationSeverity.HINT))
        file_summaries.append(FileValidationSummary(
            file_path=fp,
            error_count=file_errors,
            warning_count=file_warnings,
            info_count=file_info,
            passed=file_errors == 0,
        ))

    report_id = hashlib.sha256(str(results).encode()).hexdigest()[:16]

    return ValidationReport(
        id=f"dockerfile-validation-{report_id}",
        title="Dockerfile Validation",
        validator="DockerfileValidator",
        results=results,
        file_summaries=file_summaries,
        total_files=len(files),
        total_errors=error_count,
        total_warnings=warning_count,
        total_info=info_count,
        passed=error_count == 0,
        score=score,
        duration_ms=duration_ms,
        context=context,
    )
