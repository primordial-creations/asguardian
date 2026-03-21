"""
AsyncAPI Parser Helpers.

Helper functions for AsyncAPIParserService.
"""

from typing import Any, Optional

from Asgard.Forseti.AsyncAPI.models.asyncapi_models import (
    Channel,
    MessageInfo,
    OperationInfo,
)


def parse_message(msg_data: dict[str, Any]) -> MessageInfo:
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


def parse_operation(op_data: dict[str, Any]) -> OperationInfo:
    """Parse an operation from channel data."""
    message = None
    if "message" in op_data:
        msg_data = op_data["message"]
        if isinstance(msg_data, list):
            message = [parse_message(m) for m in msg_data]
        elif isinstance(msg_data, dict):
            message = parse_message(msg_data)

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


def get_ref_value(ref_path: str, root: dict[str, Any]) -> Optional[Any]:
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
    current: Any = root

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


def resolve_refs(
    data: Any,
    root: dict[str, Any],
    visited: Optional[set] = None,
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
                return data
            visited.add(ref_path)

            resolved = get_ref_value(ref_path, root)
            if resolved is not None:
                return resolve_refs(resolved, root, visited)
            return data

        return {
            key: resolve_refs(value, root, visited)
            for key, value in data.items()
        }

    elif isinstance(data, list):
        return [resolve_refs(item, root, visited) for item in data]

    return data


def get_channels_from_spec(channels_data: dict[str, Any]) -> list[Channel]:
    """
    Parse all channels from channel data.

    Args:
        channels_data: Channels dict from parsed spec.

    Returns:
        List of Channel objects.
    """
    channels = []
    for channel_name, channel_data in channels_data.items():
        if not isinstance(channel_data, dict):
            continue

        subscribe = None
        if "subscribe" in channel_data:
            subscribe = parse_operation(channel_data["subscribe"])

        publish = None
        if "publish" in channel_data:
            publish = parse_operation(channel_data["publish"])

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


def get_messages_from_spec(
    channels_data: dict[str, Any],
    components: Optional[dict[str, Any]],
) -> list[MessageInfo]:
    """
    Get all messages from channels and components.

    Args:
        channels_data: Channels dict from parsed spec.
        components: Components dict from parsed spec.

    Returns:
        List of MessageInfo objects.
    """
    messages = []

    for channel_data in channels_data.values():
        if not isinstance(channel_data, dict):
            continue

        for op_type in ["subscribe", "publish"]:
            if op_type in channel_data:
                op_data = channel_data[op_type]
                if "message" in op_data:
                    msg_data = op_data["message"]
                    if isinstance(msg_data, list):
                        for msg in msg_data:
                            messages.append(parse_message(msg))
                    elif isinstance(msg_data, dict):
                        messages.append(parse_message(msg_data))

    if components and "messages" in components:
        for msg_data in components["messages"].values():
            messages.append(parse_message(msg_data))

    return messages
