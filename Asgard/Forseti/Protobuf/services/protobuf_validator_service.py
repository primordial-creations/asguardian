"""
Protobuf Specification Validator Service.

Validates Protocol Buffer files against syntax and best practices.
Uses regex-based parsing to avoid requiring external protoc installation.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufConfig,
    ProtobufEnum,
    ProtobufField,
    ProtobufMessage,
    ProtobufSchema,
    ProtobufService,
    ProtobufSyntaxVersion,
    ProtobufValidationError,
    ProtobufValidationResult,
    ValidationSeverity,
)
from Asgard.Forseti.Protobuf.services._protobuf_validator_service_helpers import (
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Forseti.Protobuf.services._protobuf_validator_parse_helpers import (
    extract_block,
    parse_enum_block,
    parse_imports,
    parse_message_block,
    parse_options,
    parse_package,
    parse_service_block,
    parse_syntax,
    remove_comments,
    MESSAGE_PATTERN,
    ENUM_PATTERN,
    SERVICE_PATTERN,
)


class ProtobufValidatorService:
    """
    Service for validating Protocol Buffer specifications.

    Usage:
        service = ProtobufValidatorService()
        result = service.validate("schema.proto")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    SCALAR_TYPES = {
        "double", "float", "int32", "int64", "uint32", "uint64",
        "sint32", "sint64", "fixed32", "fixed64", "sfixed32", "sfixed64",
        "bool", "string", "bytes"
    }
    RESERVED_FIELD_NUMBERS = range(19000, 20000)

    def __init__(self, config: Optional[ProtobufConfig] = None):
        self.config = config or ProtobufConfig()

    def validate(self, proto_path: str | Path) -> ProtobufValidationResult:
        return self.validate_file(proto_path)

    def validate_file(self, proto_path: str | Path) -> ProtobufValidationResult:
        start_time = time.time()
        proto_path = Path(proto_path)
        errors: list[ProtobufValidationError] = []
        if not proto_path.exists():
            errors.append(ProtobufValidationError(path="", message=f"Proto file not found: {proto_path}", severity=ValidationSeverity.ERROR, rule="file-exists"))
            return ProtobufValidationResult(is_valid=False, file_path=str(proto_path), errors=errors, validation_time_ms=(time.time() - start_time) * 1000)
        try:
            content = proto_path.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(ProtobufValidationError(path="", message=f"Failed to read proto file: {str(e)}", severity=ValidationSeverity.ERROR, rule="readable-file"))
            return ProtobufValidationResult(is_valid=False, file_path=str(proto_path), errors=errors, validation_time_ms=(time.time() - start_time) * 1000)
        return self._validate_content(content, str(proto_path), start_time)

    def validate_content(self, content: str) -> ProtobufValidationResult:
        return self._validate_content(content, None, time.time())

    def _validate_content(self, content: str, file_path: Optional[str], start_time: float) -> ProtobufValidationResult:
        errors: list[ProtobufValidationError] = []
        warnings: list[ProtobufValidationError] = []
        info_messages: list[ProtobufValidationError] = []
        cleaned_content = remove_comments(content)
        syntax_version = parse_syntax(cleaned_content)
        if syntax_version is None:
            syntax_version = ProtobufSyntaxVersion.PROTO3
            warnings.append(ProtobufValidationError(path="/", message="No syntax declaration found, defaulting to proto3", severity=ValidationSeverity.WARNING, rule="syntax-declaration"))
        elif syntax_version == ProtobufSyntaxVersion.PROTO2 and not self.config.allow_proto2:
            errors.append(ProtobufValidationError(path="/syntax", message="proto2 syntax is not allowed by configuration", severity=ValidationSeverity.ERROR, rule="proto2-allowed"))
        package = parse_package(cleaned_content)
        if not package and self.config.require_package:
            errors.append(ProtobufValidationError(path="/", message="Package declaration is required", severity=ValidationSeverity.ERROR, rule="package-required"))
        imports, public_imports = parse_imports(cleaned_content)
        options = parse_options(cleaned_content)
        messages = self._parse_messages(cleaned_content, syntax_version)
        enums = self._parse_enums(cleaned_content)
        services = self._parse_services(cleaned_content)
        for msg in messages:
            for err in self._validate_message(msg, syntax_version):
                if err.severity == ValidationSeverity.ERROR:
                    errors.append(err)
                elif err.severity == ValidationSeverity.WARNING:
                    warnings.append(err)
                else:
                    info_messages.append(err)
        for enum in enums:
            for err in self._validate_enum(enum, syntax_version):
                if err.severity == ValidationSeverity.ERROR:
                    errors.append(err)
                elif err.severity == ValidationSeverity.WARNING:
                    warnings.append(err)
                else:
                    info_messages.append(err)
        for service in services:
            for err in self._validate_service(service, messages):
                if err.severity == ValidationSeverity.ERROR:
                    errors.append(err)
                elif err.severity == ValidationSeverity.WARNING:
                    warnings.append(err)
                else:
                    info_messages.append(err)
        if self.config.check_naming_conventions:
            warnings.extend(self._check_naming_conventions(messages, enums, services))
        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]
        schema = ProtobufSchema(syntax=syntax_version, package=package, imports=imports, public_imports=public_imports, messages=messages, enums=enums, services=services, options=options, file_path=file_path)
        return ProtobufValidationResult(
            is_valid=len(errors) == 0, file_path=file_path, syntax_version=syntax_version,
            parsed_schema=schema if len(errors) == 0 else None, errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages, validation_time_ms=(time.time() - start_time) * 1000,
        )

    def _parse_messages(self, content: str, syntax_version: ProtobufSyntaxVersion) -> list[ProtobufMessage]:
        messages = []
        for match in MESSAGE_PATTERN.finditer(content):
            name = match.group(1)
            start = match.end()
            block_content = extract_block(content, start)
            if block_content:
                messages.append(parse_message_block(name, block_content, syntax_version))
        return messages

    def _parse_enums(self, content: str) -> list[ProtobufEnum]:
        enums = []
        for match in ENUM_PATTERN.finditer(content):
            name = match.group(1)
            start = match.end()
            block_content = extract_block(content, start)
            if block_content:
                enums.append(parse_enum_block(name, block_content))
        return enums

    def _parse_services(self, content: str) -> list[ProtobufService]:
        services = []
        for match in SERVICE_PATTERN.finditer(content):
            name = match.group(1)
            start = match.end()
            block_content = extract_block(content, start)
            if block_content:
                services.append(parse_service_block(name, block_content))
        return services

    def _validate_message(self, message: ProtobufMessage, syntax_version: ProtobufSyntaxVersion) -> list[ProtobufValidationError]:
        errors: list[ProtobufValidationError] = []
        base_path = f"message {message.name}"
        field_numbers: dict[int, str] = {}
        for field in message.fields:
            if field.number in field_numbers:
                errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Duplicate field number {field.number} (also used by '{field_numbers[field.number]}')", severity=ValidationSeverity.ERROR, rule="unique-field-numbers"))
            else:
                field_numbers[field.number] = field.name
        if self.config.check_field_numbers:
            for field in message.fields:
                if field.number < 1:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field number must be positive, got {field.number}", severity=ValidationSeverity.ERROR, rule="valid-field-number"))
                elif field.number in self.RESERVED_FIELD_NUMBERS:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field number {field.number} is in reserved range 19000-19999", severity=ValidationSeverity.ERROR, rule="reserved-range"))
                elif field.number > 536870911:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field number {field.number} exceeds maximum (536870911)", severity=ValidationSeverity.ERROR, rule="max-field-number"))
                elif field.number > 15 and field.number <= 2047:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message="Consider using field numbers 1-15 for frequently used fields (better encoding)", severity=ValidationSeverity.INFO, rule="efficient-field-number"))
        if self.config.check_reserved_fields:
            for field in message.fields:
                if field.name in message.reserved_names:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field name '{field.name}' is reserved", severity=ValidationSeverity.ERROR, rule="reserved-name"))
                if field.number in message.reserved_numbers:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field number {field.number} is reserved", severity=ValidationSeverity.ERROR, rule="reserved-number"))
                for start, end in message.reserved_ranges:
                    if start <= field.number <= end:
                        errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message=f"Field number {field.number} is in reserved range {start}-{end}", severity=ValidationSeverity.ERROR, rule="reserved-range"))
        if syntax_version == ProtobufSyntaxVersion.PROTO3:
            for field in message.fields:
                if field.label == "required":
                    errors.append(ProtobufValidationError(path=f"{base_path}.{field.name}", message="'required' label is not allowed in proto3", severity=ValidationSeverity.ERROR, rule="proto3-no-required"))
        for nested in message.nested_messages:
            errors.extend(self._validate_message(nested, syntax_version))
        for nested_enum in message.nested_enums:
            errors.extend(self._validate_enum(nested_enum, syntax_version))
        return errors

    def _validate_enum(self, enum: ProtobufEnum, syntax_version: ProtobufSyntaxVersion) -> list[ProtobufValidationError]:
        errors: list[ProtobufValidationError] = []
        base_path = f"enum {enum.name}"
        if not enum.allow_alias:
            value_numbers: dict[int, str] = {}
            for value_name, value_number in enum.values.items():
                if value_number in value_numbers:
                    errors.append(ProtobufValidationError(path=f"{base_path}.{value_name}", message=f"Duplicate enum value {value_number} (also used by '{value_numbers[value_number]}'). Use allow_alias = true to allow aliases.", severity=ValidationSeverity.ERROR, rule="unique-enum-values"))
                else:
                    value_numbers[value_number] = value_name
        if syntax_version == ProtobufSyntaxVersion.PROTO3 and enum.values:
            if min(enum.values.values()) != 0:
                errors.append(ProtobufValidationError(path=base_path, message="First enum value must be 0 in proto3", severity=ValidationSeverity.ERROR, rule="proto3-enum-zero"))
        for value_name, value_number in enum.values.items():
            if value_name in enum.reserved_names:
                errors.append(ProtobufValidationError(path=f"{base_path}.{value_name}", message=f"Enum value name '{value_name}' is reserved", severity=ValidationSeverity.ERROR, rule="reserved-enum-name"))
            if value_number in enum.reserved_numbers:
                errors.append(ProtobufValidationError(path=f"{base_path}.{value_name}", message=f"Enum value number {value_number} is reserved", severity=ValidationSeverity.ERROR, rule="reserved-enum-number"))
        return errors

    def _validate_service(self, service: ProtobufService, messages: list[ProtobufMessage]) -> list[ProtobufValidationError]:
        errors: list[ProtobufValidationError] = []
        base_path = f"service {service.name}"
        message_names = set()
        for msg in messages:
            message_names.add(msg.name)
            for nested in msg.nested_messages:
                message_names.add(f"{msg.name}.{nested.name}")
        for rpc_name, rpc_def in service.rpcs.items():
            input_type = rpc_def.get("input", "")
            output_type = rpc_def.get("output", "")
            if input_type not in message_names and input_type not in self.SCALAR_TYPES:
                errors.append(ProtobufValidationError(path=f"{base_path}.{rpc_name}", message=f"RPC input type '{input_type}' may not be defined (could be an import)", severity=ValidationSeverity.INFO, rule="rpc-type-exists"))
            if output_type not in message_names and output_type not in self.SCALAR_TYPES:
                errors.append(ProtobufValidationError(path=f"{base_path}.{rpc_name}", message=f"RPC output type '{output_type}' may not be defined (could be an import)", severity=ValidationSeverity.INFO, rule="rpc-type-exists"))
        return errors

    def _check_naming_conventions(self, messages: list[ProtobufMessage], enums: list[ProtobufEnum], services: list[ProtobufService]) -> list[ProtobufValidationError]:
        warnings: list[ProtobufValidationError] = []
        for msg in messages:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', msg.name):
                warnings.append(ProtobufValidationError(path=f"message {msg.name}", message=f"Message name '{msg.name}' should be PascalCase", severity=ValidationSeverity.WARNING, rule="naming-convention"))
            for field in msg.fields:
                if not re.match(r'^[a-z][a-z0-9_]*$', field.name):
                    warnings.append(ProtobufValidationError(path=f"message {msg.name}.{field.name}", message=f"Field name '{field.name}' should be snake_case", severity=ValidationSeverity.WARNING, rule="naming-convention"))
        for enum in enums:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', enum.name):
                warnings.append(ProtobufValidationError(path=f"enum {enum.name}", message=f"Enum name '{enum.name}' should be PascalCase", severity=ValidationSeverity.WARNING, rule="naming-convention"))
            for value_name in enum.values:
                if not re.match(r'^[A-Z][A-Z0-9_]*$', value_name):
                    warnings.append(ProtobufValidationError(path=f"enum {enum.name}.{value_name}", message=f"Enum value '{value_name}' should be SCREAMING_SNAKE_CASE", severity=ValidationSeverity.WARNING, rule="naming-convention"))
        for service in services:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', service.name):
                warnings.append(ProtobufValidationError(path=f"service {service.name}", message=f"Service name '{service.name}' should be PascalCase", severity=ValidationSeverity.WARNING, rule="naming-convention"))
        return warnings

    def generate_report(self, result: ProtobufValidationResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
