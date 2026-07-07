/**
 * daena_audit_query -- search Daena's audit log.
 *
 * NOTE: this tool's body is left for you to design (see TODO).
 *
 * The skeleton handles arg validation + auth-error surfacing. What's
 * intentionally unfinished is the QUERY DESIGN: which fields can the
 * caller filter by, how do you aggregate, what do you return as a
 * compact summary that fits in a single MCP tool response?
 *
 * Backend reference (all already wired in Daena):
 *   GET /api/v1/governance/audit
 *     query params:
 *       limit (int, max 200)
 *       since (ISO datetime)
 *       until (ISO datetime)
 *       decision (ALLOWED | BLOCKED | APPROVAL_REQUIRED)
 *       tier (int 0-4)
 *       department (str)
 *       model (str)
 *       action_type (str)
 *     response:
 *       { entries: AuditEntry[], total: int }
 *
 *   AuditEntry shape (see backend/app/services/audit_service.py):
 *       id, timestamp, action, decision, tier, department, agent_id,
 *       model, latency_ms, cost_usd, route_metadata (JSONB),
 *       policy_matches (str[]), reason, request_id
 */

import { DaenaError } from '../daena-client.js';
import { type Tool, ok, fail } from './types.js';

interface AuditEntry {
  id: string;
  timestamp: string;
  action: string;
  decision: string;
  tier: number;
  department?: string;
  agent_id?: string;
  model?: string;
  latency_ms?: number;
  cost_usd?: number;
  policy_matches?: string[];
  reason?: string;
  route_metadata?: Record<string, unknown>;
}

interface AuditResponse {
  entries: AuditEntry[];
  total: number;
}

export const auditTool: Tool = {
  name: 'daena_audit_query',
  description: 'Search Daena\'s audit log. Useful for "what did Daena do today?", "show all blocked actions", "find decisions that required approval", or compliance review.',
  inputSchema: {
    type: 'object',
    properties: {
      since: {
        type: 'string',
        description: 'ISO 8601 datetime. Default: 24 hours ago.',
      },
      until: {
        type: 'string',
        description: 'ISO 8601 datetime. Default: now.',
      },
      decision: {
        type: 'string',
        enum: ['ALLOWED', 'BLOCKED', 'APPROVAL_REQUIRED'],
        description: 'Filter by governance decision. Omit for all.',
      },
      department: {
        type: 'string',
        description: 'Filter by department slug.',
      },
      limit: {
        type: 'number',
        description: 'Max entries to return (default 25, max 200).',
      },
      summary_mode: {
        type: 'string',
        enum: ['list', 'aggregate'],
        description: 'list = return individual entries. aggregate = return counts grouped by decision/department/tier. Default: list.',
      },
    },
  },
  handler: async (args, { client }) => {
    // ── Boilerplate done for you: param parsing + DaenaClient call ──
    const limit = Math.min(Math.max(Number(args.limit) || 25, 1), 200);
    const since = (args.since as string | undefined)
      ?? new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const until = args.until as string | undefined;
    const decision = args.decision as string | undefined;
    const department = args.department as string | undefined;
    const summaryMode = (args.summary_mode as string | undefined) ?? 'list';

    const params = new URLSearchParams({ since, limit: String(limit) });
    if (until) params.set('until', until);
    if (decision) params.set('decision', decision);
    if (department) params.set('department', department);

    let resp: AuditResponse;
    try {
      resp = await client.get<AuditResponse>(
        `/api/v1/governance/audit?${params.toString()}`,
      );
    } catch (err) {
      if (err instanceof DaenaError && err.status === 401) {
        return fail('Audit query requires authentication.', 'Set DAENA_TOKEN.');
      }
      const e = err as { message?: string };
      return fail(`daena_audit_query failed: ${e.message ?? String(err)}`);
    }

    // ─────────────────────────────────────────────────────────────────
    // TODO (your call -- this is the design choice that shapes the tool)
    //
    // Below is the response shaping. The naive default is "return every
    // entry verbatim" -- but with limit=200 that blows past Claude
    // Desktop's tool result size budget AND buries the signal.
    //
    // You decide:
    //   1. When summary_mode === 'list': what fields per entry are
    //      worth surfacing, and how do you keep it under ~10 KB?
    //   2. When summary_mode === 'aggregate': what aggregates matter
    //      most for the operator? (counts by decision? top blocked
    //      actions? cost per department? p95 latency? policy hit
    //      frequency?)
    //   3. Should you always include a few "anomalies" (e.g. a single
    //      BLOCKED entry hiding among 200 ALLOWED) regardless of mode?
    //
    // Replace the block below with your design. Keep it 5-15 lines.
    // ─────────────────────────────────────────────────────────────────
    if (summaryMode === 'aggregate') {
      // TODO(masoud): implement aggregation. Suggested shape:
      // {
      //   total: resp.total,
      //   window: { since, until: until ?? 'now' },
      //   by_decision: { ALLOWED: N, BLOCKED: N, APPROVAL_REQUIRED: N },
      //   by_tier: { '0': N, '1': N, '2': N, '3': N, '4': N },
      //   top_departments: [{ department: 'engineering', count: N }, ...],
      //   anomalies: [...],   // any BLOCKED in mostly-ALLOWED windows
      // }
      return ok({
        notice: 'aggregate mode not yet designed -- see TODO in src/tools/audit.ts',
        raw_total: resp.total,
        sample: resp.entries.slice(0, 3),
      });
    }

    // TODO(masoud): list mode -- decide what to keep per entry.
    // Default below returns the raw entries (works but verbose).
    return ok({
      total: resp.total,
      window: { since, until: until ?? 'now' },
      filters: { decision, department },
      returned: resp.entries.length,
      entries: resp.entries,
    });
  },
};
