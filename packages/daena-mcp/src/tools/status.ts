/**
 * daena_status -- health check for the local Daena backend.
 *
 * Returns: backend reachable? auth status? Ollama up? Redis up?
 * which models loaded?
 *
 * Use case: a Claude Desktop user troubleshooting why Daena tools
 * are erroring. One tool call surfaces every common cause.
 */

import { DaenaError } from '../daena-client.js';
import { type Tool, ok, fail } from './types.js';

interface HealthDetailed {
  status: string;
  service: string;
  version: string;
  ollama?: {
    reachable: boolean;
    models?: string[];
    default_model?: string;
  };
  redis?: { reachable: boolean };
  database?: { reachable: boolean; counts?: Record<string, number> };
  uptime_seconds?: number;
}

export const statusTool: Tool = {
  name: 'daena_status',
  description: 'Health check the local Daena backend. Returns backend reachability, auth status, runtime / Ollama / Redis / DB status. Use when other Daena tools fail or before starting a session.',
  inputSchema: {
    type: 'object',
    properties: {},
  },
  handler: async (_args, { client, baseUrl, hasToken }) => {
    try {
      const detailed = await client.get<HealthDetailed>('/health/detailed');
      return ok({
        backend: { reachable: true, url: baseUrl },
        auth: { has_token: hasToken },
        version: detailed.version,
        ollama: detailed.ollama ?? { reachable: false },
        redis: detailed.redis ?? { reachable: false },
        database: detailed.database ?? { reachable: false },
        uptime_seconds: detailed.uptime_seconds,
      });
    } catch (err) {
      if (err instanceof DaenaError && err.code === 'NETWORK_ERROR') {
        return fail(
          `Daena backend unreachable at ${baseUrl}.`,
          'Start the backend with: cd D:\\Ideas\\Daena\\backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
        );
      }
      if (err instanceof DaenaError && err.status === 401) {
        return fail(
          'Daena returned 401 Unauthorized.',
          'Pass --token <jwt> or set DAENA_TOKEN env var. Get a token from Daena UI: Settings > Developer > API Tokens.',
        );
      }
      const e = err as { message?: string };
      return fail(`Status check failed: ${e.message ?? String(err)}`);
    }
  },
};
