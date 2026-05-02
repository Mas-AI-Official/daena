/**
 * pluginIcons -- map a marketplace catalog id to a brand icon component.
 *
 * PR-CONN-PLUGIN-PARITY-UX (2026-05-02): the existing BrandIcons.tsx
 * registry already covers most third-party brands (GitHub, Slack,
 * Stripe, Notion, Cloudflare, ...) plus a CdnIcon dynamic loader for
 * SimpleIcons. This file is the catalog-id-aware adapter:
 *   - explicit map: catalog id -> known brand icon
 *   - fallback: getMcpBrandIcon() with kind-aware default glyph
 *   - never hotlinks random logos; uses local components or the
 *     CdnIcon helper which has its own fallback to BrandAvatarIcon
 *
 * No new external dependencies. No copyrighted logo files committed.
 */

import { memo } from 'react'
import type { ComponentType } from 'react'
import {
  AppWindow, BookOpen, Cpu, Globe, Server, Terminal,
} from 'lucide-react'

import {
  AnthropicIcon,
  type BrandIconProps,
  BrandAvatarIcon,
  BraveSearchIcon,
  CanvaIcon,
  CloudflareIcon,
  DesktopCommanderIcon,
  FigmaIcon,
  FilesystemIcon,
  GitHubIcon,
  GitIcon,
  GmailIcon,
  GoogleCalendarIcon,
  GoogleDriveIcon,
  GoogleGeminiIcon,
  HuggingFaceIcon,
  LinearIcon,
  MemoryIcon,
  NotionIcon,
  OllamaIcon,
  OpenAIIcon,
  PlaywrightIcon,
  PostgresIcon,
  RedisIcon,
  SentryIcon,
  SQLiteIcon,
  SlackIcon,
  StripeIcon,
  VercelIcon,
  WindowsMCPIcon,
  getBrandIcon,
  getMcpBrandIcon,
} from '@/components/icons/BrandIcons'

import type { CatalogKind } from '@/hooks/useMarketplace'

type PluginIcon = ComponentType<BrandIconProps>

// ── Kind-based fallback glyphs (so cards never render an "unknown" box) ──

const PerplexityFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Pp" size={size} className={className || 'text-cyan-300'} />
))
PerplexityFallback.displayName = 'PerplexityFallback'

const GroqFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Gq" size={size} className={className || 'text-orange-300'} />
))
GroqFallback.displayName = 'GroqFallback'

const OpenRouterFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="OR" size={size} className={className || 'text-violet-300'} />
))
OpenRouterFallback.displayName = 'OpenRouterFallback'

const TogetherFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="To" size={size} className={className || 'text-rose-300'} />
))
TogetherFallback.displayName = 'TogetherFallback'

const VLLMFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <Cpu size={size} className={className || 'text-emerald-300'} />
))
VLLMFallback.displayName = 'VLLMFallback'

const ChromeDevToolsFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Cd" size={size} className={className || 'text-blue-300'} />
))
ChromeDevToolsFallback.displayName = 'ChromeDevToolsFallback'

const BrowserbaseFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Bb" size={size} className={className || 'text-pink-300'} />
))
BrowserbaseFallback.displayName = 'BrowserbaseFallback'

const FetchFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <Globe size={size} className={className || 'text-sky-300'} />
))
FetchFallback.displayName = 'FetchFallback'

const TimeFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Tm" size={size} className={className || 'text-amber-300'} />
))
TimeFallback.displayName = 'TimeFallback'

const SequentialThinkingFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="St" size={size} className={className || 'text-violet-300'} />
))
SequentialThinkingFallback.displayName = 'SequentialThinkingFallback'

const MongoDBFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Mo" size={size} className={className || 'text-emerald-300'} />
))
MongoDBFallback.displayName = 'MongoDBFallback'

const ShopifyFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Sh" size={size} className={className || 'text-emerald-300'} />
))
ShopifyFallback.displayName = 'ShopifyFallback'

const NetlifyFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Nl" size={size} className={className || 'text-teal-300'} />
))
NetlifyFallback.displayName = 'NetlifyFallback'

const GitLabFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Gl" size={size} className={className || 'text-orange-300'} />
))
GitLabFallback.displayName = 'GitLabFallback'

const JiraFallback = memo(({ size = 24, className }: BrandIconProps) => (
  <BrandAvatarIcon label="Jr" size={size} className={className || 'text-blue-300'} />
))
JiraFallback.displayName = 'JiraFallback'

// ── Catalog-id -> icon (explicit) ──

const PLUGIN_ICON_MAP: Record<string, PluginIcon> = {
  // CLI runtimes
  'cli-claude-code': AnthropicIcon,
  'cli-codex': OpenAIIcon,
  'cli-gemini': GoogleGeminiIcon,

  // AI providers
  'provider-anthropic': AnthropicIcon,
  'provider-openai': OpenAIIcon,
  'provider-google-gemini': GoogleGeminiIcon,
  'provider-perplexity': PerplexityFallback,
  'provider-groq': GroqFallback,
  'provider-openrouter': OpenRouterFallback,
  'provider-together': TogetherFallback,

  // Local LLM
  'local-ollama': OllamaIcon,
  'local-vllm': VLLMFallback,

  // Browser
  'mcp-playwright': PlaywrightIcon,
  'mcp-chrome-devtools': ChromeDevToolsFallback,
  'mcp-browserbase': BrowserbaseFallback,

  // Computer Use
  'mcp-desktop-commander': DesktopCommanderIcon,
  'mcp-windows': WindowsMCPIcon,

  // Filesystem
  'mcp-filesystem': FilesystemIcon,

  // Code platforms
  'mcp-github': GitHubIcon,
  'mcp-gitlab': GitLabFallback,
  'mcp-cloudflare': CloudflareIcon,
  'mcp-sentry': SentryIcon,
  'mcp-vercel': VercelIcon,
  'mcp-netlify': NetlifyFallback,
  'mcp-jira': JiraFallback,

  // Communication
  'mcp-slack': SlackIcon,

  // Productivity
  'mcp-notion': NotionIcon,
  'mcp-linear': LinearIcon,
  'mcp-google-drive': GoogleDriveIcon,

  // Design
  'mcp-figma': FigmaIcon,

  // Data + Storage
  'mcp-postgres': PostgresIcon,
  'mcp-sqlite': SQLiteIcon,
  'mcp-mongodb': MongoDBFallback,
  'mcp-redis': RedisIcon,

  // Payment
  'mcp-stripe': StripeIcon,
  'mcp-shopify': ShopifyFallback,

  // Research
  'mcp-perplexity': PerplexityFallback,
  'mcp-huggingface': HuggingFaceIcon,

  // Dev tools
  'mcp-fetch': FetchFallback,
  'mcp-brave-search': BraveSearchIcon,
  'mcp-time': TimeFallback,
  'mcp-git': GitIcon,
  'mcp-memory': MemoryIcon,
  'mcp-sequential-thinking': SequentialThinkingFallback,

  // OAuth apps
  'app-gmail': GmailIcon,
  'app-google-calendar': GoogleCalendarIcon,
  'app-google-drive': GoogleDriveIcon,
  'app-github': GitHubIcon,
  'app-figma': FigmaIcon,
  'app-slack': SlackIcon,
  'app-canva': CanvaIcon,
  'app-notion-oauth': NotionIcon,
  'app-stripe-oauth': StripeIcon,
  'app-cloudflare-oauth': CloudflareIcon,
  'app-sentry-oauth': SentryIcon,
}

// ── Kind-based fallback (last-resort glyph) ──

const KIND_FALLBACK_ICON: Record<CatalogKind, ComponentType<BrandIconProps>> = {
  mcp_server: ({ size = 24, className }: BrandIconProps) => (
    <Server size={size} className={className || 'text-accent-cyan'} />
  ),
  oauth_app: ({ size = 24, className }: BrandIconProps) => (
    <AppWindow size={size} className={className || 'text-cyan-300'} />
  ),
  browser_tool: ({ size = 24, className }: BrandIconProps) => (
    <Globe size={size} className={className || 'text-sky-300'} />
  ),
  computer_use: ({ size = 24, className }: BrandIconProps) => (
    <Terminal size={size} className={className || 'text-rose-300'} />
  ),
  cli_runtime: ({ size = 24, className }: BrandIconProps) => (
    <Terminal size={size} className={className || 'text-amber-300'} />
  ),
  api_provider: ({ size = 24, className }: BrandIconProps) => (
    <Globe size={size} className={className || 'text-emerald-300'} />
  ),
  local_model: ({ size = 24, className }: BrandIconProps) => (
    <Cpu size={size} className={className || 'text-emerald-300'} />
  ),
  skill_pack: ({ size = 24, className }: BrandIconProps) => (
    <BookOpen size={size} className={className || 'text-violet-300'} />
  ),
}

/**
 * Get the icon component for a marketplace catalog entry.
 *
 * Resolution order:
 *   1. Explicit PLUGIN_ICON_MAP entry (catalog id -> brand icon)
 *   2. getMcpBrandIcon (mcp_server kind only, smart fallback by name)
 *   3. getBrandIcon (catalog-style brand lookup by display name)
 *   4. Kind-based fallback glyph from lucide-react
 */
export function pluginIconFor(
  catalogId: string,
  kind: CatalogKind,
  displayName?: string,
): PluginIcon {
  const explicit = PLUGIN_ICON_MAP[catalogId]
  if (explicit) return explicit

  if (kind === 'mcp_server') {
    return getMcpBrandIcon(catalogId)
  }

  if (displayName) {
    const slug = displayName.toLowerCase().replace(/\s+/g, '-')
    const brand = getBrandIcon(slug, 'connector')
    if (brand && brand !== getBrandIcon('___missing___', 'connector')) {
      return brand
    }
  }

  return KIND_FALLBACK_ICON[kind]
}

/** Tone hint for the icon background tile, derived from risk. */
export function pluginIconTone(risk: 'low' | 'medium' | 'high'): string {
  return risk === 'high'
    ? 'bg-rose-500/15'
    : risk === 'medium'
      ? 'bg-amber-500/10'
      : 'bg-cyan-500/10'
}
