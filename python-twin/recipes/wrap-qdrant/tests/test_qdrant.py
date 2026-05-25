"""In-process client <-> server tests for the Qdrant recipe.

A fake Qdrant (httpx.MockTransport) covers create / upsert / search and a 404,
driven through a real ClientSession over the SDK's in-memory transport.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from qdrant_recipe.client import QdrantClient
from qdrant_recipe.server import build_server
from qdrant_recipe.tools import set_qdrant_client


def _handler(request: httpx.Request) -> httpx.Response:
    method = request.method
    path = request.url.path
    if method == "PUT" and re.fullmatch(r"/collections/[^/]+", path):
        return httpx.Response(200, json={"result": True, "status": "ok"})
    if method == "PUT" and path.endswith("/points"):
        return httpx.Response(200, json={"result": {"operation_id": 1, "status": "completed"}, "status": "ok"})
    if method == "POST" and path.endswith("/points/search"):
        return httpx.Response(
            200,
            json={
                "result": [
                    {"id": 1, "score": 0.98, "payload": {"title": "intro"}},
                    {"id": 2, "score": 0.81, "payload": {"title": "next"}},
                ],
                "status": "ok",
            },
        )
    return httpx.Response(404, json={"status": {"error": "Not found"}})


@pytest.fixture
def fake_client() -> Iterator[None]:
    transport = httpx.MockTransport(_handler)
    set_qdrant_client(QdrantClient(http=httpx.Client(transport=transport, base_url="http://qdrant.test")))
    try:
        yield
    finally:
        set_qdrant_client(None)


@pytest.mark.anyio
async def test_create_collection_reports_created(fake_client: None) -> None:
    async with create_connected_server_and_client_session(build_server()) as client:
        res = await client.call_tool(
            "create_collection", {"collection": "docs", "size": 3, "distance": "Cosine"}
        )
        assert not res.isError
        assert res.structuredContent["created"] is True
        assert res.structuredContent["size"] == 3


@pytest.mark.anyio
async def test_upsert_points_reports_count(fake_client: None) -> None:
    async with create_connected_server_and_client_session(build_server()) as client:
        res = await client.call_tool(
            "upsert_points",
            {"collection": "docs", "points": [{"id": 1, "vector": [0.1, 0.2, 0.3], "payload": {"title": "intro"}}]},
        )
        assert not res.isError
        assert res.structuredContent["upserted"] == 1
        assert res.structuredContent["status"] == "completed"


@pytest.mark.anyio
async def test_search_returns_ordered_matches(fake_client: None) -> None:
    async with create_connected_server_and_client_session(build_server()) as client:
        res = await client.call_tool(
            "search", {"collection": "docs", "vector": [0.1, 0.2, 0.3], "limit": 5}
        )
        assert not res.isError
        sc = res.structuredContent
        assert sc["count"] == 2
        assert sc["matches"][0]["score"] > sc["matches"][1]["score"]


@pytest.mark.anyio
async def test_404_becomes_structured_not_found() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(404, json={"status": {"error": "no"}}))
    set_qdrant_client(QdrantClient(http=httpx.Client(transport=transport, base_url="http://qdrant.test")))
    try:
        async with create_connected_server_and_client_session(build_server()) as client:
            res = await client.call_tool("search", {"collection": "missing", "vector": [0.1]})
            assert res.isError is True
            assert res.structuredContent["error"]["code"] == "not_found"
    finally:
        set_qdrant_client(None)
