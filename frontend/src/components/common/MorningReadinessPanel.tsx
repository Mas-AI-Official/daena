/**
 * MorningReadinessPanel — Sprint-MORNING PR-4.
 *
 * Single-call read-only panel that surfaces the operator's morning
 * setup state: CLI runtimes ready, local LLMs reachable, API keys
 * present (boolean only — never values), MCPs detected in other CLIs,
 * and any blockers.
 *
 * Backend contract: GET /api/v1/system/morning-readiness.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Copy,
  Wrench,
  ExternalLink,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

interface BucketItem {
  id: string
  display_name: string
  readiness_state: string
  cost_class: string
  detected: boolean
  configured: boolean
  callable: boolean
  endpoint: string | null
  next_action: string | null
}

interface BucketSummary {
  total: number
  ready: number
  items: BucketItem[]
}

interface DetectedMCP {
  name: string
  from_cli: string
  command: string
}

interface AutofixProposal {
  id: string
  title: string
  rationale: string
  copy_command: string | null
  deep_link: string | null
  severity: 'info' | 'warn' | 'blocker'
}

interface MorningReadinessData {
  cli_runtimes: BucketSummary
  local_llms: BucketSummary
  api_providers: BucketSummary
  detected_mcps: {
    total: number
    items: DetectedMCP[]
    scan_error: string | null
  }
  blockers: string[]
  autofix_proposals: AutofixProposal[]
  ready_for_morning_work: boolean
}

const COST_CLASS_TONE: Record<string, string> = {
  free_local: 'text-emerald-300',
  subscription: 'text-sky-300',
  metered_api: 'text-amber-300',
  unknown: 'text-starlight-400',
}

const READINESS_LABEL: Record<string, string> = {
  ready: 'Ready',
  configured_untested: 'Configured (untested)',
  not_configured: 'Not configured',
  detected_offline: 'Detected (offline)',
  unknown: 'Unknown',
}

function StateDot({ state }: { state: string }) {
  const tone =
    state === 'ready'
      ? 'bg-emerald-400'
      : state === 'configured_untested'
        ? 'bg-sky-400'
        : state === 'detected_offline'
          ? 'bg-amber-400'
          : 'bg-rose-400'
  return <span className={`inline-block w-2 h-2 rounded-full ${tone}`} />
}

export function MorningReadinessPanel() {
  const [data, setData] = useState<MorningReadinessData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/system/morning-readiness', {
        params: refresh ? { refresh: true } : undefined,
        silent: true,
      })
      setData(res.data?.data ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(false)
  }, [load])

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-bold text-starlight-100">
            Ecosystem Readiness
          </div>
          <div className="text-[11px] text-starlight-500">
            CLI runtimes, local LLMs, API keys, detected MCPs. Read-only —
            secrets are never read or rendered.
          </div>
        </div>
        <button
          onClick={() => void load(true)}
          disabled={loading}
          className="inline-flex items-center gap-1 text-[11px] text-starlight-400 hover:text-starlight-100 disabled:opacity-40 cursor-pointer"
        >
          {loading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
          Refresh
        </button>
      </div>

      {error && (
        <div className="text-[11px] text-amber-300">Failed to load: {error}</div>
      )}

      {data && (
        <>
          <ReadyHeadline data={data} />
          <Bucket title="CLI Runtimes" bucket={data.cli_runtimes} />
          <Bucket title="Local LLMs" bucket={data.local_llms} />
          <Bucket title="API Providers" bucket={data.api_providers} keyHint />
          <DetectedMCPs detected={data.detected_mcps} />
          {data.blockers.length > 0 && <Blockers items={data.blockers} />}
          {data.autofix_proposals.length > 0 && (
            <AutofixProposals proposals={data.autofix_proposals} />
          )}
        </>
      )}
    </div>
  )
}

function ReadyHeadline({ data }: { data: MorningReadinessData }) {
  const ready = data.ready_for_morning_work
  return (
    <div
      className={`inline-flex items-center gap-2 px-2 py-1 rounded text-xs ${
        ready
          ? 'bg-emerald-500/10 text-emerald-200 border border-emerald-500/30'
          : 'bg-rose-500/10 text-rose-200 border border-rose-500/30'
      }`}
    >
      {ready ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
      {ready ? 'Ready for VP work' : 'Not yet ready — see blockers below'}
    </div>
  )
}

function Bucket({
  title,
  bucket,
  keyHint = false,
}: {
  title: string
  bucket: BucketSummary
  keyHint?: boolean
}) {
  if (bucket.total === 0) {
    return (
      <div>
        <div className="text-[11px] text-starlight-300 font-medium">{title}</div>
        <div className="text-[10px] text-starlight-500 italic">
          None detected.
        </div>
      </div>
    )
  }
  return (
    <div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-starlight-300 font-medium">{title}</span>
        <span className="text-starlight-500">
          {bucket.ready} / {bucket.total} ready
        </span>
      </div>
      <ul className="mt-1 space-y-0.5">
        {bucket.items.map((item) => (
          <li
            key={item.id}
            className="flex items-center gap-2 text-[11px] text-starlight-200"
          >
            <StateDot state={item.readiness_state} />
            <span className="truncate flex-1">{item.display_name}</span>
            {keyHint && (
              <span className="text-[10px] text-starlight-500">
                {item.configured ? 'key set' : 'no key'}
              </span>
            )}
            <span
              className={`text-[10px] ${COST_CLASS_TONE[item.cost_class] ?? 'text-starlight-400'}`}
            >
              {READINESS_LABEL[item.readiness_state] ?? item.readiness_state}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function DetectedMCPs({
  detected,
}: {
  detected: { total: number; items: DetectedMCP[]; scan_error: string | null }
}) {
  if (detected.scan_error) {
    return (
      <div>
        <div className="text-[11px] text-starlight-300 font-medium">
          Detected MCPs (other CLIs)
        </div>
        <div className="text-[10px] text-amber-300">
          Scan failed: {detected.scan_error}
        </div>
      </div>
    )
  }
  if (detected.total === 0) {
    return (
      <div>
        <div className="text-[11px] text-starlight-300 font-medium">
          Detected MCPs (other CLIs)
        </div>
        <div className="text-[10px] text-starlight-500 italic">
          None found in Claude Code / Codex / Gemini configs.
        </div>
      </div>
    )
  }
  return (
    <div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-starlight-300 font-medium">
          Detected MCPs (other CLIs)
        </span>
        <span className="text-starlight-500">{detected.total} found</span>
      </div>
      <ul className="mt-1 space-y-0.5">
        {detected.items.map((m) => (
          <li
            key={`${m.from_cli}:${m.name}`}
            className="flex items-center gap-2 text-[11px] text-starlight-200"
          >
            <span className="font-mono text-[10px] text-starlight-500">
              {m.from_cli}
            </span>
            <span className="truncate flex-1">{m.name}</span>
            <span className="font-mono text-[10px] text-starlight-500">
              {m.command}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-1 text-[10px] text-starlight-500 italic">
        Visit the Connections page to import these into Daena (governance gate runs).
      </div>
    </div>
  )
}

function Blockers({ items }: { items: string[] }) {
  return (
    <div className="rounded-md border border-rose-500/30 bg-rose-500/[0.04] p-2">
      <div className="text-[11px] font-semibold text-rose-200 mb-1">
        Blockers
      </div>
      <ul className="space-y-0.5">
        {items.map((b, i) => (
          <li
            key={i}
            className="text-[11px] text-rose-200/90 flex items-start gap-2"
          >
            <AlertCircle size={11} className="mt-0.5 shrink-0" />
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function AutofixProposals({ proposals }: { proposals: AutofixProposal[] }) {
  const onCopy = async (cmd: string) => {
    try {
      await navigator.clipboard.writeText(cmd)
      toast.success('Command copied')
    } catch {
      toast.error('Copy failed; select and copy manually')
    }
  }
  return (
    <div className="rounded-md border border-primary-500/20 bg-primary-500/[0.04] p-2">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-primary-200 mb-1">
        <Wrench size={11} />
        Autofix proposals
        <span className="text-[10px] font-normal text-starlight-400 ml-1">
          (Daena suggests; you decide what runs)
        </span>
      </div>
      <ul className="space-y-1.5">
        {proposals.map((p) => (
          <li
            key={p.id}
            className="rounded bg-slate-900/40 px-2 py-1.5 text-[11px] text-starlight-200"
          >
            <div className="font-medium">{p.title}</div>
            <div className="mt-0.5 text-[10px] text-starlight-400">
              {p.rationale}
            </div>
            <div className="mt-1 flex items-center gap-2">
              {p.copy_command && (
                <>
                  <code className="flex-1 truncate font-mono text-[10px] bg-black/30 rounded px-1.5 py-0.5 text-accent-cyan">
                    {p.copy_command}
                  </code>
                  <button
                    type="button"
                    onClick={() => void onCopy(p.copy_command!)}
                    className="inline-flex items-center gap-1 rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-starlight-300 hover:bg-white/5 cursor-pointer"
                  >
                    <Copy size={10} />
                    Copy
                  </button>
                </>
              )}
              {p.deep_link && (
                <Link
                  to={p.deep_link}
                  className="inline-flex items-center gap-1 rounded border border-primary-500/30 px-1.5 py-0.5 text-[10px] text-primary-300 hover:bg-primary-500/10 ml-auto"
                >
                  Open
                  <ExternalLink size={10} />
                </Link>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default MorningReadinessPanel
