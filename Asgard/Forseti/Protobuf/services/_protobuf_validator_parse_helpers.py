"""
Protobuf Validator Parse Helpers.

Parsing functions for ProtobufValidatorService.
"""

import re
from typing import Any, Optional

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufEnum,
    ProtobufField,
    ProtobufMessage,
    ProtobufService,
    ProtobufSyntaxVersion,
)

SYNTAX_PATTERN = re.compile(r'syntax\s*=\s*["\']([^"\']+)["\'];')
PACKAGE_PATTERN = re.compile(r'package\s+([\w.]+)\s*;')
IMPORT_PATTERN = re.compile(r'import\s+(public\s+)?["\']([^"\']+)["\'];')
OPTION_PATTERN = re.compile(r'option\s+([\w.]+)\s*=\s*([^;]+);')
MESSAGE_PATTERN = re.compile(r'message\s+(\w+)\s*\{')
ENUM_PATTERN = re.compile(r'enum\s+(\w+)\s*\{')
SERVICE_PATTERN = re.compile(r'service\s+(\w+)\s*\{')
FIELD_PATTERN = re.compile(r'(optional|required|repeated)?\s*([\w.]+)\s+(\w+)\s*=\s*(\d+)(?:\s*\[(.*?)\])?;')
MAP_FIELD_PATTERN = re.compile(r'map\s*<\s*([\w.]+)\s*,\s*([\w.]+)\s*>\s+(\w+)\s*=\s*(\d+)\s*;')
ONEOF_PATTERN = re.compile(r'oneof\s+(\w+)\s*\{')
RESERVED_PATTERN = re.compile(r'reserved\s+([^;]+);')
ENUM_VALUE_PATTERN = re.compile(r'(\w+)\s*=\s*(-?\d+)(?:\s*\[.*?\])?;')
RPC_PATTERN = re.compile(r'rpc\s+(\w+)\s*\(\s*(stream\s+)?(\w+)\s*\)\s*returns\s*\(\s*(stream\s+)?(\w+)\s*\)')


def remove_comments(content: str) -> str:
    """Remove single-line and multi-line comments."""
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    return content


def parse_syntax(content: str) -> Optional[ProtobufSyntaxVersion]:
    """Parse the syntax declaration."""
    match = SYNTAX_PATTERN.search(content)
    if match:
        syntax_str = match.group(1)
        if syntax_str == "proto2":
            return ProtobufSyntaxVersion.PROTO2
        elif syntax_str == "proto3":
            return ProtobufSyntaxVersion.PROTO3
    return None


def parse_package(content: str) -> Optional[str]:
    """Parse the package declaration."""
    match = PACKAGE_PATTERN.search(content)
    return match.group(1) if match else None


def parse_imports(content: str) -> tuple[list[str], list[str]]:
    """Parse import statements."""
    imports = []
    public_imports = []
    for match in IMPORT_PATTERN.finditer(content):
        is_public = match.group(1) is not None
        import_path = match.group(2)
        if is_public:
            public_imports.append(import_path)
        else:
            imports.append(import_path)
    return imports, public_imports


def parse_options(content: str) -> dict[str, Any]:
    """Parse file-level options."""
    options: dict[str, Any] = {}
    lines = content.split('\n')
    brace_depth = 0
    for line in lines:
        brace_depth += line.count('{') - line.count('}')
        if brace_depth == 0:
            match = OPTION_PATTERN.search(line)
            if match:
                name = match.group(1)
                value = match.group(2).strip()
                if value.startswith('"') and value.endswith('"'):
                    options[name] = value[1:-1]
                elif value.lower() == 'true':
                    options[name] = True
                elif value.lower() == 'false':
                    options[name] = False
                elif value.isdigit():
                    options[name] = int(value)
                else:
                    options[name] = value
    return options


def extract_block(content: str, start: int) -> Optional[str]:
    """Extract content between matching braces."""
    brace_count = 1
    end = start
    while end < len(content) and brace_count > 0:
        if content[end] == '{':
            brace_count += 1
        elif content[end] == '}':
            brace_count -= 1
        end += 1
    if brace_count == 0:
        return content[start:end-1]
    return None


def parse_reserved(reserved_str: str) -> tuple[list[str], list[int], list[tuple[int, int]]]:
    """Parse reserved declaration."""
    names: list[str] = []
    numbers: list[int] = []
    ranges: list[tuple[int, int]] = []
    parts = [p.strip() for p in reserved_str.split(',')]
    for part in parts:
        if part.startswith('"') and part.endswith('"'):
            names.append(part[1:-1])
        elif ' to ' in part:
            range_parts = part.split(' to ')
            start = int(range_parts[0])
            end_str = range_parts[1]
            end = 536870911 if end_str == 'max' else int(end_str)
            ranges.append((start, end))
        elif part.isdigit():
            numbers.append(int(part))
    return names, numbers, ranges


def parse_field_match(match: re.Match, syntax_version: ProtobufSyntaxVersion, oneof_group: Optional[str] = None) -> ProtobufField:
    """Parse a field from a regex match."""
    label = match.group(1)
    field_type = match.group(2)
    name = match.group(3)
    number = int(match.group(4))
    options_str = match.group(5) if len(match.groups()) > 4 else None
    options = {}
    default_value = None
    if options_str:
        for opt_match in re.finditer(r'(\w+)\s*=\s*([^,\]]+)', options_str):
            opt_name = opt_match.group(1)
            opt_value = opt_match.group(2).strip()
            if opt_name == 'default':
                default_value = opt_value
            else:
                options[opt_name] = opt_value
    return ProtobufField(name=name, number=number, type=field_type, label=label, default_value=default_value, options=options if options else None, oneof_group=oneof_group)


def parse_enum_block(name: str, block_content: str) -> ProtobufEnum:
    """Parse an enum block."""
    values: dict[str, int] = {}
    allow_alias = 'allow_alias' in block_content and 'true' in block_content
    reserved_names: list[str] = []
    reserved_numbers: list[int] = []
    for match in RESERVED_PATTERN.finditer(block_content):
        names, numbers, _ = parse_reserved(match.group(1))
        reserved_names.extend(names)
        reserved_numbers.extend(numbers)
    for match in ENUM_VALUE_PATTERN.finditer(block_content):
        values[match.group(1)] = int(match.group(2))
    return ProtobufEnum(name=name, values=values, allow_alias=allow_alias, reserved_names=reserved_names, reserved_numbers=reserved_numbers)


def parse_service_block(name: str, block_content: str) -> ProtobufService:
    """Parse a service block."""
    rpcs: dict[str, dict[str, str]] = {}
    for match in RPC_PATTERN.finditer(block_content):
        rpc_name = match.group(1)
        input_stream = match.group(2) is not None
        input_type = match.group(3)
        output_stream = match.group(4) is not None
        output_type = match.group(5)
        rpcs[rpc_name] = {"input": input_type, "output": output_type, "input_stream": str(input_stream).lower(), "output_stream": str(output_stream).lower()}
    return ProtobufService(name=name, rpcs=rpcs)


def parse_message_block(name: str, block_content: str, syntax_version: ProtobufSyntaxVersion) -> ProtobufMessage:
    """Parse a message block."""
    fields = []
    nested_messages = []
    nested_enums = []
    oneofs: dict[str, list[str]] = {}
    reserved_names: list[str] = []
    reserved_numbers: list[int] = []
    reserved_ranges: list[tuple[int, int]] = []
    for match in MESSAGE_PATTERN.finditer(block_content):
        nested_name = match.group(1)
        start = match.end()
        nested_block = extract_block(block_content, start)
        if nested_block:
            nested_messages.append(parse_message_block(nested_name, nested_block, syntax_version))
    for match in ENUM_PATTERN.finditer(block_content):
        enum_name = match.group(1)
        start = match.end()
        enum_block = extract_block(block_content, start)
        if enum_block:
            nested_enums.append(parse_enum_block(enum_name, enum_block))
    for match in ONEOF_PATTERN.finditer(block_content):
        oneof_name = match.group(1)
        start = match.end()
        oneof_block = extract_block(block_content, start)
        if oneof_block:
            oneof_fields = []
            for field_match in FIELD_PATTERN.finditer(oneof_block):
                oneof_fields.append(field_match.group(3))
                fields.append(parse_field_match(field_match, syntax_version, oneof_name))
            oneofs[oneof_name] = oneof_fields
    for match in RESERVED_PATTERN.finditer(block_content):
        names, numbers, ranges = parse_reserved(match.group(1))
        reserved_names.extend(names)
        reserved_numbers.extend(numbers)
        reserved_ranges.extend(ranges)
    for match in FIELD_PATTERN.finditer(block_content):
        field = parse_field_match(match, syntax_version)
        if field.oneof_group is None:
            fields.append(field)
    for match in MAP_FIELD_PATTERN.finditer(block_content):
        fields.append(ProtobufField(name=match.group(3), number=int(match.group(4)), type="map", label="repeated", map_key_type=match.group(1), map_value_type=match.group(2)))
    return ProtobufMessage(name=name, fields=fields, nested_messages=nested_messages, nested_enums=nested_enums, oneofs=oneofs, reserved_names=reserved_names, reserved_numbers=reserved_numbers, reserved_ranges=reserved_ranges)
