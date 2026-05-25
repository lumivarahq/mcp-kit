# Recipe: wrap the Qdrant REST API

Turn a [Qdrant](https://qdrant.tech) instance into MCP tools. This recipe wraps
the vector-DB REST API as three tools so an agent can manage and query a
collection over MCP. It ships in **two languages** — TypeScript here and a
**Python twin** under
[`python-twin/recipes/wrap-qdrant/`](../../python-twin/recipes/wrap-qdrant) —
sharing the same shape, so the pattern is language-agnostic. The TS server
reuses the `wrap-rest-api` error-mapping client (`src/rest-client.ts`, lifted
verbatim).

| Tool | Qdrant endpoint |
| --- | --- |
| `create_collection` | `PUT /collections/{name}` |
| `upsert_points` | `PUT /collections/{name}/points?wait=true` |
| `search` | `POST /collections/{name}/points/search` |

> **Embeddings are produced on your side.** These tools store and query vectors;
> they do not embed text. Embed with your chosen model, then `upsert_points` /
> `search`.

## ⚠️ For *curated memory*, use Mem0 on top of this — not raw Qdrant

Raw Qdrant is the right primitive for **search over embeddings you manage**
(RAG, semantic lookup). It is the **wrong** layer for *agent memory*: dedup,
fact extraction, update/forget, recency, and conflict resolution are exactly
what a memory layer like [**Mem0**](https://github.com/mem0ai/mem0) provides —
and Mem0 can use Qdrant as its vector store underneath. So:

- **Search / RAG over your own corpus** → this recipe (wrap Qdrant directly).
- **Curated, evolving memory for an agent** → run **Mem0 on top of Qdrant**, and
  wrap *Mem0's* API as MCP tools instead. Don't reimplement memory semantics on
  raw `upsert_points`.

## Run it

```bash
docker run -d -p 6333:6333 qdrant/qdrant

pnpm --filter @mcp-kit/recipe-qdrant build
MCP_TRANSPORT=stdio QDRANT_URL=http://127.0.0.1:6333 node dist/cli.js
# Qdrant Cloud / secured instances: also set QDRANT_API_KEY=…
```

`QDRANT_URL` and `QDRANT_API_KEY` are read from the **environment**; the model
passes only data — a collection name, vectors, a filter. Qdrant authenticates
with an `api-key` header, set for you at the client boundary.

## Tests

```bash
pnpm --filter @mcp-kit/recipe-qdrant test
```

Hermetic: a fake Qdrant (injected fetch) covers create / upsert / search and a
structured `not_found`. No Docker, no network.
