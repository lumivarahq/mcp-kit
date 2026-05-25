"""Qdrant tools — the Python twin of ``recipes/wrap-qdrant/src/qdrant.tools.ts``.

Three tools over the Qdrant REST API. The client is built lazily from the
environment (``QDRANT_URL``, optional ``QDRANT_API_KEY``); tests inject one via
:func:`set_qdrant_client`.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.types import ToolAnnotations

from mcp_kit_starter import ToolExample, ToolSpec, define_tool

from .client import QdrantClient

_injected: QdrantClient | None = None


def set_qdrant_client(client: QdrantClient | None) -> None:
    """Override the client (tests)."""
    global _injected
    _injected = client


def _qdrant() -> QdrantClient:
    global _injected
    if _injected is None:
        _injected = QdrantClient(
            base_url=os.environ.get("QDRANT_URL") or "http://127.0.0.1:6333",
            api_key=os.environ.get("QDRANT_API_KEY"),
        )
    return _injected


# Handlers are named functions with a `-> dict[str, Any]` return annotation, so
# FastMCP builds an output model from the registered output_schema (a bare lambda
# leaves output_model unset and breaks structured output). Mirrors the starter.
def _create_collection_handler(collection: str, size: int, distance: str = "Cosine") -> dict[str, Any]:
    return _qdrant().create_collection(collection, size, distance)


def _upsert_points_handler(
    collection: str, points: list[dict[str, Any]], wait: bool = True
) -> dict[str, Any]:
    return _qdrant().upsert_points(collection, points, wait)


def _search_handler(
    collection: str,
    vector: list[float],
    limit: int = 10,
    with_payload: bool = True,
    filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matches = _qdrant().search(
        collection, vector, limit=limit, with_payload=with_payload, filter=filter
    )
    return {"collection": collection, "count": len(matches), "matches": matches}


_create_collection = define_tool(
    ToolSpec(
        name="create_collection",
        title="Create a Qdrant collection",
        description=(
            "Create a Qdrant collection configured for a fixed vector size and distance metric. "
            "Use this once, before upserting points, when the collection does not yet exist — you "
            "must know your embedding model's dimensionality (e.g. 1536) and which metric to compare "
            "with (Cosine for most normalised text embeddings). "
            "It does not embed text, does not upsert any vectors, and is not how you add data — call "
            "upsert_points for that. "
            "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. "
            'Example: create_collection({ "collection": "docs", "size": 1536, "distance": "Cosine" }).'
        ),
        input_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": 'Name of the collection to create, e.g. "docs".'},
                "size": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Vector dimensionality — must match your embedding model (e.g. 1536).",
                },
                "distance": {
                    "type": "string",
                    "enum": ["Cosine", "Dot", "Euclid", "Manhattan"],
                    "default": "Cosine",
                    "description": 'Distance metric for similarity. Defaults to "Cosine".',
                },
            },
            "required": ["collection", "size"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string"},
                "size": {"type": "number"},
                "distance": {"type": "string"},
                "created": {"type": "boolean"},
            },
            "required": ["collection", "size", "distance", "created"],
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=True),
        examples=[
            ToolExample(
                description="A collection for OpenAI small embeddings.",
                arguments={"collection": "docs", "size": 1536, "distance": "Cosine"},
            )
        ],
        handler=_create_collection_handler,
        text_summary=lambda p: f'Collection "{p["collection"]}" (size {p["size"]}, {p["distance"]}) created={p["created"]}.',
    )
)


_upsert_points = define_tool(
    ToolSpec(
        name="upsert_points",
        title="Upsert points into a collection",
        description=(
            "Insert or update points (id + vector + optional payload) in a Qdrant collection. "
            "Use this to add or overwrite already-embedded data: you supply each point's vector and "
            "any payload metadata, and Qdrant indexes them for search. By default it waits until the "
            "write is applied so a following search sees it. "
            "It does not generate embeddings for you (embed text first, on your side) and does not "
            "create the collection — call create_collection once beforehand. "
            "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. "
            'Example: upsert_points({ "collection": "docs", "points": [{ "id": 1, "vector": [0.1, 0.2] }] }).'
        ),
        input_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Target collection that already exists."},
                "points": {
                    "type": "array",
                    "minItems": 1,
                    "description": "Points to insert/update; each is an id, a vector, and optional payload.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "anyOf": [{"type": "integer"}, {"type": "string"}],
                                "description": "Point id: an unsigned integer or a UUID string.",
                            },
                            "vector": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 1,
                                "description": "Embedding vector; length must equal the collection size.",
                            },
                            "payload": {"type": "object", "description": "Optional JSON metadata."},
                        },
                        "required": ["id", "vector"],
                    },
                },
                "wait": {
                    "type": "boolean",
                    "default": True,
                    "description": "Wait for the write to be applied before returning. Defaults to true.",
                },
            },
            "required": ["collection", "points"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string"},
                "upserted": {"type": "number"},
                "status": {"type": "string"},
            },
            "required": ["collection", "upserted", "status"],
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=True),
        examples=[
            ToolExample(
                description="Upsert one point with payload.",
                arguments={"collection": "docs", "points": [{"id": 1, "vector": [0.1, 0.2, 0.3], "payload": {"title": "intro"}}]},
            )
        ],
        handler=_upsert_points_handler,
        text_summary=lambda p: f'Upserted {p["upserted"]} point(s) into "{p["collection"]}" ({p["status"]}).',
    )
)


_search = define_tool(
    ToolSpec(
        name="search",
        title="Vector search a collection",
        description=(
            "Search a Qdrant collection for the points nearest a query vector. "
            "Use this when you already have a query embedding and want the most similar stored points, "
            "optionally narrowed by a Qdrant payload filter — it returns each match's id, similarity "
            "score, and payload. "
            "It does not embed your query text (embed it first, with the same model used for upsert) and "
            "does not return the stored vectors themselves. "
            "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. "
            'Example: search({ "collection": "docs", "vector": [0.1, 0.2, 0.3], "limit": 5 }).'
        ),
        input_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Collection to search."},
                "vector": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 1,
                    "description": "Query embedding; length must equal the collection size.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 10,
                    "description": "Maximum matches to return. Defaults to 10.",
                },
                "with_payload": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include each match's stored payload. Defaults to true.",
                },
                "filter": {
                    "type": "object",
                    "description": 'Optional Qdrant filter, e.g. {"must": [{"key": "lang", "match": {"value": "en"}}]}.',
                },
            },
            "required": ["collection", "vector"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "collection": {"type": "string"},
                "count": {"type": "number"},
                "matches": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["collection", "count", "matches"],
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        examples=[
            ToolExample(
                description="Top-5 nearest neighbours.",
                arguments={"collection": "docs", "vector": [0.1, 0.2, 0.3], "limit": 5},
            )
        ],
        handler=_search_handler,
        text_summary=lambda p: f'{p["count"]} match(es) in "{p["collection"]}".',
    )
)


tools: list[ToolSpec] = [_create_collection, _upsert_points, _search]

__all__ = ["tools", "set_qdrant_client"]
