#!/usr/bin/env node
/**
 * Qdrant MCP server entry point.
 *
 *   MCP_TRANSPORT=stdio QDRANT_URL=http://127.0.0.1:6333 node dist/cli.js
 *   QDRANT_API_KEY=... MCP_TRANSPORT=http node dist/cli.js
 *
 * `QDRANT_URL` and `QDRANT_API_KEY` are read from the environment — they are
 * never tool arguments.
 */
import { serveFromEnv } from "@mcp-kit/core";

import { tools } from "./qdrant.tools.js";

serveFromEnv({
  name: "mcp-recipe-qdrant",
  version: "0.1.0",
  instructions:
    "Wraps the Qdrant vector-DB REST API: create a collection, upsert points, and run vector search. Embeddings are " +
    "produced on your side; these tools store and query them. Set QDRANT_URL (and QDRANT_API_KEY if your instance " +
    "requires it) in the environment.",
  tools,
}).catch((err: unknown) => {
  console.error("[mcp] fatal:", err);
  process.exit(1);
});
