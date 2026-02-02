# MCP Server Wiring – Next Steps

Integrations UI already lists MCP servers (GitHub, Cloudflare, GCP, Azure/OpenAI, local models) and exposes `GET/PATCH /api/v1/integrations/mcp-servers`. **Wiring** means connecting these configs to actual MCP client calls so tools and agents can use them without rewriting logic.

## Current state

- **Config**: `integration_registry.get_default_integrations()` includes MCP-first entries with `mcp_server` and `enabled_by_default`.
- **API**: `GET /api/v1/integrations/mcp-servers` returns merged list; `PATCH .../mcp-servers/{server_id}` enables/disables via `config/mcp_servers.json`.
- **UI**: Connections page has an "MCP Servers" section with toggles.

## What wiring would add

1. **MCP client layer**  
   A small service that, given a server id (e.g. `github`, `cloudflare`), loads config from the registry + `mcp_servers.json`, establishes a connection (stdio/SSE), and exposes a common interface (e.g. `call_tool(server_id, tool_name, args)`).

2. **Tool routing**  
   When a tool is configured to use an MCP server (e.g. "deploy" → GitHub MCP), the execution layer or agent calls the MCP client instead of a local implementation. No change to agent prompts; only the backend swaps the implementation.

3. **Secrets**  
   MCP servers need API keys/tokens. Store in existing secrets/credentials (e.g. App Setup or env) and pass into the MCP client when connecting.

4. **Health / availability**  
   Optional: ping or list-tools per server and show status in the Integrations UI.

## Suggested order

1. Implement a minimal MCP client (stdio or SSE) for one server (e.g. local or GitHub).
2. Add a single "proxy" tool (e.g. `mcp_tool`) that takes `server_id`, `tool_name`, `args` and delegates to the client.
3. Register that tool in the execution layer and allow it from the Execution UI / tasks.
4. Extend Integrations UI to show connection status and link credentials to MCP servers.
5. Add more servers and optional playbooks (e.g. "on event X, call GitHub MCP deploy").

## References

- Execution layer: `backend/routes/execution_layer.py`, `backend/tools/registry.py`
- Integrations: `backend/routes/integrations.py`, `backend/services/integration_registry.py`
- Config: `config/mcp_servers.json` (if present)
