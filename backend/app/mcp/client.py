import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings


def _server_environment(server_name: str) -> dict[str, str]:
    inherited_keys = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE")
    environment = {key: os.environ[key] for key in inherited_keys if key in os.environ}
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"

    if server_name == "search":
        environment["TAVILY_API_KEY"] = settings.tavily_api_key or ""
    elif server_name == "gmail":
        environment["GMAIL_CREDENTIALS_PATH"] = str(settings.gmail_credentials_path)
        environment["GMAIL_TOKEN_PATH"] = str(settings.gmail_token_path)
    elif server_name == "mongodb":
        environment["MONGODB_DATA_URI"] = settings.mongodb_data_uri or ""
        environment["MONGODB_DATA_DATABASE"] = settings.mongodb_data_database
        environment["MONGODB_ALLOWED_COLLECTIONS"] = settings.mongodb_allowed_collections
    else:
        raise ValueError(f"Unknown MCP server: {server_name}")

    return environment


@asynccontextmanager
async def open_mcp_session(server_name: str) -> AsyncIterator[ClientSession]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", f"app.mcp.{server_name}"],
        env=_server_environment(server_name),
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session
