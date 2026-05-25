"""Build the Qdrant recipe server: identity + tool registry.

Mirrors ``mcp_kit_starter.server.create_starter_server`` but registers this
recipe's tools. Reused by ``cli.py`` and the tests.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_kit_starter import HttpConfig, register_tools

from .tools import tools

SERVER_NAME = "mcp-recipe-qdrant"

_INSTRUCTIONS = (
    "Wraps the Qdrant vector-DB REST API: create a collection, upsert points, and run vector "
    "search. Embeddings are produced on your side; these tools store and query them. Set QDRANT_URL "
    "(and QDRANT_API_KEY if your instance requires it) in the environment."
)


def build_server(http: HttpConfig | None = None) -> FastMCP:
    """Construct a fresh server with the Qdrant recipe tools registered."""
    kwargs: dict[str, object] = {"instructions": _INSTRUCTIONS}
    if http is not None:
        kwargs.update(
            host=http.host,
            port=http.port,
            streamable_http_path=http.path,
            stateless_http=http.stateless,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=http.dns_rebinding_protection,
                allowed_hosts=http.allowed_hosts,
                allowed_origins=http.allowed_origins,
            ),
        )

    server = FastMCP(SERVER_NAME, **kwargs)
    register_tools(server, tools)
    return server
