/**
 * PoC artifact block. Renders inline on a finding detail card.
 * Different artifact kinds get different UX so a curl (copy-paste
 * ready) and a screenshot (image) do not look identical.
 */
import { Shield } from 'lucide-react'
import type { PocArtifactDict } from './types'

export default function PocArtifactBlock({ artifact }: { artifact: PocArtifactDict }) {
  const kindLabel: Record<string, string> = {
    curl: 'Reproducible curl PoC',
    http_pair: 'HTTP Request / Response transcript',
    screenshot: 'Browser screenshot',
    replay_script: 'Replay script (sandbox required)',
    package_reference: 'Package reference',
    diff_hunk: 'Source pattern',
    behavioral_trace: 'Behavioral trace',
  }
  const label = kindLabel[artifact.kind] ?? artifact.kind
  const isDestructive = artifact.destructive === true
  const isImage = artifact.kind === 'screenshot'
  const hasContent = typeof artifact.content === 'string' && artifact.content.length > 0

  return (
    <div className={`mt-2 p-3 rounded-lg border ${
      isDestructive
        ? 'bg-status-error/5 border-status-error/30'
        : 'bg-primary-500/5 border-primary-500/25'
    }`}>
      <div className="flex items-center justify-between mb-1 gap-2">
        <p className="text-[10px] uppercase tracking-wider font-semibold flex items-center gap-1">
          <Shield size={10} className={isDestructive ? 'text-status-error' : 'text-primary-400'} />
          <span className={isDestructive ? 'text-status-error' : 'text-primary-400'}>
            {label}
          </span>
        </p>
        <div className="flex items-center gap-1 text-[9px] text-starlight-500 font-mono">
          <span>sha256: {artifact.sha256.slice(0, 12)}...</span>
          {isDestructive && (
            <span className="text-status-error ml-1" title="Destructive artifact">⚠</span>
          )}
          {artifact.reproducible && !isDestructive && (
            <span className="text-status-success ml-1" title="Reproducible">✓</span>
          )}
        </div>
      </div>

      {hasContent && !isImage && artifact.content_encoding !== 'base64' && (
        <pre className="text-xs text-starlight-300 bg-midnight-400/60 p-2 rounded overflow-x-auto font-mono whitespace-pre-wrap max-h-64">
          {artifact.content}
        </pre>
      )}

      {hasContent && isImage && artifact.content_encoding === 'base64' && (
        // Cap inline base64 images at ~512KB so a giant screenshot doesn't
        // tank the page. Larger artifacts get a click-to-load fallback.
        (artifact.content && artifact.content.length < 700_000) ? (
          <img
            src={`data:${artifact.content_type};base64,${artifact.content}`}
            alt={artifact.description || 'PoC screenshot'}
            className="rounded max-h-64 mt-1"
          />
        ) : (
          <details className="mt-1">
            <summary className="text-[11px] text-primary-400 cursor-pointer hover:text-primary-300">
              Large screenshot ({Math.round((artifact.content?.length || 0) / 1024)} KB) — click to load inline
            </summary>
            <img
              src={`data:${artifact.content_type};base64,${artifact.content}`}
              alt={artifact.description || 'PoC screenshot'}
              className="rounded max-h-64 mt-2"
            />
          </details>
        )
      )}

      {!hasContent && (
        <p className="text-[11px] text-starlight-500 italic">
          Artifact vaulted; content not embedded in report response.
        </p>
      )}

      {artifact.description && (
        <p className="text-[11px] text-starlight-400 mt-2">{artifact.description}</p>
      )}
    </div>
  )
}
