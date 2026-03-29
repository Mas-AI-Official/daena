/**
 * Brand icons for connectors, runtimes, and extensions.
 * Uses SimpleIcons CDN for official brand SVGs with correct colors.
 * Fallback to Lucide icons if CDN fails.
 */

import { memo } from 'react'
import {
  Activity,
  BookOpen,
  Bot,
  Brain,
  Calendar,
  Chrome,
  Cloud,
  Code,
  CreditCard,
  Database,
  FileText,
  Folder,
  GitBranch,
  Globe,
  HardDrive,
  Heart,
  Layout,
  Mail,
  MessageSquare,
  Mic,
  Monitor,
  Palette,
  Search,
  Server,
  Shield,
  Terminal,
  Users,
  Zap,
} from 'lucide-react'

// ── CDN-based brand icons ──

interface BrandIconProps {
  size?: number
  className?: string
}

function CdnIcon({ name, color, size = 24, className = '' }: BrandIconProps & { name: string; color: string }) {
  return (
    <img
      src={`https://cdn.simpleicons.org/${name}/${color}`}
      alt={name}
      width={size}
      height={size}
      className={className}
      loading="lazy"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
    />
  )
}

// ── Connector Icons ──

export const GoogleDriveIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="googledrive" color="4285F4" size={size} className={className} />
))
GoogleDriveIcon.displayName = 'GoogleDriveIcon'

export const GitHubIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="github" color="ffffff" size={size} className={className} />
))
GitHubIcon.displayName = 'GitHubIcon'

export const FigmaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="figma" color="F24E1E" size={size} className={className} />
))
FigmaIcon.displayName = 'FigmaIcon'

export const GmailIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="gmail" color="EA4335" size={size} className={className} />
))
GmailIcon.displayName = 'GmailIcon'

export const GoogleCalendarIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="googlecalendar" color="4285F4" size={size} className={className} />
))
GoogleCalendarIcon.displayName = 'GoogleCalendarIcon'

export const HuggingFaceIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="huggingface" color="FFD21E" size={size} className={className} />
))
HuggingFaceIcon.displayName = 'HuggingFaceIcon'

export const NotionIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="notion" color="ffffff" size={size} className={className} />
))
NotionIcon.displayName = 'NotionIcon'

export const SlackIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="slack" color="4A154B" size={size} className={className} />
))
SlackIcon.displayName = 'SlackIcon'

export const CanvaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="canva" color="00C4CC" size={size} className={className} />
))
CanvaIcon.displayName = 'CanvaIcon'

export const PayPalIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="paypal" color="003087" size={size} className={className} />
))
PayPalIcon.displayName = 'PayPalIcon'

export const StripeIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="stripe" color="635BFF" size={size} className={className} />
))
StripeIcon.displayName = 'StripeIcon'

export const AtlassianIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="atlassian" color="0052CC" size={size} className={className} />
))
AtlassianIcon.displayName = 'AtlassianIcon'

export const LinearIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="linear" color="5E6AD2" size={size} className={className} />
))
LinearIcon.displayName = 'LinearIcon'

export const IntercomIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="intercom" color="6AFDEF" size={size} className={className} />
))
IntercomIcon.displayName = 'IntercomIcon'

// ── Runtime Icons ──

export const AnthropicIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="anthropic" color="D4A373" size={size} className={className} />
))
AnthropicIcon.displayName = 'AnthropicIcon'

export const OpenAIIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="openai" color="ffffff" size={size} className={className} />
))
OpenAIIcon.displayName = 'OpenAIIcon'

export const OllamaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="ollama" color="ffffff" size={size} className={className} />
))
OllamaIcon.displayName = 'OllamaIcon'

export const GoogleGeminiIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="googlegemini" color="8E75B2" size={size} className={className} />
))
GoogleGeminiIcon.displayName = 'GoogleGeminiIcon'

export const XAIIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="x" color="ffffff" size={size} className={className} />
))
XAIIcon.displayName = 'XAIIcon'

// ── Extension Icons (fallback to Lucide) ──

export const FilesystemIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Folder size={size} className={className || 'text-accent-amber'} />
))
FilesystemIcon.displayName = 'FilesystemIcon'

export const DesktopCommanderIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Terminal size={size} className={className || 'text-accent-cyan'} />
))
DesktopCommanderIcon.displayName = 'DesktopCommanderIcon'

export const WindowsMCPIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Monitor size={size} className={className || 'text-primary-400'} />
))
WindowsMCPIcon.displayName = 'WindowsMCPIcon'

export const ElevenLabsIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Mic size={size} className={className || 'text-accent-purple'} />
))
ElevenLabsIcon.displayName = 'ElevenLabsIcon'

export const PDFToolsIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <FileText size={size} className={className || 'text-accent-red'} />
))
PDFToolsIcon.displayName = 'PDFToolsIcon'

// Additional extension/connector icons using Lucide
export const BraveSearchIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="brave" color="FB542B" size={size} className={className} />
))
BraveSearchIcon.displayName = 'BraveSearchIcon'

export const PuppeteerIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Chrome size={size} className={className || 'text-green-400'} />
))
PuppeteerIcon.displayName = 'PuppeteerIcon'

export const PlaywrightIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Chrome size={size} className={className || 'text-emerald-400'} />
))
PlaywrightIcon.displayName = 'PlaywrightIcon'

export const PostgresIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="postgresql" color="4169E1" size={size} className={className} />
))
PostgresIcon.displayName = 'PostgresIcon'

export const SQLiteIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="sqlite" color="003B57" size={size} className={className} />
))
SQLiteIcon.displayName = 'SQLiteIcon'

export const RedisIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="redis" color="FF4438" size={size} className={className} />
))
RedisIcon.displayName = 'RedisIcon'

export const SentryIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="sentry" color="362D59" size={size} className={className} />
))
SentryIcon.displayName = 'SentryIcon'

export const MemoryIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Brain size={size} className={className || 'text-violet-400'} />
))
MemoryIcon.displayName = 'MemoryIcon'

export const GitIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="git" color="F05032" size={size} className={className} />
))
GitIcon.displayName = 'GitIcon'

// Connector icons that were missing
export const MondayIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="monday" color="FF3D57" size={size} className={className} />
))
MondayIcon.displayName = 'MondayIcon'

export const AsanaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="asana" color="F06A6A" size={size} className={className} />
))
AsanaIcon.displayName = 'AsanaIcon'

export const AirtableIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="airtable" color="18BFFF" size={size} className={className} />
))
AirtableIcon.displayName = 'AirtableIcon'

export const DropboxIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="dropbox" color="0061FF" size={size} className={className} />
))
DropboxIcon.displayName = 'DropboxIcon'

export const BoxIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="box" color="0061D5" size={size} className={className} />
))
BoxIcon.displayName = 'BoxIcon'

export const WordPressIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="wordpress" color="21759B" size={size} className={className} />
))
WordPressIcon.displayName = 'WordPressIcon'

export const ClickUpIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="clickup" color="7B68EE" size={size} className={className} />
))
ClickUpIcon.displayName = 'ClickUpIcon'

export const BasecampIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="basecamp" color="1D2D35" size={size} className={className} />
))
BasecampIcon.displayName = 'BasecampIcon'

export const SalesforceIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="salesforce" color="00A1E0" size={size} className={className} />
))
SalesforceIcon.displayName = 'SalesforceIcon'

export const HubSpotIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="hubspot" color="FF7A59" size={size} className={className} />
))
HubSpotIcon.displayName = 'HubSpotIcon'

export const CloudflareIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="cloudflare" color="F38020" size={size} className={className} />
))
CloudflareIcon.displayName = 'CloudflareIcon'

export const VercelIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="vercel" color="ffffff" size={size} className={className} />
))
VercelIcon.displayName = 'VercelIcon'

export const AmplitudeIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="amplitude" color="0060FF" size={size} className={className} />
))
AmplitudeIcon.displayName = 'AmplitudeIcon'

export const SnowflakeIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="snowflake" color="29B5E8" size={size} className={className} />
))
SnowflakeIcon.displayName = 'SnowflakeIcon'

export const ZapierIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="zapier" color="FF4F00" size={size} className={className} />
))
ZapierIcon.displayName = 'ZapierIcon'

export const SquareIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="square" color="3E4348" size={size} className={className} />
))
SquareIcon.displayName = 'SquareIcon'

export const MicrosoftTeamsIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CdnIcon name="microsoftteams" color="6264A7" size={size} className={className} />
))
MicrosoftTeamsIcon.displayName = 'MicrosoftTeamsIcon'

export const ClayIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Users size={size} className={className || 'text-indigo-400'} />
))
ClayIcon.displayName = 'ClayIcon'

export const PlaidIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <CreditCard size={size} className={className || 'text-green-400'} />
))
PlaidIcon.displayName = 'PlaidIcon'

export const GammaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Layout size={size} className={className || 'text-purple-400'} />
))
GammaIcon.displayName = 'GammaIcon'

export const GranolaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <BookOpen size={size} className={className || 'text-amber-400'} />
))
GranolaIcon.displayName = 'GranolaIcon'

export const AppleHealthIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Heart size={size} className={className || 'text-red-400'} />
))
AppleHealthIcon.displayName = 'AppleHealthIcon'

export const PubMedIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <BookOpen size={size} className={className || 'text-blue-400'} />
))
PubMedIcon.displayName = 'PubMedIcon'

export const HexIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Activity size={size} className={className || 'text-pink-400'} />
))
HexIcon.displayName = 'HexIcon'

// ── Icon Registry (lookup by name) ──

export const CONNECTOR_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
  // New connectors added for Browse modal
  'monday': MondayIcon,
  'monday.com': MondayIcon,
  'asana': AsanaIcon,
  'airtable': AirtableIcon,
  'dropbox': DropboxIcon,
  'box': BoxIcon,
  'wordpress': WordPressIcon,
  'wordpress.com': WordPressIcon,
  'clickup': ClickUpIcon,
  'basecamp': BasecampIcon,
  'salesforce': SalesforceIcon,
  'hubspot': HubSpotIcon,
  'cloudflare': CloudflareIcon,
  'vercel': VercelIcon,
  'amplitude': AmplitudeIcon,
  'snowflake': SnowflakeIcon,
  'zapier': ZapierIcon,
  'square': SquareIcon,
  'microsoft-teams': MicrosoftTeamsIcon,
  'clay': ClayIcon,
  'plaid': PlaidIcon,
  'gamma': GammaIcon,
  'granola': GranolaIcon,
  'apple-health': AppleHealthIcon,
  'pubmed': PubMedIcon,
  'hex': HexIcon,
  'sentry': SentryIcon,
  'google-drive': GoogleDriveIcon,
  'github': GitHubIcon,
  'figma': FigmaIcon,
  'gmail': GmailIcon,
  'google-calendar': GoogleCalendarIcon,
  'hugging-face': HuggingFaceIcon,
  'notion': NotionIcon,
  'slack': SlackIcon,
  'canva': CanvaIcon,
  'paypal': PayPalIcon,
  'stripe': StripeIcon,
  'atlassian': AtlassianIcon,
  'linear': LinearIcon,
  'intercom': IntercomIcon,
}

export const RUNTIME_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
  'claude_code': AnthropicIcon,
  'codex': OpenAIIcon,
  'ollama': OllamaIcon,
  'gemini_cli': GoogleGeminiIcon,
  'grok_cli': XAIIcon,
}

export const EXTENSION_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
  'filesystem': FilesystemIcon,
  'figma': FigmaIcon,
  'figma-mcp': FigmaIcon,
  'windows-mcp': WindowsMCPIcon,
  'elevenlabs': ElevenLabsIcon,
  'elevenlabs-agents-mcp-app': ElevenLabsIcon,
  'pdf-tools': PDFToolsIcon,
  'pdf-tools---fill-analyze-extract-view': PDFToolsIcon,
  'desktop-commander': DesktopCommanderIcon,
  'brave-search': BraveSearchIcon,
  'puppeteer': PuppeteerIcon,
  'playwright': PlaywrightIcon,
  'postgres': PostgresIcon,
  'postgresql': PostgresIcon,
  'sqlite': SQLiteIcon,
  'redis': RedisIcon,
  'sentry': SentryIcon,
  'sentry-mcp': SentryIcon,
  'memory': MemoryIcon,
  'git': GitIcon,
}

/** Get the right icon for a connector/runtime/extension by name. */
export function getBrandIcon(
  name: string,
  category: 'connector' | 'runtime' | 'extension' = 'connector',
): React.ComponentType<BrandIconProps> {
  const slug = name.toLowerCase().replace(/[\s_]+/g, '-').replace(/[()]/g, '')
  const registry = category === 'runtime' ? RUNTIME_ICONS
    : category === 'extension' ? EXTENSION_ICONS
    : CONNECTOR_ICONS
  return registry[slug] || (() => <Globe size={24} className="text-starlight-400" />)
}
