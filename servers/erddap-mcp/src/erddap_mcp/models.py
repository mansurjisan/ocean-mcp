"""Pydantic models for ERDDAP MCP server."""

from enum import Enum


class Protocol(str, Enum):
    GRIDDAP = "griddap"
    TABLEDAP = "tabledap"


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
