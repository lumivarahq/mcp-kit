/**
 * A thin typed client for the Qdrant REST API, built on {@link RestClient}.
 *
 * Qdrant (https://qdrant.tech) exposes a plain JSON REST API. This client maps
 * the three capabilities the recipe needs onto it:
 *   - `PUT  /collections/{name}`                 — create a collection
 *   - `PUT  /collections/{name}/points?wait=…`   — upsert points
 *   - `POST /collections/{name}/points/search`   — vector search
 *
 * The base URL and API key come from the *environment* (a transport concern),
 * never from a tool argument. Qdrant authenticates with an `api-key` header
 * (not `Bearer`), so we pass it as a static header rather than `bearerToken`.
 */
import { McpToolError } from "@mcp-kit/core";

import { RestClient, type FetchLike } from "./rest-client.js";

/** Qdrant's local default. Override with `QDRANT_URL`. */
export const DEFAULT_BASE_URL = "http://127.0.0.1:6333";

/** Distance metrics Qdrant supports for a vector index. */
export type Distance = "Cosine" | "Dot" | "Euclid" | "Manhattan";

export interface QdrantClientOptions {
  baseUrl?: string;
  /** Qdrant API key (`QDRANT_API_KEY`), sent as the `api-key` header. */
  apiKey?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}

export interface QdrantPoint {
  /** Point id — an unsigned integer or a UUID string. */
  id: number | string;
  vector: number[];
  payload?: Record<string, unknown>;
}

export interface CreateCollectionResult {
  collection: string;
  size: number;
  distance: Distance;
  created: boolean;
}

export interface UpsertResult {
  collection: string;
  upserted: number;
  status: string;
}

export interface ScoredPoint {
  id: number | string;
  score: number;
  payload: Record<string, unknown> | null;
}

interface RawStatusResponse {
  result?: unknown;
  status?: string | { error?: string };
}

interface RawSearchResponse {
  result?: Array<{ id: number | string; score: number; payload?: Record<string, unknown> | null }>;
}

interface RawUpsertResponse {
  result?: { status?: string; operation_id?: number };
}

function seg(value: string): string {
  return encodeURIComponent(value);
}

export class QdrantClient {
  private readonly rest: RestClient;

  constructor(options: QdrantClientOptions = {}) {
    const headers: Record<string, string> = { "User-Agent": "mcp-kit-recipe-qdrant" };
    if (options.apiKey) headers["api-key"] = options.apiKey;
    const restOptions: ConstructorParameters<typeof RestClient>[0] = {
      baseUrl: options.baseUrl ?? DEFAULT_BASE_URL,
      headers,
    };
    if (options.timeoutMs !== undefined) restOptions.timeoutMs = options.timeoutMs;
    if (options.fetchImpl) restOptions.fetchImpl = options.fetchImpl;
    this.rest = new RestClient(restOptions);
  }

  async createCollection(name: string, size: number, distance: Distance): Promise<CreateCollectionResult> {
    const res = await this.rest.request<RawStatusResponse>("PUT", `/collections/${seg(name)}`, {
      body: { vectors: { size, distance } },
    });
    return { collection: name, size, distance, created: res.result === true };
  }

  async upsertPoints(name: string, points: QdrantPoint[], wait = true): Promise<UpsertResult> {
    if (points.length === 0) {
      throw new McpToolError("invalid_input", "upsert_points needs at least one point.");
    }
    const res = await this.rest.request<RawUpsertResponse>("PUT", `/collections/${seg(name)}/points`, {
      query: { wait },
      body: { points },
    });
    return { collection: name, upserted: points.length, status: res.result?.status ?? "unknown" };
  }

  async search(
    name: string,
    vector: number[],
    opts: { limit?: number; withPayload?: boolean; filter?: Record<string, unknown> } = {},
  ): Promise<ScoredPoint[]> {
    const body: Record<string, unknown> = {
      vector,
      limit: opts.limit ?? 10,
      with_payload: opts.withPayload ?? true,
    };
    if (opts.filter !== undefined) body.filter = opts.filter;
    const res = await this.rest.request<RawSearchResponse>("POST", `/collections/${seg(name)}/points/search`, {
      body,
    });
    return (res.result ?? []).map((p) => ({ id: p.id, score: p.score, payload: p.payload ?? null }));
  }
}
