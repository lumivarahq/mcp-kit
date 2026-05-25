"""A thin typed client for the Qdrant REST API, built on httpx.

Python twin of ``recipes/wrap-qdrant/src/client.ts``. The base URL and API key
come from the *environment* (a transport concern), never from a tool argument;
Qdrant authenticates with an ``api-key`` header. HTTP failures are mapped to the
kit's structured :class:`~mcp_kit_starter.errors.McpToolError`.

``httpx`` ships as a dependency of ``mcp`` (the base's only runtime dep), so no
extra install is needed. Tests inject an ``httpx.Client`` backed by an
``httpx.MockTransport`` for fully offline runs.
"""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

import httpx

from mcp_kit_starter import McpToolError
from mcp_kit_starter.errors import ErrorCode

#: Qdrant's local default. Override with ``QDRANT_URL``.
DEFAULT_BASE_URL = "http://127.0.0.1:6333"

Distance = Literal["Cosine", "Dot", "Euclid", "Manhattan"]


def _status_to_code(status: int) -> tuple[ErrorCode, bool]:
    if status in (401, 403):
        return ("unauthorized", False)
    if status == 404:
        return ("not_found", False)
    if status == 429:
        return ("rate_limited", True)
    if status >= 500:
        return ("upstream_unavailable", True)
    return ("upstream_error", False)


class QdrantClient:
    """Minimal Qdrant REST client over httpx."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        *,
        http: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        if http is not None:
            self._http = http
        else:
            headers = {"User-Agent": "mcp-kit-recipe-qdrant"}
            if api_key:
                headers["api-key"] = api_key
            self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        try:
            response = self._http.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise McpToolError(
                "timeout", f"Qdrant {method} {path} timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise McpToolError(
                "upstream_unavailable",
                f"Qdrant {method} {path} failed: {exc}",
                retryable=True,
            ) from exc

        if response.is_success:
            return response.json() if response.content else {}

        code, retryable = _status_to_code(response.status_code)
        detail = response.text[:500]
        raise McpToolError(
            code,
            f"Qdrant {method} {path} returned HTTP {response.status_code}.",
            retryable=retryable,
            details=detail or None,
        )

    def create_collection(self, name: str, size: int, distance: Distance) -> dict[str, Any]:
        res = self._request(
            "PUT",
            f"/collections/{quote(name, safe='')}",
            json={"vectors": {"size": size, "distance": distance}},
        )
        return {
            "collection": name,
            "size": size,
            "distance": distance,
            "created": res.get("result") is True,
        }

    def upsert_points(
        self, name: str, points: list[dict[str, Any]], wait: bool = True
    ) -> dict[str, Any]:
        if not points:
            raise McpToolError("invalid_input", "upsert_points needs at least one point.")
        res = self._request(
            "PUT",
            f"/collections/{quote(name, safe='')}/points",
            params={"wait": "true" if wait else "false"},
            json={"points": points},
        )
        result = res.get("result") or {}
        return {
            "collection": name,
            "upserted": len(points),
            "status": result.get("status", "unknown"),
        }

    def search(
        self,
        name: str,
        vector: list[float],
        *,
        limit: int = 10,
        with_payload: bool = True,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"vector": vector, "limit": limit, "with_payload": with_payload}
        if filter is not None:
            body["filter"] = filter
        res = self._request(
            "POST", f"/collections/{quote(name, safe='')}/points/search", json=body
        )
        return [
            {"id": p["id"], "score": p["score"], "payload": p.get("payload")}
            for p in (res.get("result") or [])
        ]
