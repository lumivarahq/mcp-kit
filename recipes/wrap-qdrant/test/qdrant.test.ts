import { buildServer } from "@mcp-kit/core";
import { connectInMemory } from "@mcp-kit/core/testing";
import { afterEach, describe, expect, it } from "vitest";

import { QdrantClient } from "../src/client.js";
import { setQdrantClient, tools } from "../src/qdrant.tools.js";
import type { FetchLike } from "../src/rest-client.js";

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

/** A fake Qdrant covering create / upsert / search and a 404. */
const fakeFetch: FetchLike = async (url, init) => {
  const method = init?.method ?? "GET";
  if (method === "PUT" && /\/collections\/[^/]+$/.test(url)) {
    return json({ result: true, status: "ok" });
  }
  if (method === "PUT" && url.includes("/points")) {
    return json({ result: { operation_id: 1, status: "completed" }, status: "ok" });
  }
  if (method === "POST" && url.includes("/points/search")) {
    return json({
      result: [
        { id: 1, score: 0.98, payload: { title: "intro" } },
        { id: 2, score: 0.81, payload: { title: "next" } },
      ],
      status: "ok",
    });
  }
  return json({ status: { error: "Not found" } }, 404);
};

afterEach(() => setQdrantClient(undefined));

async function withServer<T>(fn: (client: Awaited<ReturnType<typeof connectInMemory>>["client"]) => Promise<T>): Promise<T> {
  setQdrantClient(new QdrantClient({ fetchImpl: fakeFetch }));
  const { client, close } = await connectInMemory(buildServer({ name: "qdrant-test", version: "0", tools }));
  try {
    return await fn(client);
  } finally {
    await close();
  }
}

describe("Qdrant server", () => {
  it("create_collection reports created", async () => {
    await withServer(async (client) => {
      const res = await client.callTool({
        name: "create_collection",
        arguments: { collection: "docs", size: 3, distance: "Cosine" },
      });
      const sc = res.structuredContent as { created: boolean; size: number; distance: string };
      expect(sc.created).toBe(true);
      expect(sc.size).toBe(3);
      expect(sc.distance).toBe("Cosine");
    });
  });

  it("upsert_points reports the count and status", async () => {
    await withServer(async (client) => {
      const res = await client.callTool({
        name: "upsert_points",
        arguments: { collection: "docs", points: [{ id: 1, vector: [0.1, 0.2, 0.3], payload: { title: "intro" } }] },
      });
      const sc = res.structuredContent as { upserted: number; status: string };
      expect(sc.upserted).toBe(1);
      expect(sc.status).toBe("completed");
    });
  });

  it("search returns scored matches ordered by score", async () => {
    await withServer(async (client) => {
      const res = await client.callTool({
        name: "search",
        arguments: { collection: "docs", vector: [0.1, 0.2, 0.3], limit: 5 },
      });
      const sc = res.structuredContent as { count: number; matches: { id: number; score: number }[] };
      expect(sc.count).toBe(2);
      expect(sc.matches[0]?.score).toBeGreaterThan(sc.matches[1]!.score);
    });
  });

  it("surfaces a 404 as a structured not_found error", async () => {
    setQdrantClient(new QdrantClient({ fetchImpl: async () => json({ status: { error: "Not found" } }, 404) }));
    const { client, close } = await connectInMemory(buildServer({ name: "qdrant-test", version: "0", tools }));
    try {
      const res = await client.callTool({ name: "search", arguments: { collection: "missing", vector: [0.1] } });
      expect(res.isError).toBe(true);
      const sc = res.structuredContent as unknown as { error: { code: string } };
      expect(sc.error.code).toBe("not_found");
    } finally {
      await close();
    }
  });
});
