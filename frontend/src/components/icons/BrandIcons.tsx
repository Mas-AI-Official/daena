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

export interface BrandIconProps {
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
      onError={(e) => {
        // Fallback: show first letter as icon instead of hiding
        const img = e.target as HTMLImageElement
        const parent = img.parentElement
        if (parent) {
          const fallback = document.createElement('span')
          fallback.textContent = name.charAt(0).toUpperCase()
          fallback.style.cssText = `display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:6px;background:#${color}33;color:#${color};font-weight:700;font-size:${Math.round(size * 0.5)}px;`
          fallback.className = className
          parent.replaceChild(fallback, img)
        }
      }}
    />
  )
}

export function BrandAvatarIcon({
  label,
  size = 24,
  className = '',
}: BrandIconProps & { label: string }) {
  const cleaned = label.replace(/[^a-zA-Z0-9 ]/g, ' ').trim()
  const words = cleaned.split(/\s+/).filter(Boolean)
  const initials = (words.length >= 2 ? `${words[0][0]}${words[1][0]}` : cleaned.slice(0, 2) || '?').toUpperCase()
  let hash = 0
  for (const ch of label) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  const colors = ['2DD4BF', 'D4A843', '60A5FA', 'A78BFA', '34D399', 'F97316', 'F43F5E']
  const color = colors[hash % colors.length]
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        borderRadius: 6,
        background: `#${color}22`,
        color: `#${color}`,
        border: `1px solid #${color}55`,
        fontWeight: 700,
        fontSize: Math.max(9, Math.round(size * 0.42)),
        lineHeight: 1,
      }}
    >
      {initials}
    </span>
  )
}

function simpleIcon(slug: string, color: string): React.ComponentType<BrandIconProps> {
  const Icon = memo(({ size = 24, className }: BrandIconProps) => (
    <CdnIcon name={slug} color={color} size={size} className={className} />
  ))
  Icon.displayName = `SimpleIcon_${slug}`
  return Icon
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.122 2.521a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.268 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zm-2.523 10.122a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.268a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
  </svg>
))
SlackIcon.displayName = 'SlackIcon'

export const CanvaIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.884 14.14c-.346 1.49-1.453 2.78-3.114 3.632-1.65.847-3.641 1.145-5.539.793-1.894-.35-3.449-1.29-4.476-2.63C3.733 14.601 3.3 12.95 3.5 11.35c.203-1.62 1.05-3.06 2.394-4.063C7.233 6.29 8.92 5.82 10.62 5.95c.9.07 1.77.32 2.54.73.37.2.49.66.27 1.02-.22.37-.7.49-1.07.28a4.88 4.88 0 0 0-1.75-.5c-1.26-.1-2.54.24-3.56.96-1.02.73-1.69 1.82-1.84 3.08-.15 1.22.18 2.48.96 3.51.78 1.02 1.98 1.74 3.44 2.01 1.45.27 2.99.04 4.29-.61 1.28-.65 2.14-1.63 2.37-2.63.1-.42.54-.68.96-.58.42.1.68.54.58.96z" fill="#00C4CC"/>
  </svg>
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor"/>
  </svg>
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M2.6 18.4a2.6 2.6 0 1 1 0-5.2c.6 0 1.2.2 1.6.6l3-5.6c-.2-.4-.4-.9-.4-1.4a2.6 2.6 0 0 1 5.2 0c0 .5-.2 1-.4 1.4l3 5.6c.4-.3 1-.6 1.6-.6a2.6 2.6 0 0 1 0 5.2c-1 0-1.8-.5-2.2-1.3l-3.4-6.4c-.4.2-.9.3-1.4.3s-1-.1-1.4-.3L4.8 17c-.4.8-1.3 1.4-2.2 1.4zm18.8 0a2.6 2.6 0 1 1 0-5.2 2.6 2.6 0 0 1 0 5.2z" fill="#FF3D57"/>
  </svg>
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M10 3.2c.9-1 2.2-1.5 3.5-1.5 1.7 0 3.2.9 4 2.3.7-.3 1.5-.5 2.3-.5 3.1 0 5.5 2.5 5.5 5.5 0 3.1-2.4 5.5-5.5 5.5-.5 0-.9-.1-1.4-.2-.7 1.4-2.2 2.4-3.9 2.4-1 0-1.9-.3-2.6-.9-.8 1.5-2.4 2.5-4.2 2.5-2.2 0-4-1.4-4.6-3.4C1.3 14.7 0 13.2 0 11.3c0-2.2 1.6-3.9 3.7-4.2C4.4 5.1 6 3.7 8 3.7c.7 0 1.4.2 2 .5V3.2z" fill="#00A1E0"/>
  </svg>
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M12 2L2 19.5h4.5L12 8.5l5.5 11H22L12 2z" fill="#0060FF"/>
  </svg>
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
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
    <path d="M20.5 5.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm2.5 2h-5a1 1 0 0 0-1 1v5.5a3.5 3.5 0 0 0 7 0V8.5a1 1 0 0 0-1-1zM13 6H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2zm-2.5 8.5h-3V11H6v3.5H5v-5h5.5v5zM16 20.5c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2v-1h14v1z" fill="#6264A7"/>
  </svg>
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

export const NeonPostgresIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Database size={size} className={className || 'text-emerald-400'} />
))
NeonPostgresIcon.displayName = 'NeonPostgresIcon'

export const QuicknodeIcon = memo(({ size = 24, className }: BrandIconProps) => (
  <Server size={size} className={className || 'text-blue-400'} />
))
QuicknodeIcon.displayName = 'QuicknodeIcon'

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
  'neon': NeonPostgresIcon,
  'neon-postgres': NeonPostgresIcon,
  'quicknode': QuicknodeIcon,
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

const CONNECTOR_SIMPLE_ICON_ALIASES: Record<string, { slug: string; color: string }> = {
  'netlify': { slug: 'netlify', color: '00C7B7' },
  'circleci': { slug: 'circleci', color: '343434' },
  'expo': { slug: 'expo', color: 'ffffff' },
  'coderabbit': { slug: 'coderabbit', color: 'FF570A' },
  'neon-postgres': { slug: 'neon', color: '00E599' },
  'cloudinary': { slug: 'cloudinary', color: '3448C5' },
  'hostinger': { slug: 'hostinger', color: '673DE6' },
  'quicknode': { slug: 'quicknode', color: '2D5BFF' },
  'render': { slug: 'render', color: '46E3B7' },
  'remotion': { slug: 'remotion', color: 'ffffff' },
  'google-calendar': { slug: 'googlecalendar', color: '4285F4' },
  'google-drive': { slug: 'googledrive', color: '4285F4' },
  'outlook-email': { slug: 'microsoftoutlook', color: '0078D4' },
  'outlook-calendar': { slug: 'microsoftoutlook', color: '0078D4' },
  'sharepoint': { slug: 'microsoftsharepoint', color: '038387' },
  'teams': { slug: 'microsoftteams', color: '6264A7' },
  'jam': { slug: 'jamstack', color: 'F0047F' },
  'attio': { slug: 'attio', color: 'ffffff' },
  'brex': { slug: 'brex', color: '212121' },
  'carta-crm': { slug: 'carta', color: '00A9E0' },
  'clickup': { slug: 'clickup', color: '7B68EE' },
  'coupler.io': { slug: 'coupler', color: '4D7CFE' },
  'dovetail': { slug: 'dovetail', color: '190041' },
  'egnyte': { slug: 'egnyte', color: '00968F' },
  'fireflies': { slug: 'fireflyiii', color: 'CD5029' },
  'help-scout': { slug: 'helpscout', color: '1292EE' },
  'hubspot': { slug: 'hubspot', color: 'FF7A59' },
  'monday.com': { slug: 'mondaydotcom', color: 'FF3D57' },
  'pipedrive': { slug: 'pipedrive', color: '017737' },
  'razorpay': { slug: 'razorpay', color: '0C2451' },
  'semrush': { slug: 'semrush', color: 'FF642D' },
  'signnow': { slug: 'signnow', color: '2F80ED' },
  'teamwork.com': { slug: 'teamwork', color: '6A61FF' },
  'binance': { slug: 'binance', color: 'F0B90B' },
  'moody-s': { slug: 'moodys', color: '005AA0' },
  'morningstar': { slug: 'morningstar', color: 'E31B23' },
  'paypal': { slug: 'paypal', color: '003087' },
  'intercom': { slug: 'intercom', color: '6AFDEF' },
  'vercel': { slug: 'vercel', color: 'ffffff' },
  'cloudflare': { slug: 'cloudflare', color: 'F38020' },
  'sentry': { slug: 'sentry', color: '362D59' },
  'stripe': { slug: 'stripe', color: '635BFF' },
  'amplitude': { slug: 'amplitude', color: '0060FF' },
  'box': { slug: 'box', color: '0061D5' },
  'notion': { slug: 'notion', color: 'ffffff' },
  'figma': { slug: 'figma', color: 'F24E1E' },
  'canva': { slug: 'canva', color: '00C4CC' },
  'github': { slug: 'github', color: 'ffffff' },
  'gmail': { slug: 'gmail', color: 'EA4335' },
  'slack': { slug: 'slack', color: '4A154B' },
  'hugging-face': { slug: 'huggingface', color: 'FFD21E' },
  'linear': { slug: 'linear', color: '5E6AD2' },
}

const DYNAMIC_CONNECTOR_ICONS: Record<string, React.ComponentType<BrandIconProps>> =
  Object.fromEntries(
    Object.entries(CONNECTOR_SIMPLE_ICON_ALIASES).map(([key, value]) => [
      key,
      simpleIcon(value.slug, value.color),
    ]),
  ) as Record<string, React.ComponentType<BrandIconProps>>

export const RUNTIME_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
  'claude_code': AnthropicIcon,
  'codex': OpenAIIcon,
  'ollama': OllamaIcon,
  'gemini_cli': GoogleGeminiIcon,
  'grok_cli': XAIIcon,
}

// Additional CdnIcon-backed extensions added 2026-04-16 for the
// Extensions modal which previously showed generic puzzle pieces
// for every popular MCP. Each entry below is a SimpleIcons slug
// + the brand's primary hex color. CdnIcon handles fallback to
// a branded letter avatar if the CDN is unreachable.
const GoogleSheetsExtIcon = memo(() => <CdnIcon name="googlesheets" color="34A853" size={24} />)
const GoogleDocsExtIcon = memo(() => <CdnIcon name="googledocs" color="4285F4" size={24} />)
const ObsidianExtIcon = memo(() => <CdnIcon name="obsidian" color="7C3AED" size={24} />)
const TodoistExtIcon = memo(() => <CdnIcon name="todoist" color="E44332" size={24} />)
const RaycastExtIcon = memo(() => <CdnIcon name="raycast" color="FF6363" size={24} />)
const JupyterExtIcon = memo(() => <CdnIcon name="jupyter" color="F37626" size={24} />)
const SalesforceExtIcon = memo(() => <CdnIcon name="salesforce" color="00A1E0" size={24} />)
const HubSpotExtIcon = memo(() => <CdnIcon name="hubspot" color="FF7A59" size={24} />)
const ApolloExtIcon = memo(() => <CdnIcon name="apollographql" color="311C87" size={24} />)
const DbtExtIcon = memo(() => <CdnIcon name="dbt" color="FF694A" size={24} />)
const AmplitudeExtIcon = memo(() => <CdnIcon name="amplitude" color="1E61F0" size={24} />)
const MixpanelExtIcon = memo(() => <CdnIcon name="mixpanel" color="7856FF" size={24} />)
const LinearExtIcon = memo(() => <CdnIcon name="linear" color="5E6AD2" size={24} />)
const IntercomExtIcon = memo(() => <CdnIcon name="intercom" color="1F8DED" size={24} />)
const AsanaExtIcon = memo(() => <CdnIcon name="asana" color="F06A6A" size={24} />)
const AirtableExtIcon = memo(() => <CdnIcon name="airtable" color="18BFFF" size={24} />)
const ZapierExtIcon = memo(() => <CdnIcon name="zapier" color="FF4A00" size={24} />)
const StripeExtIcon = memo(() => <CdnIcon name="stripe" color="635BFF" size={24} />)
const VercelExtIcon = memo(() => <CdnIcon name="vercel" color="ffffff" size={24} />)
const SupabaseExtIcon = memo(() => <CdnIcon name="supabase" color="3ECF8E" size={24} />)
const FirebaseExtIcon = memo(() => <CdnIcon name="firebase" color="FFCA28" size={24} />)
const MongoDBExtIcon = memo(() => <CdnIcon name="mongodb" color="47A248" size={24} />)
const OpenAIExtIcon = memo(() => <CdnIcon name="openai" color="ffffff" size={24} />)
const AnthropicExtIcon = memo(() => <CdnIcon name="anthropic" color="D97757" size={24} />)
const HuggingFaceExtIcon = memo(() => <CdnIcon name="huggingface" color="FFD21E" size={24} />)
const PineconeExtIcon = memo(() => <CdnIcon name="pinecone" color="1C7ED6" size={24} />)

export const EXTENSION_ICONS: Record<string, React.ComponentType<BrandIconProps>> = {
  // --- File & infra ---
  'filesystem': FilesystemIcon,
  'memory': MemoryIcon,
  'git': GitIcon,
  'postgres': PostgresIcon,
  'postgresql': PostgresIcon,
  'sqlite': SQLiteIcon,
  'redis': RedisIcon,
  'mongodb-mcp': MongoDBExtIcon,
  // --- Browser / automation ---
  'puppeteer': PuppeteerIcon,
  'playwright': PlaywrightIcon,
  'brave-search': BraveSearchIcon,
  'desktop-commander': DesktopCommanderIcon,
  'windows-mcp': WindowsMCPIcon,
  // --- Design ---
  'figma': FigmaIcon,
  'figma-mcp': FigmaIcon,
  // --- Voice / media ---
  'elevenlabs': ElevenLabsIcon,
  'elevenlabs-agents-mcp-app': ElevenLabsIcon,
  'pdf-tools': PDFToolsIcon,
  'pdf-tools---fill-analyze-extract-view': PDFToolsIcon,
  // --- Monitoring ---
  'sentry': SentryIcon,
  'sentry-mcp': SentryIcon,
  // --- Google Workspace ---
  'google-drive-mcp': GoogleDriveIcon,
  'google-calendar-mcp': GoogleCalendarIcon,
  'google-sheets-mcp': GoogleSheetsExtIcon,
  'google-docs-mcp': GoogleDocsExtIcon,
  'gmail-mcp': GmailIcon,
  // --- Productivity ---
  'notion-mcp': NotionIcon,
  'obsidian-mcp': ObsidianExtIcon,
  'todoist-mcp': TodoistExtIcon,
  'raycast-mcp': RaycastExtIcon,
  'linear-mcp': LinearExtIcon,
  'asana-mcp': AsanaExtIcon,
  'airtable-mcp': AirtableExtIcon,
  // --- Data / analytics ---
  'jupyter-mcp': JupyterExtIcon,
  'dbt-mcp': DbtExtIcon,
  'amplitude-mcp': AmplitudeExtIcon,
  'mixpanel-mcp': MixpanelExtIcon,
  // --- CRM / sales ---
  'salesforce-mcp': SalesforceExtIcon,
  'hubspot-mcp': HubSpotExtIcon,
  'apollo-mcp': ApolloExtIcon,
  'intercom-mcp': IntercomExtIcon,
  // --- Comms ---
  'slack-mcp': SlackIcon,
  // --- Dev platforms ---
  'github-mcp': GitHubIcon,
  'vercel-mcp': VercelExtIcon,
  'supabase-mcp': SupabaseExtIcon,
  'firebase-mcp': FirebaseExtIcon,
  'stripe-mcp': StripeExtIcon,
  'zapier-mcp': ZapierExtIcon,
  // --- AI / ML ---
  'openai-mcp': OpenAIExtIcon,
  'anthropic-mcp': AnthropicExtIcon,
  'huggingface-mcp': HuggingFaceExtIcon,
  'pinecone-mcp': PineconeExtIcon,
}

/** Get the right icon for a connector/runtime/extension by name. */
export function getBrandIcon(
  name: string,
  category: 'connector' | 'runtime' | 'extension' = 'connector',
): React.ComponentType<BrandIconProps> {
  const slug = name
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const registry = category === 'runtime' ? RUNTIME_ICONS
    : category === 'extension' ? EXTENSION_ICONS
    : CONNECTOR_ICONS
  if (registry[slug]) return registry[slug]
  if (category === 'connector' && DYNAMIC_CONNECTOR_ICONS[slug]) return DYNAMIC_CONNECTOR_ICONS[slug]
  return ({ size = 24, className }: BrandIconProps) => (
    <BrandAvatarIcon label={name} size={size} className={className} />
  )
}

/**
 * Resolve a brand icon for an MCP server_key like Daena's bootstrap
 * registry produces them: ``mcp-google-drive``, ``mcp-github``,
 * ``gitnexus``, ``chrome-devtools``, ``mcp_docker``, etc.
 *
 * The base ``getBrandIcon('foo', 'extension')`` only matches the exact
 * registered slug. MCP keys come from the npm package name, the
 * filename of the wrapper, or the user's freeform "name" field — they
 * don't follow one convention. So we try a series of normalised
 * candidates and return the first match. Missing ones fall back to a
 * generic server icon (NOT the world Globe used by getBrandIcon, which
 * implies "external connector" — wrong for a local MCP).
 */
export function getMcpBrandIcon(server_key: string): React.ComponentType<BrandIconProps> {
  const lower = server_key.toLowerCase().replace(/_/g, '-')
  const candidates: string[] = []

  // 1. Exact match.
  candidates.push(lower)
  // 2. Strip leading mcp- / -mcp suffix (most common shapes).
  const noLeading = lower.replace(/^mcp-/, '')
  const noTrailing = lower.replace(/-mcp$/, '')
  candidates.push(noLeading, noTrailing)
  // 3. Try with -mcp suffix (the registry above mostly stores ext keys
  //    with -mcp at the end: 'google-drive-mcp', 'gmail-mcp', ...).
  candidates.push(`${noLeading.replace(/-mcp$/, '')}-mcp`)
  // 4. Some MCPs are namespaced like '@cocal/google-calendar-mcp' —
  //    pick the last segment after the slash.
  const slashIdx = lower.lastIndexOf('/')
  if (slashIdx >= 0) {
    const tail = lower.slice(slashIdx + 1).replace(/^@/, '')
    candidates.push(tail, tail.replace(/^mcp-/, ''), tail.replace(/-mcp$/, ''), `${tail.replace(/-mcp$/, '')}-mcp`)
  }
  // 5. Try the connector registry too (some MCPs share names with
  //    OAuth connectors: gmail, github, notion, slack, ...).
  for (const cand of candidates) {
    if (EXTENSION_ICONS[cand]) return EXTENSION_ICONS[cand]
  }
  for (const cand of candidates) {
    if (CONNECTOR_ICONS[cand]) return CONNECTOR_ICONS[cand]
  }
  // 6. Final fallback: generic server icon, not the world Globe.
  return () => <Server size={24} className="text-accent-cyan" />
}
