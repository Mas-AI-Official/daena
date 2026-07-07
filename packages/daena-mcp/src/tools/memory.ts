/**
 * daena_recall_memory -- query Daena's NBMF 5-tier memory.
 *
 * Lets an MCP host (Claude Desktop, Cursor, Codex) ask "what does
 * Daena know about X?" without firing a full chat request. Useful
 * for grounding a separate AI's answer in Daena's accumulated facts.
 *
 * Tiers (default: T1+T2 for working+project knowledge):
 *   T0 ephemeral    - 1 hr scratch
 *   T1 working      - 7 d
 *   T2 project      - 1 yr
 *   T3 institutional- permanent (founder approval)
 *   T4 founder-priv - permanent (founder only, encrypted)
 */

import { DaenaError } from '../daena-client.js';
import { type Tool, ok, fail } from './types.js';

interface MemoryEntry {
  id: string;
  tier: string;
  content: string;
  created_at: string;
  trust_score: number;
  agent_id?: string | null;
  skill_id?: string | null;
  is_quarantined?: boolean;
  is_sensitive?: boolean;
}

interface MemoryQueryResponse {
  entries: MemoryEntry[];
  total: number;
}

const VALID_TIERS = ['T0', 'T1', 'T2', 'T3', 'T4'] as const;

export const memoryTool: Tool = {
  name: 'daena_recall_memory',
  description: 'Search Daena\'s NBMF memory tiers (T0 ephemeral, T1 working, T2 project, T3 institutional, T4 founder-private). Returns top matches with trust score. Use to ground an answer in what Daena already knows.',
  inputSchema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Free-text search query.',
      },
      tiers: {
        type: 'array',
        items: { type: 'string' },
        description: 'Tier filter (default ["T1","T2"] for verified working+project memory). Use ["T0"] for recent scratch, ["T3"] for institutional truth. T4 founder-private will be redacted unless caller is founder.',
      },
      limit: {
        type: 'number',
        description: 'Max results (default 10, max 50).',
      },
      include_quarantined: {
        type: 'boolean',
        description: 'Include L2Q-quarantined entries (contradictions). Default false.',
      },
    },
    required: ['query'],
  },
  handler: async (args, { client }) => {
    const query = (args.query as string)?.trim();
    if (!query) return fail('query is required');

    const tiersInput = args.tiers as string[] | undefined;
    const tiers = (tiersInput && tiersInput.length > 0)
      ? tiersInput.filter((t) => (VALID_TIERS as readonly string[]).includes(t))
      : ['T1', 'T2'];

    if (tiers.length === 0) {
      return fail(`Invalid tier(s). Valid: ${VALID_TIERS.join(', ')}`);
    }

    const limit = Math.min(Math.max(Number(args.limit) || 10, 1), 50);
    const includeQuarantined = Boolean(args.include_quarantined);

    const params = new URLSearchParams({
      q: query,
      tiers: tiers.join(','),
      limit: String(limit),
      include_quarantined: includeQuarantined ? 'true' : 'false',
    });

    try {
      const resp = await client.get<MemoryQueryResponse>(
        `/api/v1/memory?${params.toString()}`,
      );
      const summary = (resp.entries ?? []).map((e) => ({
        tier: e.tier,
        trust: e.trust_score?.toFixed(2),
        content: e.content.length > 280 ? e.content.slice(0, 280) + '...' : e.content,
        agent: e.agent_id,
        skill: e.skill_id,
        quarantined: e.is_quarantined ?? false,
        created_at: e.created_at,
      }));
      return ok({
        query,
        tiers,
        total_matches: resp.total ?? summary.length,
        returned: summary.length,
        results: summary,
      });
    } catch (err) {
      if (err instanceof DaenaError && err.status === 401) {
        return fail('Daena memory requires authentication.', 'Set DAENA_TOKEN.');
      }
      const e = err as { message?: string };
      return fail(`daena_recall_memory failed: ${e.message ?? String(err)}`);
    }
  },
};
