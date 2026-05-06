/**
 * VPCommandCard — renders the structured response from /api/v1/vp-commands.
 *
 * Sprint-MORNING PR-1: when the chat preflight matches a VP-work command
 * (review drafts, enrich, QE review, create workstream from draft, next
 * steps, which department), MessageBubble renders this card instead of
 * the LLM markdown stream. Pure read-only render -- no actions fire from
 * inside the card; the operator copies an id and re-issues the command,
 * or follows the deep-link to Workstreams / Drafts.
 */
import { Link } from 'react-router-dom'
import {
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ListChecks,
  Brain,
  Users,
  Workflow,
  Building2,
  ArrowRight,
} from 'lucide-react'
import type { VPCommandResult } from '@/types/api'

interface VPCommandCardProps {
  result: VPCommandResult
}

interface DraftRow {
  id?: string
  kind?: string
  goal?: string
  source_host?: string
  status?: string
}

interface WorkstreamRow {
  id?: string
  next_step_text?: string | null
  source_type?: string | null
  source_ref_id?: string | null
}

const INTENT_ICON: Record<string, typeof Brain> = {
  review_drafts: ListChecks,
  next_steps: Workflow,
  enrich_draft: Brain,
  qe_review_draft: Users,
  create_workstream_from_draft: Workflow,
  which_department: Building2,
  unrecognized: HelpCircle,
}

const INTENT_LABEL: Record<string, string> = {
  review_drafts: 'Review drafts',
  next_steps: 'What is next',
  enrich_draft: 'Enrich draft',
  qe_review_draft: 'Council review',
  create_workstream_from_draft: 'Create workstream',
  which_department: 'Department routing',
  unrecognized: 'Did not understand',
}

function shortId(id?: string | null): string {
  if (!id) return ''
  return id.length > 8 ? id.slice(0, 8) : id
}

export function VPCommandCard({ result }: VPCommandCardProps) {
  const Icon = INTENT_ICON[result.intent] ?? HelpCircle
  const label = INTENT_LABEL[result.intent] ?? result.intent

  // Pill state: green=success, amber=needs_disambiguation, red=refusal/unrecognized.
  const pillState: 'ok' | 'ask' | 'refuse' = result.success
    ? 'ok'
    : result.needs_disambiguation
      ? 'ask'
      : 'refuse'

  const pillClass =
    pillState === 'ok'
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : pillState === 'ask'
        ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
        : 'bg-rose-500/15 text-rose-300 border-rose-500/30'

  const PillIcon = pillState === 'ok' ? CheckCircle2 : pillState === 'ask' ? HelpCircle : AlertCircle
  const pillText =
    pillState === 'ok'
      ? 'Done'
      : pillState === 'ask'
        ? 'Need a draft id'
        : result.intent === 'unrecognized'
          ? 'Unrecognized'
          : 'Refused'

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-primary-400" />
          <span className="text-sm font-medium text-starlight-100">{label}</span>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${pillClass}`}
        >
          <PillIcon size={11} />
          {pillText}
        </span>
      </div>

      <p className="mt-2 text-sm text-starlight-200">{result.summary}</p>

      <VPCommandBody result={result} />

      {result.next_action && (
        <div className="mt-3 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
          <span className="font-medium">Next:</span> {result.next_action}
        </div>
      )}
    </div>
  )
}

function VPCommandBody({ result }: { result: VPCommandResult }) {
  const data = result.data || {}

  if (result.intent === 'review_drafts') {
    const research = (data.research_drafts as DraftRow[] | undefined) ?? []
    const forms = (data.form_drafts as DraftRow[] | undefined) ?? []
    if (research.length === 0 && forms.length === 0) {
      return (
        <p className="mt-2 text-xs text-starlight-400">
          No drafts yet. Run the scraper or create a draft from the Drafts lane.
        </p>
      )
    }
    return (
      <div className="mt-3 space-y-2">
        {research.length > 0 && (
          <DraftList title="Research drafts" rows={research} kindHint="research" />
        )}
        {forms.length > 0 && (
          <DraftList title="Form drafts" rows={forms} kindHint="form" />
        )}
      </div>
    )
  }

  if (result.intent === 'next_steps') {
    const open = (data.open_workstreams as WorkstreamRow[] | undefined) ?? []
    if (open.length === 0) {
      return (
        <p className="mt-2 text-xs text-starlight-400">
          No open workstreams. Promote a draft to a work plan first.
        </p>
      )
    }
    return (
      <ul className="mt-3 space-y-1.5">
        {open.slice(0, 5).map((ws) => (
          <li key={ws.id ?? Math.random()} className="flex items-center justify-between gap-2 text-xs">
            <span className="truncate text-starlight-200">
              {ws.next_step_text || '(no next step yet)'}
            </span>
            <Link
              to="/workstreams"
              className="inline-flex items-center gap-1 text-primary-300 hover:text-primary-200"
            >
              {shortId(ws.id)}
              <ArrowRight size={11} />
            </Link>
          </li>
        ))}
      </ul>
    )
  }

  if (result.intent === 'create_workstream_from_draft' && result.success) {
    const id = data.id as string | undefined
    const nextStep = data.next_step_text as string | undefined
    return (
      <div className="mt-3 flex items-center justify-between gap-3 rounded-md bg-slate-800/40 px-3 py-2 text-xs">
        <div>
          <div className="text-starlight-300">Workstream</div>
          <div className="font-mono text-starlight-100">{shortId(id)}</div>
          {nextStep && <div className="mt-1 text-starlight-400">Next: {nextStep}</div>}
        </div>
        <Link
          to="/workstreams"
          className="inline-flex items-center gap-1 rounded border border-primary-500/30 bg-primary-500/10 px-2 py-1 text-primary-300 hover:bg-primary-500/20"
        >
          Open
          <ArrowRight size={11} />
        </Link>
      </div>
    )
  }

  if (result.intent === 'which_department') {
    const dept = data.department as string | undefined
    const reason = data.reason as string | undefined
    if (!dept) return null
    return (
      <div className="mt-3 rounded-md bg-slate-800/40 px-3 py-2 text-xs text-starlight-200">
        Routes to <span className="font-medium text-primary-300">{dept}</span>
        {reason && <span className="text-starlight-400"> ({reason})</span>}
      </div>
    )
  }

  if (result.intent === 'qe_review_draft') {
    const mode = data.mode as string | undefined
    const reviewers = data.reviewers as string[] | undefined
    if (!mode) return null
    return (
      <div className="mt-3 rounded-md bg-slate-800/40 px-3 py-2 text-xs text-starlight-200">
        <div>Mode: <span className="font-medium text-primary-300">{mode}</span></div>
        {reviewers && reviewers.length > 0 && (
          <div className="mt-1 text-starlight-400">
            Reviewers: {reviewers.join(', ')}
          </div>
        )}
      </div>
    )
  }

  if (result.intent === 'enrich_draft' && !result.success) {
    const code = data.refusal_code as string | undefined
    if (!code) return null
    return (
      <div className="mt-3 rounded-md bg-slate-800/40 px-3 py-2 text-xs text-starlight-300">
        Refusal code: <span className="font-mono text-rose-300">{code}</span>
      </div>
    )
  }

  return null
}

function DraftList({
  title,
  rows,
  kindHint,
}: {
  title: string
  rows: DraftRow[]
  kindHint: 'research' | 'form'
}) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-starlight-500">
        {title}
      </div>
      <ul className="space-y-1">
        {rows.slice(0, 5).map((r) => (
          <li key={r.id ?? Math.random()} className="flex items-center justify-between gap-2 text-xs">
            <span className="truncate text-starlight-200">
              {r.goal || r.source_host || '(untitled)'}
            </span>
            <Link
              to={kindHint === 'research' ? '/research' : '/form-drafts'}
              className="font-mono text-[11px] text-primary-300 hover:text-primary-200"
            >
              {shortId(r.id)}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default VPCommandCard
