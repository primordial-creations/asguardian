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
            # Try to parse as YAML (which also handles JSON)
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            # Try JSON as fallback
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

        # Validate basic structure
        if not isinstance(data, dict):
            raise ValueError("Specification must be a dictionary")

        if "asyncapi" not in data:
            raise ValueError("Missing required field: asyncapi")

        if "info" not in data:
            raise ValueError("Missing required field: info")

        # Parse info
        info_data = data.get("info", {})
        info = AsyncAPIInfo(
            title=info_data.get("title", "Untitled"),
            version=info_data.get("version", "1.0.0"),
            description=info_data.get("description"),
            terms_of_service=info_data.get("termsOfService"),
            contact=info_data.get("contact"),
            license=info_data.get("license"),
        )

        # Parse servers
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

        # Resolve references if configured
        channels_data = data.get("channels", {})
        if self.config.resolve_refs:
            channels_data = self._resolve_refs(channels_data, data)

        # Create spec
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

        channels = []
        for channel_name, channel_data in self._parsed_spec.channels.items():
            if not isinstance(channel_data, dict):
                continue

            # Parse subscribe operation
            subscribe = None
            if "subscribe" in channel_data:
                subscribe = self._parse_operation(channel_data["subscribe"])

            # Parse publish operation
            publish = None
            if "publish" in channel_data:
                publish = self._parse_operation(channel_data["publish"])

            channel = Channel(
                name=channel_name,
                description=channel_data.get("description"),
                subscribe=subscribe,
                publish=publish,
                parameters=channel_data.get("parameters"),
                bindings=channel_data.get("bindings"),
                servers=channel_data.get("servers"),
            )
            channels.append(channel)

        return channels

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

        messages = []

        # Get messages from channels
        for channel_data in self._parsed_spec.channels.values():
            if not isinstance(channel_data, dict):
                continue

            for op_type in ["subscribe", "publish"]:
                if op_type in channel_data:
                    op_data = channel_data[op_type]
                    if "message" in op_data:
                        msg_data = op_data["message"]
                        if isinstance(msg_data, list):
                            for msg in msg_data:
                                messages.append(self._parse_message(msg))
                        elif isinstance(msg_data, dict):
                            messages.append(self._parse_message(msg_data))

        # Get messages from components
        if self._parsed_spec.components and "messages" in self._parsed_spec.components:
            for msg_data in self._parsed_spec.components["messages"].values():
                messages.append(self._parse_message(msg_data))

        return messages

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

        # Count protocols
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

    def _parse_operation(self, op_data: dict[str, Any]) -> OperationInfo:
        """Parse an operation from channel data."""
        message = None
        if "message" in op_data:
            msg_data = op_data["message"]
            if isinstance(msg_data, list):
                message = [self._parse_message(m) for m in msg_data]
            elif isinstance(msg_data, dict):
                message = self._parse_message(msg_data)

        return OperationInfo(
            operation_id=op_data.get("operationId"),
            summary=op_data.get("summary"),
            description=op_data.get("description"),
            tags=op_data.get("tags"),
            external_docs=op_data.get("externalDocs"),
            bindings=op_data.get("bindings"),
            traits=op_data.get("traits"),
            message=message,
            security=op_data.get("security"),
        )

    def _parse_message(self, msg_data: dict[str, Any]) -> MessageInfo:
        """Parse a message definition."""
        return MessageInfo(
            name=msg_data.get("name"),
            title=msg_data.get("title"),
            summary=msg_data.get("summary"),
            description=msg_data.get("description"),
            content_type=msg_data.get("contentType"),
            payload=msg_data.get("payload"),
            headers=msg_data.get("headers"),
            correlation_id=msg_data.get("correlationId"),
            tags=msg_data.get("tags"),
            bindings=msg_data.get("bindings"),
            examples=msg_data.get("examples"),
            traits=msg_data.get("traits"),
        )

    def _resolve_refs(
        self,
        data: Any,
        root: dict[str, Any],
        visited: Optional[set] = None
    ) -> Any:
        """
        Resolve $ref references in the specification.

        Args:
            data: Data to resolve references in.
            root: Root specification for reference resolution.
            visited: Set of visited paths to prevent circular references.

        Returns:
            Data with resolved references.
        """
        if visited is None:
            visited = set()

        if isinstance(data, dict):
            if "$ref" in data:
                ref_path = data["$ref"]
                if ref_path in visited:
                    return data  # Prevent circular references
                visited.add(ref_path)

                resolved = self._get_ref(ref_path, root)
                if resolved is not None:
                    return self._resolve_refs(resolved, root, visited)
                return data

            return {
                key: self._resolve_refs(value, root, visited)
                for key, value in data.items()
            }

        elif isinstance(data, list):
            return [self._resolve_refs(item, root, visited) for item in data]

        return data

    def _get_ref(self, ref_path: str, root: dict[str, Any]) -> Optional[Any]:
        """
        Get the value at a $ref path.

        Args:
            ref_path: Reference path (e.g., "#/components/messages/UserMessage").
            root: Root specification.

        Returns:
            Referenced value or None if not found.
        """
        if not ref_path.startswith("#/"):
            return None

        parts = ref_path[2:].split("/")
        current = root

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current
