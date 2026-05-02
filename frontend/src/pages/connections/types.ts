/**
 * Shared types for ConnectionsPage and its sub-tab components.
 * Lives in its own file so sub-files can import without creating
 * a cycle through ConnectionsPage.tsx.
 */

export interface RuntimeData {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: {
    is_authenticated: boolean
    plan_name: string | null
    user_display: string | null
    login_url?: string
    setup_command?: string
    method?: string
    status?: string
  } | null
}

export interface ExtensionData {
  id: string
  name: string
  description: string
  enabled: boolean
  permission: string
  // Session 10: Claude Desktop parity -- show each tool the MCP server
  // exposes, with its own Allow/Ask/Block permission. Optional because
  // not every extension type surfaces tools at scan time (e.g. Claude
  // Code plugins are categorized by name only). Missing tools arrays
  // render an informative placeholder instead of empty space.
  tools?: string[]
  source?: string   // "mcp-server", "claude-plugins-official", "dxt-*", etc.
  version?: string
  // Session 11: per-user saved tool permissions from User.settings JSONB.
  // Empty/missing means "inherit the default permission". Hydrated by
  // the backend in GET /connections/extensions.
  tool_permissions?: Record<string, string>
}

// Auth methods for connectors
export type AuthMethod = 'oauth' | 'api_key' | 'token'

// Permission tri-state (matches Claude Desktop's MCP UI)
export type Permission = 'ALLOW' | 'ASK_EACH_TIME' | 'BLOCK'

// Browse-modal catalog item (marketplace-style entries)
export interface BrowseCatalogItem {
  id: string
  name: string
  description: string
  popularity?: string   // "Most popular", "#2 popular", etc.
  connected?: boolean
  category: string
  authUrl?: string      // URL to open for OAuth or setup
}

// Connector definition shape (matches the inline objects in the catalog).
// Codex-style enrichment: when a connector bundles official skills + an
// MCP server, declare them inline so a single "Connect" wires the
// account auth + every bundled skill + MCP at once. Mirrors how Codex
// surfaces e.g. Cloudflare = Wrangler + Agents SDK + Workers Best
// Practices + Cloudflare API MCP, all configured by one OAuth.
export interface BundledSkill {
  id: string             // skill slug, e.g. 'cloudflare-wrangler'
  name: string           // display name
  description: string    // one-line "what this skill does"
}
export interface BundledMcp {
  name: string           // e.g. 'Cloudflare API MCP'
  package?: string       // optional install hint
  scope: string          // 'official' | 'community' | 'self-hosted'
}
export interface ConnectorDef {
  id: string
  name: string
  subtitle: string
  category: string
  auth: AuthMethod
  tools: string[]
  // ── Codex-style metadata (all optional for backwards compat) ──
  developer?: string                    // e.g. 'Cloudflare', 'OpenAI', 'Anthropic'
  built_by?: string                     // e.g. 'Built by OpenAI'
  capabilities?: ('Interactive' | 'Write' | 'Read')[]
  website?: string                      // marketing URL
  privacy_policy?: string               // link
  terms_url?: string                    // link
  included_skills?: BundledSkill[]      // skills bundled with this connector
  included_mcp?: BundledMcp             // MCP server bundled with this connector
}

// Equivalent MCP server metadata for a connector (Session 10).
export interface MCPEquivalent {
  name: string         // Display name of the MCP server
  package: string      // npm package or command arg
  command: string      // "npx" | "uvx" | etc.
  args: string[]       // Command args
  repo_url: string     // Where the source lives
  auth_note: string    // One-line description of how auth works
}

// Shared OAuth launcher options (used by ConnectorRow + Browse modal).
export interface StartOAuthOptions {
  connectorId: string
  connectorName: string
  onSuccess?: () => void
  onRequestSetup?: (missingField: string) => void
}

// Top-level tab key for the page nav.
export type TabKey = 'runtimes' | 'extensions' | 'connectors' | 'mcp'
