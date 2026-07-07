/**
 * Tool registry: the public catalog of Daena capabilities exposed
 * via MCP. Add a new file under src/tools/, export a `Tool`, then
 * register it in the array below.
 */

import { auditTool } from './audit.js';
import { chatTool } from './chat.js';
import { governanceTool } from './governance.js';
import { memoryTool } from './memory.js';
import { statusTool } from './status.js';
import type { Tool } from './types.js';

export const TOOL_REGISTRY: Tool[] = [
  statusTool,
  chatTool,
  memoryTool,
  governanceTool,
  auditTool,
];

export const TOOL_LOOKUP: ReadonlyMap<string, Tool> = new Map(
  TOOL_REGISTRY.map((t) => [t.name, t]),
);
