from __future__ import annotations
import asyncio
import argparse
import base64
from dataclasses import dataclass
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from dotenv import find_dotenv, load_dotenv
from appwrite.client import Client
from appwrite.input_file import InputFile
from appwrite.enums.browser import Browser
from appwrite.services.tables_db import TablesDB
from appwrite.services.users import Users
from appwrite.services.teams import Teams
from appwrite.services.storage import Storage
from appwrite.services.functions import Functions
from appwrite.services.locale import Locale
from appwrite.services.avatars import Avatars
from appwrite.services.messaging import Messaging
from appwrite.services.sites import Sites
from appwrite.exception import AppwriteException
from mcp.server.lowlevel.helper_types import ReadResourceContents
from .operator import Operator
from .service import Service
from .tool_manager import ToolManager

SERVER_VERSION = "0.4.1"


@dataclass(frozen=True)
class AppwriteConfig:
    project_id: str
    api_key: str
    endpoint: str


def _log_startup(message: str) -> None:
    print(f"[appwrite-mcp] {message}", file=sys.stderr, flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Appwrite MCP Server")
    return parser.parse_args()


def load_appwrite_config() -> AppwriteConfig:
    cwd_dotenv = Path.cwd() / ".env"
    if cwd_dotenv.exists():
        load_dotenv(dotenv_path=cwd_dotenv)
    else:
        discovered_dotenv = find_dotenv(usecwd=True)
        if discovered_dotenv:
            load_dotenv(dotenv_path=discovered_dotenv)

    project_id = os.getenv("APPWRITE_PROJECT_ID")
    api_key = os.getenv("APPWRITE_API_KEY")
    endpoint = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")

    if not project_id or not api_key:
        raise ValueError(
            "APPWRITE_PROJECT_ID and APPWRITE_API_KEY must be set in environment variables"
        )

    return AppwriteConfig(project_id=project_id, api_key=api_key, endpoint=endpoint)


def build_client(config: AppwriteConfig | None = None) -> Client:
    config = config or load_appwrite_config()
    client = Client()
    client.set_endpoint(config.endpoint)
    client.set_project(config.project_id)
    client.set_key(config.api_key)
    client.add_header("x-sdk-name", "mcp")
    return client


def register_services(client: Client) -> ToolManager:
    tools_manager = ToolManager()
    for service in [
        Service(TablesDB(client), "tables_db"),
        Service(Users(client), "users"),
        Service(Teams(client), "teams"),
        Service(Storage(client), "storage"),
        Service(Functions(client), "functions"),
        Service(Messaging(client), "messaging"),
        Service(Locale(client), "locale"),
        Service(Avatars(client), "avatars"),
        Service(Sites(client), "sites"),
    ]:
        tools_manager.register_service(service)

    return tools_manager


def _validate_service(service: Service) -> None:
    match service.service_name:
        case "tables_db" | "users" | "teams" | "functions" | "sites":
            service.service.list()
        case "storage":
            service.service.list_buckets()
        case "messaging":
            service.service.list_messages()
        case "locale":
            service.service.list_codes()
        case "avatars":
            service.service.get_browser(Browser.GOOGLE_CHROME.value, width=1, height=1)
        case _:
            raise ValueError(
                f"No startup validation probe configured for service '{service.service_name}'"
            )


def validate_services(tools_manager: ToolManager) -> None:
    if not tools_manager.services:
        return

    service = tools_manager.services[0]
    _log_startup(f"Validating startup access via {service.service_name}")

    try:
        _validate_service(service)
    except AppwriteException as exc:
        raise RuntimeError(
            "Appwrite startup validation failed during the minimal startup probe. "
            "Check your endpoint, project ID, API key, and required scopes.\n"
            f"- {service.service_name}: {_format_appwrite_error(exc)}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "Appwrite startup validation failed during the minimal startup probe. "
            "Check your endpoint, project ID, API key, and required scopes.\n"
            f"- {service.service_name}: {exc}"
        ) from exc

    _log_startup(f"Validated startup access via {service.service_name}")


def _unwrap_optional_type(py_type: Any) -> Any:
    origin = get_origin(py_type)
    if origin not in (UnionType, Union):
        return py_type

    args = [arg for arg in get_args(py_type) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return py_type


def _coerce_enum(enum_type: type[Enum], value: Any, param_name: str) -> Any:
    if isinstance(value, enum_type):
        return value.value

    try:
        return enum_type(value).value
    except ValueError as exc:
        valid_values = ", ".join(str(member.value) for member in enum_type)
        raise ValueError(
            f"Invalid value for '{param_name}'. Expected one of: {valid_values}"
        ) from exc


def _coerce_input_file(value: Any, param_name: str) -> InputFile:
    if isinstance(value, InputFile):
        return value

    if isinstance(value, str):
        return InputFile.from_path(value)

    if not isinstance(value, Mapping):
        raise ValueError(
            f"Invalid value for '{param_name}'. Provide a file path string or an object with `path` or `filename` and `content`."
        )

    path = value.get("path")
    if path:
        return InputFile.from_path(str(path))

    filename = value.get("filename")
    content = value.get("content")
    if filename and content is not None:
        encoding = str(value.get("encoding", "utf-8")).lower()
        if encoding == "base64":
            try:
                data = base64.b64decode(content)
            except Exception as exc:
                raise ValueError(f"Invalid base64 content for '{param_name}'.") from exc
        elif encoding == "utf-8":
            data = str(content).encode("utf-8")
        else:
            raise ValueError(
                f"Invalid encoding for '{param_name}'. Expected 'utf-8' or 'base64'."
            )

        return InputFile.from_bytes(data, str(filename), value.get("mime_type"))

    raise ValueError(
        f"Invalid value for '{param_name}'. Provide `path`, or both `filename` and `content`."
    )


def _coerce_argument(param_name: str, value: Any, param_type: Any) -> Any:
    if value is None:
        return value

    param_type = _unwrap_optional_type(param_type)
    origin = get_origin(param_type)
    args = get_args(param_type)

    if param_type is InputFile:
        return _coerce_input_file(value, param_name)

    if isinstance(param_type, type) and issubclass(param_type, Enum):
        return _coerce_enum(param_type, value, param_name)

    if origin is list and isinstance(value, list) and args:
        return [_coerce_argument(param_name, item, args[0]) for item in value]

    if origin is dict and isinstance(value, dict) and len(args) >= 2:
        return {
            key: _coerce_argument(param_name, item, args[1])
            for key, item in value.items()
        }

    return value


def _to_snake_case(value: str) -> str:
    normalized = value.lstrip("$")
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace(" ", "_")
    normalized = normalized.replace(".", "_")
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.lower().strip("_")


def _expected_argument_names(tool_info: dict) -> set[str]:
    parameter_names = set(tool_info.get("parameter_types", {}).keys())
    if parameter_names:
        return parameter_names

    input_schema = (
        tool_info.get("definition").inputSchema if tool_info.get("definition") else None
    )
    properties = (
        input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
    )
    return set(properties.keys()) if isinstance(properties, dict) else set()


def _normalize_argument_key(
    key: str, expected_names: set[str], normalized_arguments: dict[str, Any]
) -> str:
    if key in expected_names:
        return key

    candidate_key = _to_snake_case(key)
    if candidate_key in expected_names:
        return candidate_key

    if candidate_key == "id":
        id_candidates = [
            name
            for name in expected_names
            if name.endswith("_id") and name not in normalized_arguments
        ]
        if len(id_candidates) == 1:
            return id_candidates[0]

    return key


def _normalize_argument_keys(
    tool_info: dict, arguments: dict[str, Any]
) -> dict[str, Any]:
    expected_names = _expected_argument_names(tool_info)
    if not expected_names:
        return dict(arguments)

    normalized_arguments: dict[str, Any] = {}
    argument_sources: dict[str, str] = {}

    for key, value in arguments.items():
        target_key = _normalize_argument_key(key, expected_names, normalized_arguments)

        existing_source = argument_sources.get(target_key)
        if existing_source and existing_source != key:
            existing_value = normalized_arguments[target_key]
            if existing_value != value:
                raise ValueError(
                    f"Conflicting values provided for '{target_key}' via '{existing_source}' and '{key}'."
                )
            continue

        normalized_arguments[target_key] = value
        argument_sources[target_key] = key

    return normalized_arguments


def _validate_argument_keys(
    tool_name: str, tool_info: dict, arguments: dict[str, Any]
) -> None:
    expected_names = _expected_argument_names(tool_info)
    if not expected_names:
        return

    unexpected_names = sorted(name for name in arguments if name not in expected_names)
    if not unexpected_names:
        return

    hints: list[str] = []
    for name in unexpected_names:
        normalized_name = _to_snake_case(name)
        if normalized_name in expected_names:
            hints.append(f"{name} -> {normalized_name}")
            continue

        if normalized_name == "id":
            id_candidates = [
                expected for expected in expected_names if expected.endswith("_id")
            ]
            if len(id_candidates) == 1:
                hints.append(f"{name} -> {id_candidates[0]}")

    hint_text = f" Suggestions: {', '.join(hints)}." if hints else ""
    allowed_preview = ", ".join(sorted(expected_names))
    raise ValueError(
        f"Unsupported arguments for {tool_name}: {', '.join(unexpected_names)}. "
        f"Allowed arguments: {allowed_preview}.{hint_text}"
    )


def _prepare_arguments(tool_info: dict, arguments: dict[str, Any]) -> dict[str, Any]:
    prepared_arguments = _normalize_argument_keys(tool_info, arguments)
    tool_name = (
        tool_info.get("definition").name if tool_info.get("definition") else "tool"
    )
    _validate_argument_keys(tool_name, tool_info, prepared_arguments)
    for param_name, param_type in tool_info.get("parameter_types", {}).items():
        if param_name not in prepared_arguments:
            continue
        prepared_arguments[param_name] = _coerce_argument(
            param_name, prepared_arguments[param_name], param_type
        )

    return prepared_arguments


def execute_registered_tool(
    tools_manager: ToolManager,
    name: str,
    arguments: dict[str, Any] | None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    tool_info = tools_manager.get_tool(name)
    if not tool_info:
        raise ValueError(f"Tool {name} not found")

    prepared_arguments = _prepare_arguments(tool_info, arguments or {})
    bound_method = tool_info["function"]

    try:
        result = bound_method(**prepared_arguments)
    except AppwriteException as exc:
        raise RuntimeError(_format_appwrite_error(exc)) from exc

    return _format_tool_result(name, result, prepared_arguments)


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _serialize_result(result: Any) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False, default=_json_default)


def _guess_mime_type(data: bytes, tool_name: str, arguments: dict[str, Any]) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x1f\x8b"):
        return "application/gzip"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"
    if tool_name.startswith("avatars_"):
        return "image/png"
    if tool_name == "storage_get_file_preview":
        output = arguments.get("output")
        if isinstance(output, Enum):
            output = output.value
        preview_mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        if output in preview_mime_types:
            return preview_mime_types[output]
        return "image/png"
    return "application/octet-stream"


def _format_binary_result(
    tool_name: str, data: bytes, arguments: dict[str, Any]
) -> list[types.ImageContent | types.EmbeddedResource]:
    mime_type = _guess_mime_type(data, tool_name, arguments)
    encoded = base64.b64encode(data).decode("ascii")
    if mime_type.startswith("image/"):
        return [types.ImageContent(type="image", data=encoded, mimeType=mime_type)]

    return [
        types.EmbeddedResource(
            type="resource",
            resource=types.BlobResourceContents(
                uri=f"appwrite://tool/{tool_name}",
                blob=encoded,
                mimeType=mime_type,
            ),
        )
    ]


def _format_tool_result(
    tool_name: str, result: Any, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if hasattr(result, "to_dict") and callable(result.to_dict):
        result = result.to_dict()

    if isinstance(result, bytes):
        return _format_binary_result(tool_name, result, arguments)

    if isinstance(result, (dict, list, tuple, str, int, float, bool)) or result is None:
        return [types.TextContent(type="text", text=_serialize_result(result))]

    return [types.TextContent(type="text", text=str(result))]


def _format_appwrite_error(exc: AppwriteException) -> str:
    details = []
    if getattr(exc, "code", None):
        details.append(f"code={exc.code}")
    if getattr(exc, "type", None):
        details.append(f"type={exc.type}")
    detail_text = f" ({', '.join(details)})" if details else ""
    return f"Appwrite request failed{detail_text}: {exc}"


async def serve(operator: Operator) -> Server:
    instructions = (
        "Appwrite workflow: use appwrite_search_tools first, then appwrite_call_tool. "
        "Mutating hidden tools require confirm_write=true. "
        "Large results are stored as resources; read the URI returned by the tool."
    )

    server = Server("Appwrite MCP Server", instructions=instructions)

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return operator.get_public_tools()

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        if operator.has_public_tool(name):
            return operator.execute_public_tool(name, arguments)

        raise ValueError(f"Tool {name} not found")

    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        return operator.list_resources()

    @server.list_resource_templates()
    async def handle_list_resource_templates() -> list[types.ResourceTemplate]:
        return operator.list_resource_templates()

    @server.read_resource()
    async def handle_read_resource(uri) -> list[ReadResourceContents]:
        return operator.read_resource(str(uri))

    return server


async def _run():
    parse_args()
    _log_startup("Loading Appwrite configuration")
    config = load_appwrite_config()
    client = build_client(config)
    _log_startup(f"Using Appwrite endpoint: {config.endpoint}")
    _log_startup("Registering Appwrite services")
    tools_manager = register_services(client)
    _log_startup("Starting Appwrite service validation")
    validate_services(tools_manager)
    _log_startup("Building Appwrite operator surface")
    operator = Operator(
        tools_manager,
        lambda tool_name, tool_arguments: execute_registered_tool(
            tools_manager,
            tool_name,
            tool_arguments,
        ),
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        server = await serve(operator)
        _log_startup("MCP transport: stdio")
        _log_startup("Appwrite MCP server ready")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="appwrite",
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(_run())
