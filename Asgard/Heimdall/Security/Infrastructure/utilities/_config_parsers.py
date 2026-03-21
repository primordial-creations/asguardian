"""
Heimdall Config Parser Helpers

Parse functions for reading different configuration file formats.
"""

from typing import Any, Dict


def parse_env_file(content: str) -> Dict[str, str]:
    """
    Parse a .env file content into a dictionary.

    Args:
        content: Content of the .env file

    Returns:
        Dictionary of environment variable key-value pairs
    """
    env_vars: Dict[str, str] = {}
    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        if key:
            env_vars[key] = value

    return env_vars


def parse_yaml_simple(content: str) -> Dict[str, Any]:
    """
    Simple YAML parser for basic key-value extraction.
    Does not handle complex YAML structures - use for security scanning only.

    Args:
        content: YAML content to parse

    Returns:
        Dictionary of extracted key-value pairs
    """
    result: Dict[str, Any] = {}
    lines = content.split("\n")

    for line in lines:
        line_stripped = line.strip()

        if not line_stripped or line_stripped.startswith("#"):
            continue

        if ":" not in line_stripped:
            continue

        key, _, value = line_stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        if key:
            result[key] = value

    return result


def parse_properties_file(content: str) -> Dict[str, str]:
    """
    Parse a .properties file (Java-style) into a dictionary.

    Args:
        content: Content of the properties file

    Returns:
        Dictionary of property key-value pairs
    """
    properties: Dict[str, str] = {}
    lines = content.split("\n")
    current_value = ""
    current_key = ""

    for line in lines:
        if line.rstrip().endswith("\\"):
            if current_key:
                current_value += line.rstrip()[:-1]
            else:
                key_part, _, value_part = line.rstrip()[:-1].partition("=")
                current_key = key_part.strip()
                current_value = value_part.strip()
            continue

        if current_key:
            current_value += line.strip()
            properties[current_key] = current_value
            current_key = ""
            current_value = ""
            continue

        line = line.strip()

        if not line or line.startswith("#") or line.startswith("!"):
            continue

        if "=" in line:
            key, _, value = line.partition("=")
        elif ":" in line:
            key, _, value = line.partition(":")
        else:
            continue

        key = key.strip()
        value = value.strip()

        if key:
            properties[key] = value

    return properties


def parse_ini_file(content: str) -> Dict[str, Dict[str, str]]:
    """
    Parse an INI file into a nested dictionary.

    Args:
        content: Content of the INI file

    Returns:
        Dictionary with sections as keys and dictionaries of values
    """
    result: Dict[str, Dict[str, str]] = {}
    current_section = "DEFAULT"
    result[current_section] = {}

    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#") or line.startswith(";"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if current_section not in result:
                result[current_section] = {}
            continue

        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            if key:
                result[current_section][key] = value

    return result
