/**
 * DaenaClient -- thin HTTP wrapper for Daena backend.
 *
 * Used by MCP tools to translate `tools/call` into Daena REST calls.
 * No state, no caching: the MCP host is short-lived (per Claude Desktop
 * conversation), so each call is fresh.
 *
 * Auth model:
 *   - JWT bearer token from --token flag OR DAENA_TOKEN env var.
 *   - Falls back to no-auth (local-only Daena dev install where the
 *     backend has DISABLE_AUTH=true).
 */

import { request } from 'undici';

export interface DaenaClientOptions {
  baseUrl: string;
  token?: string;
  timeoutMs?: number;
}

export interface DaenaResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export class DaenaError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'DaenaError';
  }
}

export class DaenaClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly timeoutMs: number;

  constructor(opts: DaenaClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, '');
    this.token = opts.token;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  /**
   * GET an endpoint. Returns the parsed JSON body on success.
   * Throws DaenaError on non-2xx OR network failure.
   */
  async get<T>(path: string): Promise<T> {
    return this.send<T>('GET', path);
  }

  /**
   * POST an endpoint with a JSON body.
   */
  async post<T>(path: string, body: unknown): Promise<T> {
    return this.send<T>('POST', path, body);
  }

  /**
   * PATCH an endpoint with a JSON body.
   */
  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.send<T>('PATCH', path, body);
  }

  private async send<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'User-Agent': '@mas-ai/daena-mcp/0.1.0',
    };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const { statusCode, body: respBody } = await request(url, {
        method: method as 'GET' | 'POST' | 'PATCH',
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });

      const text = await respBody.text();
      let parsed: unknown;
      try {
        parsed = text ? JSON.parse(text) : {};
      } catch {
        throw new DaenaError(
          statusCode,
          'INVALID_JSON',
          `Daena returned non-JSON (HTTP ${statusCode}): ${text.slice(0, 200)}`,
        );
      }

      if (statusCode >= 400) {
        const envelope = parsed as Partial<DaenaResponse<unknown>>;
        const code = envelope?.error?.code ?? 'HTTP_' + statusCode;
        const message = envelope?.error?.message ?? `HTTP ${statusCode}`;
        throw new DaenaError(statusCode, code, message);
      }

      // Daena's API uses an envelope { success, data, error }. Most
      // endpoints return data inside; some legacy ones return raw
      // payload. Unwrap when the envelope shape is present.
      const envelope = parsed as Partial<DaenaResponse<T>>;
      if (
        envelope &&
        typeof envelope === 'object' &&
        'success' in envelope &&
        'data' in envelope
      ) {
        return envelope.data as T;
      }
      return parsed as T;
    } catch (err) {
      if (err instanceof DaenaError) throw err;
      const e = err as { name?: string; message?: string };
      if (e.name === 'AbortError') {
        throw new DaenaError(
          0,
          'TIMEOUT',
          `Daena did not respond within ${this.timeoutMs}ms at ${url}`,
        );
      }
      throw new DaenaError(
        0,
        'NETWORK_ERROR',
        `Could not reach Daena at ${url}: ${e.message ?? String(err)}`,
      );
    } finally {
      clearTimeout(timer);
    }
  }
}
