/**
 * Qdrant tools — wrap a vector database's REST API as MCP tools.
 *
 * Three tools over the Qdrant REST API. The client is built lazily from the
 * environment (`QDRANT_URL`, optional `QDRANT_API_KEY`) so importing this module
 * for the lint never touches the network; tests inject a client via
 * {@link setQdrantClient}.
 */
import { type AnyToolSpec, defineTool, toolResult } from "@mcp-kit/core";
import { z } from "zod";

import { QdrantClient } from "./client.js";

let injected: QdrantClient | undefined;

/** Override the client (tests). */
export function setQdrantClient(client: QdrantClient | undefined): void {
  injected = client;
}

function qdrant(): QdrantClient {
  if (!injected) {
    const options: ConstructorParameters<typeof QdrantClient>[0] = {};
    if (process.env.QDRANT_URL) options.baseUrl = process.env.QDRANT_URL;
    if (process.env.QDRANT_API_KEY) options.apiKey = process.env.QDRANT_API_KEY;
    injected = new QdrantClient(options);
  }
  return injected;
}

const createCollection = defineTool({
  name: "create_collection",
  title: "Create a Qdrant collection",
  description:
    "Create a Qdrant collection configured for a fixed vector size and distance metric. " +
    "Use this once, before upserting points, when the collection does not yet exist — you must know your embedding " +
    "model's dimensionality (e.g. 1536 for text-embedding-3-small) and which metric to compare with (Cosine for most " +
    "normalised text embeddings). " +
    "It does not embed text, does not upsert any vectors, and is not how you add data — call upsert_points for that. " +
    "Re-creating an existing collection may replace it, so check first. " +
    "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. " +
    'Example: create_collection({ "collection": "docs", "size": 1536, "distance": "Cosine" }).',
  inputSchema: {
    collection: z.string().min(1).describe('Name of the collection to create, e.g. "docs".'),
    size: z
      .number()
      .int()
      .min(1)
      .describe("Vector dimensionality — must match your embedding model (e.g. 1536)."),
    distance: z
      .enum(["Cosine", "Dot", "Euclid", "Manhattan"])
      .describe('Distance metric for similarity. Defaults to "Cosine".')
      .default("Cosine"),
  },
  outputSchema: {
    collection: z.string().describe("The collection that was created."),
    size: z.number().describe("Configured vector size."),
    distance: z.string().describe("Configured distance metric."),
    created: z.boolean().describe("True if Qdrant reported the collection created."),
  },
  annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: true },
  examples: [
    { description: "A collection for OpenAI small embeddings.", arguments: { collection: "docs", size: 1536, distance: "Cosine" } },
  ],
  handler: async (args) => {
    const result = await qdrant().createCollection(args.collection, args.size, args.distance);
    return toolResult(`Collection "${result.collection}" (size ${result.size}, ${result.distance}) created=${result.created}.`, result);
  },
});

const upsertPoints = defineTool({
  name: "upsert_points",
  title: "Upsert points into a collection",
  description:
    "Insert or update points (id + vector + optional payload) in a Qdrant collection. " +
    "Use this to add or overwrite already-embedded data: you supply each point's vector and any payload metadata, and " +
    "Qdrant indexes them for search. By default it waits until the write is applied so a following search sees it. " +
    "It does not generate embeddings for you (embed text first, on your side) and does not create the collection — " +
    "call create_collection once beforehand. " +
    "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. " +
    'Example: upsert_points({ "collection": "docs", "points": [{ "id": 1, "vector": [0.1, 0.2], "payload": { "title": "intro" } }] }).',
  inputSchema: {
    collection: z.string().min(1).describe("Target collection that already exists (see create_collection)."),
    points: z
      .array(
        z.object({
          id: z.union([z.number(), z.string()]).describe("Point id: an unsigned integer or a UUID string."),
          vector: z.array(z.number()).min(1).describe("The embedding vector; length must equal the collection size."),
          payload: z.record(z.unknown()).optional().describe("Optional JSON metadata stored with the point."),
        }),
      )
      .min(1)
      .describe("The points to insert or update; each is an id, a vector, and optional payload."),
    wait: z
      .boolean()
      .describe("Wait for the write to be applied before returning. Defaults to true.")
      .default(true),
  },
  outputSchema: {
    collection: z.string().describe("The collection written to."),
    upserted: z.number().describe("Number of points sent."),
    status: z.string().describe('Qdrant operation status, e.g. "completed" or "acknowledged".'),
  },
  annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: true },
  examples: [
    {
      description: "Upsert one point with payload.",
      arguments: { collection: "docs", points: [{ id: 1, vector: [0.1, 0.2, 0.3], payload: { title: "intro" } }] },
    },
  ],
  handler: async (args) => {
    const result = await qdrant().upsertPoints(args.collection, args.points, args.wait);
    return toolResult(`Upserted ${result.upserted} point(s) into "${result.collection}" (${result.status}).`, result);
  },
});

const search = defineTool({
  name: "search",
  title: "Vector search a collection",
  description:
    "Search a Qdrant collection for the points nearest a query vector. " +
    "Use this when you already have a query embedding and want the most similar stored points, optionally narrowed by " +
    "a Qdrant payload filter — it returns each match's id, similarity score, and payload. " +
    "It does not embed your query text (embed it first, with the same model used for upsert) and does not return the " +
    "stored vectors themselves, only ids/scores/payloads. " +
    "Part of the wrap-qdrant server (a Qdrant vector-DB wrapper), not a primitive. " +
    'Example: search({ "collection": "docs", "vector": [0.1, 0.2, 0.3], "limit": 5 }).',
  inputSchema: {
    collection: z.string().min(1).describe("Collection to search."),
    vector: z.array(z.number()).min(1).describe("Query embedding; length must equal the collection size."),
    limit: z.number().int().min(1).max(1000).describe("Maximum matches to return. Defaults to 10.").default(10),
    with_payload: z
      .boolean()
      .describe("Include each match's stored payload in the result. Defaults to true.")
      .default(true),
    filter: z
      .record(z.unknown())
      .optional()
      .describe('Optional Qdrant filter object, e.g. { "must": [{ "key": "lang", "match": { "value": "en" } }] }.'),
  },
  outputSchema: {
    collection: z.string().describe("The collection searched."),
    count: z.number().describe("Number of matches returned."),
    matches: z
      .array(z.object({ id: z.union([z.number(), z.string()]), score: z.number(), payload: z.record(z.unknown()).nullable() }))
      .describe("Matches ordered by descending similarity score."),
  },
  annotations: { readOnlyHint: true, openWorldHint: true },
  examples: [
    { description: "Top-5 nearest neighbours.", arguments: { collection: "docs", vector: [0.1, 0.2, 0.3], limit: 5 } },
  ],
  handler: async (args) => {
    const opts: { limit?: number; withPayload?: boolean; filter?: Record<string, unknown> } = {
      limit: args.limit,
      withPayload: args.with_payload,
    };
    if (args.filter !== undefined) opts.filter = args.filter;
    const matches = await qdrant().search(args.collection, args.vector, opts);
    return toolResult(`${matches.length} match(es) in "${args.collection}".`, {
      collection: args.collection,
      count: matches.length,
      matches,
    });
  },
});

export const tools: AnyToolSpec[] = [createCollection, upsertPoints, search];
