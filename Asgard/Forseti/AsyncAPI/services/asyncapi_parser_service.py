"""
AsyncAPI Parser Service.

Parses AsyncAPI specifications from files or strings and provides
structured access to the specification contents.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.AsyncAPI.models.asyncapi_models import (
    AsyncAPIConfig,
    AsyncAPIInfo,
    AsyncAPIReport,
    AsyncAPISpec,
    AsyncAPIValidationResult,
    AsyncAPIVersion,
    Channel,
    MessageInfo,
    OperationInfo,
    ServerInfo,
)
from Asgard.Forseti.AsyncAPI.services._asyncapi_parser_helpers import (
    get_channels_from_spec,
    get_messages_from_spec,
    resolve_refs,
)


class AsyncAPIParserService:
    """
    Service for parsing AsyncAPI specifications.

    Parses specifications from files or strings and provides structured
    access to channels, messages, and operations.

    Usage:
        parser = AsyncAPIParserService()
        spec = parser.parse("asyncapi.yaml")
        print(f"Title: {spec.info.title}")
        for channel in parser.get_channels():
            print(f"Channel: {channel.name}")
    """

    def __init__(self, config: Optional[AsyncAPIConfig] = None):
        """
        Initialize the parser service.

        Args:
            config: Optional configuration for parsing behavior.
        """
        self.config = config or AsyncAPIConfig()
        self._parsed_spec: Optional[AsyncAPISpec] = None
        self._raw_data: Optional[dict[str, Any]] = None

    def parse(self, spec_path: str | Path) -> AsyncAPISpec:
        """
        Parse an AsyncAPI specification file.

        Args:
            spec_path: Path to the AsyncAPI specification file.

        Returns:
            Parsed AsyncAPISpec object.

        Raises:
            FileNotFoundError: If the specification file doesn't exist.
            ValueError: If the file cannot be parsed.
        """
        spec_path = Path(spec_path)

        if not spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_path}")

        content = spec_path.read_text(encoding="utf-8")
        return self.parse_string(content)

    def parse_string(self, content: str) -> AsyncAPISpec:
        """
        Parse an AsyncAPI specification from a string.

        Args:
            content: YAML or JSON content of the specification.

        Returns:
            Parsed AsyncAPISpec object.

        Raises:
            ValueError: If the content cannot be parsed.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse specification: {e}")

        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any]) -> AsyncAPISpec:
        """
        Parse an AsyncAPI specification from a dictionary.

        Args:
            data: Specification data as a dictionary.

        Returns:
            Parsed AsyncAPISpec object.

        Raises:
            ValueError: If the data is not a valid AsyncAPI specification.
        """
        self._raw_data = data

        if not isinstance(data, dict):
            raise ValueError("Specification must be a dictionary")

        if "asyncapi" not in data:
            raise ValueError("Missing required field: asyncapi")

        if "info" not in data:
            raise ValueError("Missing required field: info")

        info_data = data.get("info", {})
        info = AsyncAPIInfo(
            title=info_data.get("title", "Untitled"),
            version=info_data.get("version", "1.0.0"),
            description=info_data.get("description"),
            terms_of_service=info_data.get("termsOfService"),
            contact=info_data.get("contact"),
            license=info_data.get("license"),
        )

        servers = None
        if "servers" in data:
            servers = {}
            for server_name, server_data in data["servers"].items():
                servers[server_name] = ServerInfo(
                    url=server_data.get("url", ""),
                    protocol=server_data.get("protocol", ""),
                    protocol_version=server_data.get("protocolVersion"),
                    description=server_data.get("description"),
                    variables=server_data.get("variables"),
                    security=server_data.get("security"),
                    bindings=server_data.get("bindings"),
                )

        channels_data = data.get("channels", {})
        if self.config.resolve_refs:
            channels_data = resolve_refs(channels_data, data)

        self._parsed_spec = AsyncAPISpec(
            asyncapi=data.get("asyncapi", "2.6.0"),
            id=data.get("id"),
            info=info,
            servers=servers,
            channels=channels_data,
            components=data.get("components"),
            tags=data.get("tags"),
            external_docs=data.get("externalDocs"),
            default_content_type=data.get("defaultContentType"),
        )

        return self._parsed_spec

    def get_channels(self) -> list[Channel]:
        """
        Get all channels from the parsed specification.

        Returns:
            List of Channel objects.

        Raises:
            ValueError: If no specification has been parsed.
        """
        if self._parsed_spec is None:
            raise ValueError("No specification has been parsed. Call parse() first.")

        return get_channels_from_spec(self._parsed_spec.channels)

    def get_messages(self) -> list[MessageInfo]:
        """
        Get all messages from the parsed specification.

        Returns:
            List of MessageInfo objects.

        Raises:
            ValueError: If no specification has been parsed.
        """
        if self._parsed_spec is None:
            raise ValueError("No specification has been parsed. Call parse() first.")

        return get_messages_from_spec(
            self._parsed_spec.channels,
            self._parsed_spec.components,
        )

    def get_servers(self) -> dict[str, ServerInfo]:
        """
        Get all servers from the parsed specification.

        Returns:
            Dictionary of server name to ServerInfo.

        Raises:
            ValueError: If no specification has been parsed.
        """
        if self._parsed_spec is None:
            raise ValueError("No specification has been parsed. Call parse() first.")

        return self._parsed_spec.servers or {}

    def generate_report(self) -> AsyncAPIReport:
        """
        Generate a comprehensive report of the parsed specification.

        Returns:
            AsyncAPIReport with detailed analysis.

        Raises:
            ValueError: If no specification has been parsed.
        """
        if self._parsed_spec is None:
            raise ValueError("No specification has been parsed. Call parse() first.")

        channels = self.get_channels()
        messages = self.get_messages()

        protocol_summary: dict[str, int] = {}
        if self._parsed_spec.servers:
            for server in self._parsed_spec.servers.values():
                protocol = server.protocol
                protocol_summary[protocol] = protocol_summary.get(protocol, 0) + 1

        return AsyncAPIReport(
            validation_result=AsyncAPIValidationResult(
                is_valid=True,
                asyncapi_version=self._parsed_spec.version,
            ),
            spec=self._parsed_spec,
            channels=channels,
            message_count=len(messages),
            protocol_summary=protocol_summary,
        )
