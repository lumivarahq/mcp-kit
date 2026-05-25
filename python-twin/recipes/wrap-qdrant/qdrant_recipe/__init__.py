"""wrap-qdrant — the Python twin of ``recipes/wrap-qdrant``.

Wraps the Qdrant REST API as MCP tools (create_collection, upsert_points,
search), built on the ``mcp-kit-starter`` base. Importable, or runnable via
``python -m qdrant_recipe.cli``.
"""

from __future__ import annotations

from .client import QdrantClient
from .server import build_server
from .tools import set_qdrant_client, tools

__all__ = ["QdrantClient", "build_server", "tools", "set_qdrant_client"]
