/**
 * daena_chat -- send a message to Daena's 10-stage pipeline.
 *
 * The MCP host (e.g. Claude Desktop) gets back the synthesized answer
 * from Daena's ChatOrchestrator: SecurityGate -> ... -> ModelRouter
 * (with primary_mind boost) -> MemoryRecall -> LLMStream -> Persist.
 *
 * Streaming note: MCP `tools/call` is request-response, not streaming.
 * We use Daena's non-streaming chat endpoint and return the full
 * response. (A future iteration could expose stream events as
 * progress reports per the MCP `_meta.progressToken` mechanism.)
 */

import { DaenaError } from '../daena-client.js';
import { type Tool, ok, fail } from './types.js';

interface ChatResponse {
  message_id?: string;
  session_id?: string;
  content: string;
  model?: string;
  governance_tier?: number;
  reasoning_mode?: string;
  cost_usd?: number;
  latency_ms?: number;
  audit_id?: string;
}

export const chatTool: Tool = {
  name: 'daena_chat',
  description: 'Ask Daena a question. Daena routes it through the full 10-stage pipeline (security check, governance, model router with primary_mind preference, NBMF memory recall, LLM stream, audit log). Best for questions that need Daena\'s memory + multi-model reasoning, not for simple lookups.',
  inputSchema: {
    type: 'object',
    properties: {
      message: {
        type: 'string',
        description: 'The question or request to send to Daena.',
      },
      department: {
        type: 'string',
        description: 'Optional department to scope the request (engineering, product, marketing, sales, finance, operations, research, legal, skill_governance, security_operations). If omitted, Daena routes to the most relevant department.',
      },
      reasoning_mode: {
        type: 'string',
        enum: ['standard', 'council', 'quintessence'],
        description: 'Reasoning depth. standard = single best model. council = 3 models in parallel + synthesis. quintessence = council + 15 expert lenses. Default: standard.',
      },
      session_id: {
        type: 'string',
        description: 'Optional existing session id for continued conversation. Omit to start fresh.',
      },
    },
    required: ['message'],
  },
  handler: async (args, { client, baseUrl }) => {
    const message = (args.message as string)?.trim();
    if (!message) return fail('message is required');

    const department = args.department as string | undefined;
    const reasoningMode = (args.reasoning_mode as string | undefined) ?? 'standard';
    const sessionId = args.session_id as string | undefined;

    try {
      const resp = await client.post<ChatResponse>('/api/v1/chat/messages', {
        message,
        department,
        reasoning_mode: reasoningMode,
        session_id: sessionId,
      });
      return ok({
        answer: resp.content,
        session_id: resp.session_id,
        model: resp.model,
        reasoning_mode: resp.reasoning_mode,
        governance_tier: resp.governance_tier,
        cost_usd: resp.cost_usd,
        latency_ms: resp.latency_ms,
        audit_id: resp.audit_id,
      });
    } catch (err) {
      if (err instanceof DaenaError && err.status === 401) {
        return fail(
          'Daena chat requires authentication.',
          'Pass --token <jwt> or set DAENA_TOKEN. Get one from Daena UI: Settings > Developer > API Tokens.',
        );
      }
      if (err instanceof DaenaError && err.code === 'NETWORK_ERROR') {
        return fail(`Daena backend unreachable at ${baseUrl}.`, 'Run daena_status to diagnose.');
      }
      const e = err as { message?: string };
      return fail(`daena_chat failed: ${e.message ?? String(err)}`);
    }
  },
};
