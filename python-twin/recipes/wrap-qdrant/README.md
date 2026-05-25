# wrap-qdrant (Python twin)

The Python twin of [`recipes/wrap-qdrant`](../../../recipes/wrap-qdrant): the
same three tools (`create_collection`, `upsert_points`, `search`) over the
Qdrant REST API, built on the `mcp-kit-starter` base. Same shape as the
TypeScript recipe, so the pattern reads identically in either language.

> **For curated memory, use [Mem0](https://github.com/mem0ai/mem0) on top of
> this — not raw Qdrant.** Raw Qdrant is the right primitive for search over
> embeddings you manage; agent *memory* (dedup, fact extraction, update/forget)
> is what Mem0 adds, and Mem0 can use Qdrant underneath. See the
> [TypeScript recipe's README](../../../recipes/wrap-qdrant/README.md#-for-curated-memory-use-mem0-on-top-of-this--not-raw-qdrant).

## Run it

From `python-twin/` (the installed `mcp-kit-starter` env):

```bash
cd python-twin
.venv/bin/pip install -e ".[dev]"   # if not already

MCP_TRANSPORT=stdio QDRANT_URL=http://127.0.0.1:6333 \
  .venv/bin/python -m qdrant_recipe.cli
# Secured instances: also set QDRANT_API_KEY=…
```

(Run with `recipes/wrap-qdrant/` on `PYTHONPATH`, or from this directory.)
`httpx` — the only HTTP dependency — ships with `mcp`, so there is nothing extra
to install. Embeddings are produced on your side; these tools store and query
them.

## Tests

Run the whole Python suite from `python-twin/` (testpaths includes `recipes`):

```bash
cd python-twin && .venv/bin/python -m pytest
```

Hermetic: a fake Qdrant (`httpx.MockTransport`) covers create / upsert / search
and a structured `not_found`, driven through a real in-memory MCP client.
