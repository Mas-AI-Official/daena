# @mas-ai/daena-mcp

> **Daena MCP Server** -- expose your local Daena instance to any MCP-compatible host (Claude Desktop, Cursor, Codex CLI, Continue, etc.) via a single `npx` command.

## What this is

`daena-mcp` is a thin Model Context Protocol server that bridges an MCP host (Claude Desktop, Cursor, Codex CLI, ...) to a running Daena backend. It translates `tools/call` requests into HTTP calls against `http://localhost:8000` (or wherever Daena is running) and returns the responses as MCP tool results.

It exposes 5 tools:

| Tool | Use it when |
|---|---|
| `daena_status` | Troubleshooting -- check backend reachability, auth, Ollama, Redis, DB |
| `daena_chat` | Ask Daena a question through the full 10-stage governed pipeline |
| `daena_recall_memory` | Search NBMF memory tiers (T0..T4) for facts Daena already knows |
| `daena_governance_check` | Pre-flight a destructive action through SecurityGate before executing it |
| `daena_audit_query` | Search the audit log -- "what did Daena do today?", compliance review |

## Install (locally, pre-publish)

```bash
cd D:\Ideas\Daena\packages\daena-mcp
npm install
npm run build
npm link
```

`npm link` registers the `daena-mcp` binary globally. To unlink later: `npm unlink -g @mas-ai/daena-mcp`.

## Install (when published to npm)

```bash
npm install -g @mas-ai/daena-mcp
# or invoke ad-hoc with no install:
npx @mas-ai/daena-mcp --help
```

## Configure Claude Desktop

Edit `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "daena": {
      "command": "npx",
      "args": ["-y", "@mas-ai/daena-mcp"],
      "env": {
        "DAENA_URL": "http://localhost:8000",
        "DAENA_TOKEN": "<your-jwt-from-daena-settings>"
      }
    }
  }
}
```

Or, with a globally `npm link`'d build:

```json
{
  "mcpServers": {
    "daena": {
      "command": "daena-mcp",
      "env": {
        "DAENA_URL": "http://localhost:8000",
        "DAENA_TOKEN": "<your-jwt>"
      }
    }
  }
}
```

Restart Claude Desktop. The 5 `daena_*` tools should appear in the tool picker.

## Configure Cursor

Cursor's MCP config (Settings -> MCP -> Edit JSON):

```json
{
  "mcpServers": {
    "daena": {
      "command": "daena-mcp",
      "args": ["--url", "http://localhost:8000"],
      "env": { "DAENA_TOKEN": "<jwt>" }
    }
  }
}
```

## Configure Codex CLI

Codex reads `~/.codex/config.toml`:

```toml
[mcp_servers.daena]
command = "daena-mcp"
args    = ["--url", "http://localhost:8000"]
env     = { DAENA_TOKEN = "<jwt>" }
```

## Get a Daena token

In the Daena UI: **Settings -> Developer -> API Tokens -> Generate**. Tokens are JWTs scoped to the issuing user; rotate as you would any credential.

For local dev installs running with `DISABLE_AUTH=true`, no token is needed.

## CLI flags

| Flag | Env var | Default | Purpose |
|---|---|---|---|
| `--url <url>` | `DAENA_URL` | `http://localhost:8000` | HTTP base URL of the Daena backend |
| `--token <jwt>` | `DAENA_TOKEN` | unset | Bearer token for the inbound HTTP API |
| `--bridge` | -- | `false` | Enable outbound WebSocket bridge mode |
| `--bridge-token <token>` | `DAENA_BRIDGE_TOKEN` | unset | Auth for bridge mode |
| `--bridge-url <wss://...>` | -- | `wss://daena.mas-ai.co/api/v1/ws/bridge` | Bridge endpoint |
| `--verbose` | -- | `false` | Log to stderr for debugging |

## Two operating modes

### 1. STDIO (default) -- *inbound* tool calls

```
[Claude Desktop] -> stdio -> [daena-mcp] -> HTTP -> [Daena backend at http://localhost:8000]
```

The MCP host calls Daena tools. This is the standard MCP pattern; what you almost certainly want.

### 2. BRIDGE (`--bridge`) -- *outbound* tool execution

```
[Daena Cloud] -> wss -> [daena-mcp] -> [local MCP host's tools]
```

Daena Cloud dispatches work to your machine -- e.g., "read this local file and tell me what changed". Opt-in only. Requires `--bridge-token`.

## Verify the install

After setting up the config and restarting your MCP host, ask:

> "Use daena_status to confirm my Daena backend is reachable."

If the backend is offline, `daena_status` returns a one-line "backend unreachable" message with a hint on how to start it.

## Troubleshooting

- **`npm install -g @mas-ai/daena-mcp` returns 404** -- The package isn't published to npm yet. Use `npm link` from this folder, or install from the local path: `npm install -g D:\Ideas\Daena\packages\daena-mcp`.
- **`tools/list` returns nothing** -- The MCP host probably can't find the `daena-mcp` binary on PATH. After `npm link`, try `where daena-mcp` (Windows) / `which daena-mcp` (Mac/Linux).
- **Every tool returns 401** -- Set `DAENA_TOKEN` in the env block, or run Daena with `DISABLE_AUTH=true` for local dev.
- **`daena_chat` works but the answer is wrong** -- Check `daena_audit_query` to see which model was selected. The Primary Mind setting in Daena UI controls runtime preference.

## Architecture

`src/index.ts` is the entry point. It:
1. Parses CLI flags / env vars.
2. Builds a `DaenaClient` (HTTP) for inbound mode.
3. Optionally connects a `DaenaBridgeRelay` (WebSocket) for outbound mode.
4. Registers 5 tools from `src/tools/` with the SDK.
5. Speaks JSON-RPC 2.0 over stdio.

`src/tools/<name>.ts` is the tool registry. To add a tool:
1. Create `src/tools/myTool.ts` exporting a `Tool` (see `types.ts`).
2. Register it in `src/tools/index.ts`.
3. `npm run build`.

## License

MIT (Commercial Daena uses this package; the package itself is intentionally MIT to maximize distribution.)

## Related

- **Daena backend**: `D:\Ideas\Daena\backend\` -- the FastAPI service this package talks to.
- **Daena audit docs**: `D:\Ideas\Daena\docs\daena-Claude\` -- 11 audit + pitch deck files documenting the architecture this package exposes.
- **GitNexus index**: `D:\agents\wiki\` -- the unified knowledge graph.
