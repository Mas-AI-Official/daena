/**
 * daena_governance_check -- pre-flight a tool action through SecurityGate.
 *
 * Before another MCP server (filesystem-write, send-email, deploy) runs
 * a destructive action, ask Daena: would this require approval under
 * the operator's current governance mode + plain-English policies?
 *
 * Returns: { decision: ALLOWED | BLOCKED | APPROVAL_REQUIRED, tier,
 *            reason, policy_matches, mode }
 *
 * Use case: a Claude Desktop session about to delete files asks
 * daena_governance_check first; if APPROVAL_REQUIRED comes back, the
 * agent surfaces a confirmation card instead of executing blindly.
 */

import { DaenaError } from '../daena-client.js';
import { type Tool, ok, fail } from './types.js';

interface GovernanceResult {
  decision: 'ALLOWED' | 'BLOCKED' | 'APPROVAL_REQUIRED';
  tier: number;
  reason: string;
  mode: 'UNLEASHED' | 'BALANCED' | 'GOVERNED';
  policy_matches: Array<{ name: string; rule_id: string }>;
  approval_url?: string;
}

export const governanceTool: Tool = {
  name: 'daena_governance_check',
  description: 'Ask Daena\'s SecurityGate whether an action is allowed under the operator\'s governance mode + plain-English policies. Returns ALLOWED / BLOCKED / APPROVAL_REQUIRED with tier and matching policy names. Call BEFORE any destructive action (delete, send_email, deploy, transfer_money).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        description: 'Short action name. Examples: "delete_file", "send_email", "post_to_linkedin", "transfer_money", "deploy_to_production".',
      },
      target: {
        type: 'string',
        description: 'What the action operates on. Examples: "/home/user/project/secrets.env", "ceo@example.com", "main branch".',
      },
      details: {
        type: 'string',
        description: 'Additional context: payload size, recipients, money amount, etc. Helps the policy compiler match accurately.',
      },
      initiator: {
        type: 'string',
        enum: ['operator', 'background', 'delegated'],
        description: 'Who is initiating the action (affects Asset Shield tier collapse). Default: operator.',
      },
    },
    required: ['action'],
  },
  handler: async (args, { client }) => {
    const action = (args.action as string)?.trim();
    if (!action) return fail('action is required');

    const body = {
      action,
      target: args.target,
      details: args.details,
      initiator: args.initiator ?? 'operator',
      source: 'daena-mcp',
    };

    try {
      const result = await client.post<GovernanceResult>(
        '/api/v1/governance/evaluate',
        body,
      );
      return ok({
        decision: result.decision,
        governance_tier: result.tier,
        mode: result.mode,
        reason: result.reason,
        matched_policies: result.policy_matches?.map((p) => p.name) ?? [],
        approval_url: result.approval_url,
        guidance: decisionGuidance(result.decision),
      });
    } catch (err) {
      if (err instanceof DaenaError && err.status === 401) {
        return fail('Governance check requires authentication.', 'Set DAENA_TOKEN.');
      }
      const e = err as { message?: string };
      return fail(`daena_governance_check failed: ${e.message ?? String(err)}`);
    }
  },
};

function decisionGuidance(decision: string): string {
  switch (decision) {
    case 'ALLOWED':
      return 'Proceed. The action will still be audit-logged.';
    case 'APPROVAL_REQUIRED':
      return 'Do NOT proceed. Surface the approval_url to the operator and wait for explicit consent.';
    case 'BLOCKED':
      return 'Do NOT proceed. The action violates a hard law (e.g., data exfiltration, tenant isolation) that cannot be overridden.';
    default:
      return 'Unknown decision. Treat as BLOCKED.';
  }
}
