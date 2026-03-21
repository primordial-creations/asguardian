"""
Protobuf Compatibility Checker Service.

Checks backward compatibility between Protocol Buffer schema versions.
"""

import json
import time
from pathlib import Path
from typing import Optional

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    BreakingChange,
    BreakingChangeType,
    CompatibilityLevel,
    ProtobufCompatibilityResult,
    ProtobufConfig,
    ProtobufSchema,
)
from Asgard.Forseti.Protobuf.services.protobuf_validator_service import ProtobufValidatorService
from Asgard.Forseti.Protobuf.services._protobuf_compatibility_service_helpers import (
    check_enums_compatibility,
    check_message_compatibility,
    check_services_compatibility,
)
from Asgard.Forseti.Protobuf.services._protobuf_compatibility_report_helpers import (
    generate_markdown_report,
    generate_text_report,
)


class ProtobufCompatibilityService:
    """
    Service for checking Protocol Buffer schema compatibility.

    Checks backward compatibility between schema versions and reports
    breaking changes.

    Usage:
        service = ProtobufCompatibilityService()
        result = service.check("old.proto", "new.proto")
        if not result.is_compatible:
            for change in result.breaking_changes:
                print(f"Breaking: {change.message}")
    """

    def __init__(self, config: Optional[ProtobufConfig] = None):
        self.config = config or ProtobufConfig()
        self.validator = ProtobufValidatorService(self.config)

    def check(self, old_proto_path: str | Path, new_proto_path: str | Path) -> ProtobufCompatibilityResult:
        start_time = time.time()
        breaking_changes: list[BreakingChange] = []
        warnings: list[BreakingChange] = []
        added_messages: list[str] = []
        removed_messages: list[str] = []
        modified_messages: list[str] = []
        old_result = self.validator.validate_file(old_proto_path)
        new_result = self.validator.validate_file(new_proto_path)
        if not old_result.parsed_schema:
            return ProtobufCompatibilityResult(
                is_compatible=False,
                compatibility_level=CompatibilityLevel.NONE,
                source_file=str(old_proto_path),
                target_file=str(new_proto_path),
                breaking_changes=[BreakingChange(
                    change_type=BreakingChangeType.REMOVED_MESSAGE,
                    path="/",
                    message=f"Failed to parse old schema: {old_result.errors[0].message if old_result.errors else 'Unknown error'}",
                )],
                check_time_ms=(time.time() - start_time) * 1000,
            )
        if not new_result.parsed_schema:
            return ProtobufCompatibilityResult(
                is_compatible=False,
                compatibility_level=CompatibilityLevel.NONE,
                source_file=str(old_proto_path),
                target_file=str(new_proto_path),
                breaking_changes=[BreakingChange(
                    change_type=BreakingChangeType.REMOVED_MESSAGE,
                    path="/",
                    message=f"Failed to parse new schema: {new_result.errors[0].message if new_result.errors else 'Unknown error'}",
                )],
                check_time_ms=(time.time() - start_time) * 1000,
            )
        old_schema = old_result.parsed_schema
        new_schema = new_result.parsed_schema
        old_message_names = {msg.name for msg in old_schema.messages}
        new_message_names = {msg.name for msg in new_schema.messages}
        for msg_name in old_message_names - new_message_names:
            removed_messages.append(msg_name)
            breaking_changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_MESSAGE,
                path=f"message {msg_name}",
                message=f"Message '{msg_name}' was removed",
                old_value=msg_name,
                severity="error",
                mitigation="Keep the message or mark it as deprecated first",
            ))
        for msg_name in new_message_names - old_message_names:
            added_messages.append(msg_name)
        old_messages_map = {msg.name: msg for msg in old_schema.messages}
        new_messages_map = {msg.name: msg for msg in new_schema.messages}
        for msg_name in old_message_names & new_message_names:
            msg_changes = check_message_compatibility(old_messages_map[msg_name], new_messages_map[msg_name])
            if msg_changes:
                modified_messages.append(msg_name)
                for change in msg_changes:
                    if change.severity == "error":
                        breaking_changes.append(change)
                    else:
                        warnings.append(change)
        for change in check_enums_compatibility(old_schema.enums, new_schema.enums):
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)
        for change in check_services_compatibility(old_schema.services, new_schema.services):
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)
        if not breaking_changes:
            compatibility_level = CompatibilityLevel.FULL
        elif not removed_messages:
            compatibility_level = CompatibilityLevel.BACKWARD
        else:
            compatibility_level = CompatibilityLevel.NONE
        return ProtobufCompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            compatibility_level=compatibility_level,
            source_file=str(old_proto_path),
            target_file=str(new_proto_path),
            breaking_changes=breaking_changes,
            warnings=warnings,
            added_messages=added_messages,
            removed_messages=removed_messages,
            modified_messages=modified_messages,
            check_time_ms=(time.time() - start_time) * 1000,
        )

    def check_schemas(self, old_schema: ProtobufSchema, new_schema: ProtobufSchema) -> ProtobufCompatibilityResult:
        start_time = time.time()
        breaking_changes: list[BreakingChange] = []
        warnings: list[BreakingChange] = []
        added_messages: list[str] = []
        removed_messages: list[str] = []
        modified_messages: list[str] = []
        old_message_names = {msg.name for msg in old_schema.messages}
        new_message_names = {msg.name for msg in new_schema.messages}
        for msg_name in old_message_names - new_message_names:
            removed_messages.append(msg_name)
            breaking_changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_MESSAGE,
                path=f"message {msg_name}",
                message=f"Message '{msg_name}' was removed",
                old_value=msg_name,
                severity="error",
            ))
        for msg_name in new_message_names - old_message_names:
            added_messages.append(msg_name)
        old_messages_map = {msg.name: msg for msg in old_schema.messages}
        new_messages_map = {msg.name: msg for msg in new_schema.messages}
        for msg_name in old_message_names & new_message_names:
            msg_changes = check_message_compatibility(old_messages_map[msg_name], new_messages_map[msg_name])
            if msg_changes:
                modified_messages.append(msg_name)
                for change in msg_changes:
                    if change.severity == "error":
                        breaking_changes.append(change)
                    else:
                        warnings.append(change)
        if not breaking_changes:
            compatibility_level = CompatibilityLevel.FULL
        elif not removed_messages:
            compatibility_level = CompatibilityLevel.BACKWARD
        else:
            compatibility_level = CompatibilityLevel.NONE
        return ProtobufCompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            compatibility_level=compatibility_level,
            source_file=old_schema.file_path,
            target_file=new_schema.file_path,
            breaking_changes=breaking_changes,
            warnings=warnings,
            added_messages=added_messages,
            removed_messages=removed_messages,
            modified_messages=modified_messages,
            check_time_ms=(time.time() - start_time) * 1000,
        )

    def generate_report(self, result: ProtobufCompatibilityResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
