/**
 * Brand icons for connectors, runtimes, and extensions.
 * Uses SimpleIcons CDN for official brand SVGs with correct colors.
 * Fallback to Lucide icons if CDN fails.
 */

import { memo } from 'react'
import {
  Cloud,
  Code,
  FileText,
  Globe,
  HardDrive,
  Mail,
  MessageSquare,
  Monitor,
  Palette,
  Search,
  Terminal,
  Zap,
  Calendar,
  BookOpen,
  CreditCard,
  Folder,
  Mic,
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
  <CdnIcon name="openai" color="412991" size={size} className={className} />
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

// ── Icon Registry (lookup by name) ──

export const CONNECTOR_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
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
  'windows-mcp': WindowsMCPIcon,
  'elevenlabs': ElevenLabsIcon,
  'elevenlabs-agents-mcp-app': ElevenLabsIcon,
  'pdf-tools': PDFToolsIcon,
  'pdf-tools---fill-analyze-extract-view': PDFToolsIcon,
  'desktop-commander': DesktopCommanderIcon,
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
