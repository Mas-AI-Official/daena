/**
 * pluginCard -- view-model adapter (founder pivot 2026-05-02).
 *
 * The catalog (`marketplace_catalog.py`) carries 6 different `kind`s
 * internally: mcp_server / oauth_app / browser_tool / computer_use /
 * cli_runtime / api_provider / local_model / skill_pack.
 *
 * The user-facing UX collapses ALL of those into ONE concept: "Plugins."
 * This adapter normalizes a backend `MarketplaceCard` into a single
 * `PluginCard` shape with founder-spec status + action vocabulary:
 *
 *   status:  available | installed | needs_auth | connected | failed | not_supported_on_os
 *   action:  install   | configure | connect    | test      | open   | setup_guide
 *
 * Honesty:
 *   - "connected" only when V2 truth has callable=true AND no recent failure
 *   - "needs_auth" when configured but auth has not been proven yet
 *   - "available" when no V2 row exists
 *   - "not_supported_on_os" when entry.compatible_os excludes the current host
 *   - skill packs collapse to status="connected" + action="open" + caption
 *     "Skill pack. Needs a runtime/tool to execute."
 *   - install action is gated on backend safety -- today every install
 *     surfaces as "Setup guide" because the backend has no safe install
 *     endpoint yet (per founder rule 8 + 11)
 */

import type {
  CatalogCategory,
  CatalogEntry,
  CatalogKind,
  LifecycleState,
  MarketplaceCard,
} from '@/hooks/useMarketplace'

// ── Plugin-card vocabulary (founder spec) ──

export type PluginStatus =
  | 'available'
  | 'installed'
  | 'needs_auth'
  | 'connected'
  | 'failed'
  | 'not_supported_on_os'

export type PluginAction =
  | 'install'
  | 'configure'
  | 'connect'
  | 'test'
  | 'open'
  | 'setup_guide'

export type BackingType =
  | 'mcp'
  | 'oauth'
  | 'api'
  | 'local_model'
  | 'skill_pack'
  | 'cli'
  | 'browser'
  | 'computer_use'

export interface PluginCard {
  id: string
  name: string
  vendor: string
  icon: string                  // single-letter glyph hint (kind)
  category: CatalogCategory
  category_label: string
  description: string
  included_skills: string[]     // capabilities exposed by this plugin
  backing_types: BackingType[]
  status: PluginStatus
  status_label: string
  primary_action: PluginAction
  primary_action_label: string
  action_enabled: boolean
  failure_reason: string | null
  last_checked: string | null
  is_skill_pack: boolean
  is_skill_pack_caption: string | null
  required_env_vars: string[]
  setup_notes: string
  install_method: CatalogEntry['install_method']
  auth_type: CatalogEntry['auth_type']
  risk_level: CatalogEntry['risk_level']
  official_url: string
  compatible_os: string[]
  /** PR-CONN-MCP-CATALOG-SKILL-BUNDLES (2026-05-03): bundle metadata
   * surfaced on the card. ``default_skills`` are NOT executable until
   * the plugin's lifecycle reaches ``callable`` -- the UI shows them
   * with the "Skill ready. Requires <plugin> connection." caption
   * until then. ``officiality`` drives the trust badge. */
  officiality: import('@/hooks/useMarketplace').Officiality
  default_skills: string[]
  suggested_prompts: string[]
  permissions_summary: string[]
  source_refs: string[]
  last_verified_at: string
  // Pass-through of the source card so callers can call probe / enable
  // via existing V2 endpoints without re-fetching.
  v2_row_id: string | null
  source: MarketplaceCard
}

// ── Status display labels ──

const STATUS_LABELS: Record<PluginStatus, string> = {
  available: 'Available',
  installed: 'Installed',
  needs_auth: 'Needs auth',
  connected: 'Connected',
  failed: 'Failed',
  not_supported_on_os: 'Not supported on this OS',
}

const ACTION_LABELS: Record<PluginAction, string> = {
  install: 'Install',
  configure: 'Configure',
  connect: 'Connect',
  test: 'Test',
  open: 'Open',
  setup_guide: 'Setup guide',
}

// ── Category display labels (mirror the Codex-style catalog) ──

const CATEGORY_LABEL: Record<CatalogCategory, string> = {
  filesystem: 'Filesystem',
  browser: 'Browser',
  computer_use: 'Computer Use',
  code_platform: 'Code Platforms',
  communication: 'Communication',
  productivity: 'Productivity',
  design: 'Design',
  data_storage: 'Data + Storage',
  payment: 'Payment',
  research: 'Research',
  local_llm: 'Local LLM',
  ai_provider: 'AI Providers',
  dev_tools: 'Dev Tools',
  cli_runtime: 'CLI Runtimes',
}

// ── Kind -> single-letter icon hint ──

const KIND_ICON: Record<CatalogKind, string> = {
  mcp_server: 'M',
  oauth_app: 'O',
  browser_tool: 'B',
  computer_use: 'C',
  cli_runtime: 'R',
  api_provider: 'A',
  local_model: 'L',
  skill_pack: 'S',
}

// ── Kind -> backing-type tag ──

const KIND_TO_BACKING: Record<CatalogKind, BackingType> = {
  mcp_server: 'mcp',
  oauth_app: 'oauth',
  browser_tool: 'browser',
  computer_use: 'computer_use',
  cli_runtime: 'cli',
  api_provider: 'api',
  local_model: 'local_model',
  skill_pack: 'skill_pack',
}

// ── OS detection (best-effort browser-side, never blocks) ──

function currentOs(): string {
  if (typeof navigator === 'undefined') return 'unknown'
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('windows')) return 'windows'
  if (ua.includes('mac os')) return 'mac'
  if (ua.includes('linux')) return 'linux'
  return 'unknown'
}

function isOsSupported(entry: CatalogEntry): boolean {
  if (entry.compatible_os.length === 0) return true  // unrestricted
  const os = currentOs()
  if (os === 'unknown') return true  // do not falsely block when unknown
  return entry.compatible_os.includes(os)
}

// ── Status derivation (lifecycle -> founder vocabulary) ──

function deriveStatus(card: MarketplaceCard, entry: CatalogEntry): PluginStatus {
  // OS gate runs first -- never mark "Connected" on an unsupported host.
  if (!isOsSupported(entry)) return 'not_supported_on_os'

  // Skill packs always connected (they are content, not callable).
  if (entry.kind === 'skill_pack') return 'connected'
  if (card.lifecycle === 'skill_pack') return 'connected'

  // Failure overrides happy-path
  if (card.lifecycle === 'failed') return 'failed'

  // Disabled / archived collapse to available so the operator can re-enable
  if (card.lifecycle === 'disabled' || card.lifecycle === 'archived') {
    return 'installed'
  }

  // Happy path
  if (card.lifecycle === 'callable' || card.lifecycle === 'enabled') return 'connected'
  if (card.lifecycle === 'reachable') return 'needs_auth'
  if (card.lifecycle === 'configured') {
    // Configured + auth not required -> needs_auth label still works
    // (the Test button proves callable=true)
    return entry.auth_type === 'none' ? 'installed' : 'needs_auth'
  }
  if (card.lifecycle === 'installed') return 'installed'

  return 'available'
}

// ── Action derivation (founder safety rules) ──

function deriveAction(
  card: MarketplaceCard,
  entry: CatalogEntry,
  status: PluginStatus,
): { action: PluginAction; enabled: boolean } {
  // OS gate
  if (status === 'not_supported_on_os') {
    return { action: 'setup_guide', enabled: true }
  }

  // Skill packs: always Open (no install/test/connect)
  if (entry.kind === 'skill_pack' || card.lifecycle === 'skill_pack') {
    return { action: 'open', enabled: true }
  }

  // Connected: re-test or open
  if (status === 'connected') {
    if (card.v2_row_id) return { action: 'test', enabled: true }
    return { action: 'open', enabled: true }
  }

  // Failed: re-test (or setup guide if no V2 row)
  if (status === 'failed') {
    if (card.v2_row_id) return { action: 'test', enabled: true }
    return { action: 'setup_guide', enabled: true }
  }

  // Needs auth -> Connect (OAuth) or Configure (api_key/token) or Test (none)
  if (status === 'needs_auth') {
    if (entry.auth_type === 'oauth') return { action: 'connect', enabled: true }
    // PR-CONN-PROVIDER-KEY-VISIBILITY (2026-05-03): an api_provider /
    // local_model card whose credential is ALREADY present in
    // settings (provider_key_present === true) is ready to probe.
    // Show Test instead of Configure so the operator can verify the
    // key works without bouncing through the API-keys UI.
    if (
      (entry.kind === 'api_provider' || entry.kind === 'local_model')
      && card.provider_key_present === true
    ) {
      return { action: 'test', enabled: true }
    }
    if (entry.auth_type === 'api_key' || entry.auth_type === 'token') {
      return { action: 'configure', enabled: true }
    }
    return { action: 'test', enabled: true }
  }

  // Installed (V2 row exists, not yet configured) -> Configure
  if (status === 'installed') {
    if (entry.auth_type === 'oauth') return { action: 'connect', enabled: true }
    // Same provider-key truth guard as the needs_auth branch above.
    if (
      (entry.kind === 'api_provider' || entry.kind === 'local_model')
      && card.provider_key_present === true
    ) {
      return { action: 'test', enabled: true }
    }
    if (entry.auth_type === 'api_key' || entry.auth_type === 'token') {
      return { action: 'configure', enabled: true }
    }
    return { action: 'test', enabled: true }
  }

  // Available -- the founder safety rules:
  //   "If backend cannot install yet, button must say 'Setup guide,' not fake Install."
  //   "If OAuth is needed, button says 'Connect.'"
  //   "If MCP package is known but not installed, button says 'Install' only if
  //    backend can safely write config."
  //   "If backend only has instructions, button says 'Setup guide.'"
  //
  // PR-CONN-MCP-INSTALL-INTO-CLI (2026-05-02): MCP entries with a
  // resolvable command_template DO have a safe install endpoint now
  // (preview + apply with backup + atomic write). Surface "Install"
  // for those; everything else still routes to Setup guide.
  if (entry.install_method === 'coming-soon') {
    return { action: 'setup_guide', enabled: true }
  }
  // PR-CONN-PROVIDER-KEY-VISIBILITY (2026-05-03): API providers
  // whose credential is missing in settings get "Configure" -- a
  // deep-link into the API key surface instead of a generic Setup
  // guide. provider_key_present === false is the honest signal
  // (None = not credentialed via settings; True is handled upstream
  // by the lifecycle bump to "configured" -> "test").
  //
  // Local-model endpoints also use provider_key_present, but their
  // missing config is an env var (OLLAMA_BASE_URL / VLLM_BASE_URL),
  // not a paste-in key -- we keep them on Setup guide so the drawer
  // shows the correct env-var instructions instead of routing to the
  // API-key UI which would confuse the operator.
  if (entry.kind === 'api_provider' && card.provider_key_present === false) {
    return { action: 'configure', enabled: true }
  }
  if (entry.auth_type === 'oauth') {
    // No V2 row yet, but the catalog knows the OAuth provider. Point
    // the operator at the Setup guide; the actual Connect button lights
    // up after they paste OAuth client credentials in Settings and
    // discovery imports the row.
    return { action: 'setup_guide', enabled: true }
  }
  if (
    entry.kind === 'mcp_server'
    && entry.command_template
    && entry.command_template.length > 0
  ) {
    return { action: 'install', enabled: true }
  }
  return { action: 'setup_guide', enabled: true }
}

// ── Failure reason picker ──

function pickFailureReason(card: MarketplaceCard): string | null {
  if (card.v2_failure_reason) return card.v2_failure_reason
  if (!card.v2_truth) return null
  const dims: Array<keyof typeof card.v2_truth> = [
    'callable',
    'authenticated',
    'reachable',
    'configured',
  ]
  for (const dim of dims) {
    const t = card.v2_truth[dim]
    if (t.failure_reason) return t.failure_reason
  }
  return null
}

// ── Public adapter ──

export function pluginCardFromMarketplaceCard(card: MarketplaceCard): PluginCard {
  const entry = card.catalog
  const status = deriveStatus(card, entry)
  const { action, enabled } = deriveAction(card, entry, status)
  const isSkillPack = entry.kind === 'skill_pack' || card.lifecycle === 'skill_pack'

  return {
    id: entry.id,
    name: entry.display_name,
    vendor: entry.vendor,
    icon: KIND_ICON[entry.kind] ?? '?',
    category: entry.category,
    category_label: CATEGORY_LABEL[entry.category] ?? entry.category,
    description: entry.short_description,
    // PR-CONN-MCP-CATALOG-SKILL-BUNDLES (2026-05-03): prefer bundle
    // default_skills (Codex-style names) over the legacy
    // capabilities field for the included-skills chip list. Fall
    // back to capabilities for entries that haven't been bumped to
    // the new schema yet.
    included_skills: (entry.default_skills && entry.default_skills.length > 0)
      ? entry.default_skills
      : entry.capabilities,
    backing_types: [KIND_TO_BACKING[entry.kind]],
    status,
    status_label: STATUS_LABELS[status],
    primary_action: action,
    primary_action_label: ACTION_LABELS[action],
    action_enabled: enabled,
    failure_reason: pickFailureReason(card),
    last_checked: card.v2_last_probe_at,
    is_skill_pack: isSkillPack,
    is_skill_pack_caption: isSkillPack
      ? 'Skill pack. Needs a runtime/tool to execute.'
      : null,
    required_env_vars: entry.required_env_vars,
    setup_notes: entry.setup_notes,
    install_method: entry.install_method,
    auth_type: entry.auth_type,
    risk_level: entry.risk_level,
    official_url: entry.official_url,
    compatible_os: entry.compatible_os,
    officiality: entry.officiality ?? 'community',
    default_skills: entry.default_skills ?? [],
    suggested_prompts: entry.suggested_prompts ?? [],
    permissions_summary: entry.permissions_summary ?? [],
    source_refs: entry.source_refs ?? [],
    last_verified_at: entry.last_verified_at ?? '',
    v2_row_id: card.v2_row_id,
    source: card,
  }
}

// ── Tone (color) per status ──

export const PLUGIN_STATUS_TONE: Record<
  PluginStatus,
  { dot: string; text: string; bg: string; border: string }
> = {
  available: {
    dot: 'bg-cyan-300',
    text: 'text-cyan-200',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
  },
  installed: {
    dot: 'bg-blue-300',
    text: 'text-blue-200',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
  },
  needs_auth: {
    dot: 'bg-amber-400',
    text: 'text-amber-200',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
  connected: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-500/40',
  },
  failed: {
    dot: 'bg-rose-400',
    text: 'text-rose-200',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
  },
  not_supported_on_os: {
    dot: 'bg-slate-500',
    text: 'text-slate-300',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
  },
}

export function pluginStatusTone(status: PluginStatus) {
  return PLUGIN_STATUS_TONE[status] ?? PLUGIN_STATUS_TONE.available
}

// ── Officiality badge (PR-CONN-MCP-CATALOG-SKILL-BUNDLES) ──

import type { Officiality } from '@/hooks/useMarketplace'

export const OFFICIALITY_LABEL: Record<Officiality, string> = {
  'official': 'Official',
  'vendor-official': 'Vendor official',
  'vendor-blessed': 'Vendor blessed',
  'verified': 'Verified',
  'community': 'Community',
  'archived': 'Archived',
  'coming-soon': 'Coming soon',
}

export const OFFICIALITY_TONE: Record<
  Officiality,
  { dot: string; text: string; bg: string; border: string }
> = {
  // Top trust tiers: green
  'official': {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
  },
  'vendor-official': {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
  },
  'vendor-blessed': {
    dot: 'bg-cyan-300',
    text: 'text-cyan-200',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
  },
  'verified': {
    dot: 'bg-cyan-300',
    text: 'text-cyan-200',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
  },
  // Caveat tiers: amber/slate
  'community': {
    dot: 'bg-amber-300',
    text: 'text-amber-200',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
  'archived': {
    dot: 'bg-slate-400',
    text: 'text-slate-300',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
  },
  'coming-soon': {
    dot: 'bg-slate-500',
    text: 'text-slate-400',
    bg: 'bg-slate-500/5',
    border: 'border-slate-500/20',
  },
}

export function officialityTone(o: Officiality | undefined) {
  return OFFICIALITY_TONE[o ?? 'community']
}

export function officialityLabel(o: Officiality | undefined) {
  return OFFICIALITY_LABEL[o ?? 'community']
}

// Re-export for convenience
export type {
  CatalogCategory,
  CatalogEntry,
  CatalogKind,
  LifecycleState,
  MarketplaceCard,
}
