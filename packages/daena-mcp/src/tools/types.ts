/**
 * Tool registry types.
 *
 * Each tool is a small object with: name, description, JSON schema for
 * inputs, and an async handler. The handler receives the parsed args
 * + a DaenaClient, returns a `ToolResult`.
 *
 * Adding a tool: create a new file in src/tools/ exporting a `Tool`,
 * then register it in src/tools/index.ts.
 */

import type { DaenaClient } from '../daena-client.js';

export interface ToolInputSchema {
  type: 'object';
  properties: Record<string, {
    type: string;
    description?: string;
    enum?: readonly string[];
    items?: { type: string };
  }>;
  required?: readonly string[];
}

// Open record so it satisfies the SDK's CallToolResult union
// (which optionally carries _meta or async-task envelopes).
export interface ToolResult {
  content: Array<{ type: 'text'; text: string }>;
  isError?: boolean;
  [key: string]: unknown;
}

export interface ToolContext {
  client: DaenaClient;
  baseUrl: string;
  hasToken: boolean;
}

export interface Tool {
  name: string;
  description: string;
  inputSchema: ToolInputSchema;
  handler: (args: Record<string, unknown>, ctx: ToolContext) => Promise<ToolResult>;
}

/** Helper: format a successful tool response from any JSON-serializable payload. */
export function ok(payload: unknown): ToolResult {
  return {
    content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
  };
}

/** Helper: format an error tool response. The MCP host will surface this to the user. */
export function fail(message: string, hint?: string): ToolResult {
  const body = hint ? `${message}\n\nHint: ${hint}` : message;
  return {
    content: [{ type: 'text', text: body }],
    isError: true,
  };
}
