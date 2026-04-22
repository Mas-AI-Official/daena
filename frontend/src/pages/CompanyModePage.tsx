/**
 * CompanyModePage -- Activate Daena as an AI marketing+sales agency.
 *
 * Founder-only page. Takes a brief (company one-liner, ICP, pain, promise,
 * proof, channels, prospect limit, tone) and kicks POST /company-mode/activate.
 * The backend produces prospect list + first-touch drafts across Sales/
 * Marketing Minds. Drafts land in approval queue by default; auto-send is
 * opt-in and warns loudly for LinkedIn (ToS risk).
 *
 * Layout:
 *   - Activation form (left, sticky on wide screens)
 *   - Latest activation result + history ring buffer (right)
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Rocket,
  Plus,
  X,
  AlertTriangle,
  Mail,
  Linkedin,
  MessageSquare,
  Phone,
  Globe,
  MessagesSquare,
  CheckCircle2,
  ShieldCheck,
  Clock,
  Building,
  Download,
  Save,
  Send,
  ChevronRight,
  Copy,
  ExternalLink,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Input, Switch, EmptyState, Shimmer, Modal } from '@/components/common'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/stores/toastStore'
import type {
  ActivateRequest,
  ActivationResult,
  ActivationMission,
  ActivationHistoryEntry,
  MissionChannel,
  Draft,
  DraftStatus,
  SeedBriefResponse,
  SendOutcome,
} from '@/types/api'

// Channel presentation (icon + short label + ToS risk flag).
const CHANNELS: {
  key: MissionChannel
  label: string
  icon: React.ReactNode
  risk?: 'tos' | 'friction'
}[] = [
  { key: 'email',      label: 'Email',      icon: <Mail size={14} /> },
  { key: 'linkedin',   label: 'LinkedIn',   icon: <Linkedin size={14} />, risk: 'tos' },
  { key: 'twitter_dm', label: 'Twitter DM', icon: <MessagesSquare size={14} /> },
  { key: 'sms',        label: 'SMS',        icon: <MessageSquare size={14} />, risk: 'friction' },
  { key: 'web_form',   label: 'Web form',   icon: <Globe size={14} /> },
  { key: 'phone',      label: 'Phone',      icon: <Phone size={14} />, risk: 'friction' },
]

const TONE_OPTIONS = ['warm-direct', 'curious', 'sharp-pitch', 'founder-to-founder', 'technical']

function blankRequest(): ActivateRequest {
  return {
    company_name: '',
    company_one_liner: '',
    target_customer: '',
    customer_pain: '',
    our_promise: '',
    proof_points: [''],
    channels: ['email', 'linkedin'],
    prospect_limit_per_mission: 10,
    tone: 'warm-direct',
    auto_send: false,
    require_founder_approval: true,
    notes: '',
  }
}

export function CompanyModePage() {
  usePageTitle('Company Mode')
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isFounder = user?.role === 'FOUNDER'

  const [req, setReq] = useState<ActivateRequest>(blankRequest)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ActivationResult | null>(null)
  const [history, setHistory] = useState<ActivationHistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)

  // Seed brief quick-fill state. The founder can stash a "go-to" brief on
  // the backend and reload it with one click. We load the stash on mount
  // but never auto-apply -- user must click "Load seed" explicitly.
  const [seedBrief, setSeedBrief] = useState<ActivateRequest | null>(null)
  const [seedExists, setSeedExists] = useState(false)
  const [seedUpdatedAt, setSeedUpdatedAt] = useState<string | null>(null)
  const [seedSaving, setSeedSaving] = useState(false)

  useEffect(() => {
    if (!isFounder) return
    let cancelled = false
    const load = async () => {
      try {
        const { data } = await api.get<ActivationHistoryEntry[]>('/company-mode/activations?limit=20')
        if (!cancelled) setHistory(data ?? [])
      } catch (err) {
        console.error('Failed to load activation history:', err)
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    }
    const loadSeed = async () => {
      try {
        const { data } = await api.get<SeedBriefResponse>('/company-mode/seed-brief')
        if (cancelled) return
        if (data?.exists && data.brief) {
          setSeedBrief(data.brief)
          setSeedExists(true)
          setSeedUpdatedAt(data.updated_at)
        }
      } catch (err) {
        // 404 is fine -- no seed yet. Only log real errors.
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status && status !== 404) {
          console.error('Failed to load seed brief:', err)
        }
      }
    }
    void load()
    void loadSeed()
    return () => {
      cancelled = true
    }
  }, [isFounder])

  // Validation mirrors the Pydantic bounds on ActivateRequest.
  const errors = useMemo(() => {
    const e: Partial<Record<keyof ActivateRequest, string>> = {}
    if (req.company_name.trim().length < 1) e.company_name = 'Required'
    if (req.company_one_liner.trim().length < 3) e.company_one_liner = 'At least 3 chars'
    if (req.target_customer.trim().length < 3) e.target_customer = 'At least 3 chars'
    if (req.customer_pain.trim().length < 3) e.customer_pain = 'At least 3 chars'
    if (req.our_promise.trim().length < 3) e.our_promise = 'At least 3 chars'
    if (req.channels.length === 0) e.channels = 'Pick at least one channel'
    if (req.prospect_limit_per_mission < 1 || req.prospect_limit_per_mission > 50)
      e.prospect_limit_per_mission = '1-50 prospects'
    return e
  }, [req])

  const canSubmit = Object.keys(errors).length === 0 && !submitting
  const canSaveSeed = Object.keys(errors).length === 0 && !seedSaving

  // Apply the loaded seed into the form. We deep-copy arrays so later edits
  // do not mutate the stashed seed.
  const applySeed = () => {
    if (!seedBrief) return
    setReq({
      ...seedBrief,
      proof_points: seedBrief.proof_points.length > 0 ? [...seedBrief.proof_points] : [''],
      channels: [...seedBrief.channels],
    })
    toast.success('Seed brief loaded')
  }

  const saveSeed = async () => {
    if (!canSaveSeed) return
    setSeedSaving(true)
    try {
      const payload: ActivateRequest = {
        ...req,
        company_name: req.company_name.trim(),
        company_one_liner: req.company_one_liner.trim(),
        target_customer: req.target_customer.trim(),
        customer_pain: req.customer_pain.trim(),
        our_promise: req.our_promise.trim(),
        proof_points: req.proof_points.map((p) => p.trim()).filter(Boolean),
        notes: req.notes?.trim() || null,
      }
      const { data } = await api.post<{ exists: boolean; updated_at: string }>(
        '/company-mode/seed-brief',
        payload,
      )
      setSeedBrief(payload)
      setSeedExists(true)
      setSeedUpdatedAt(data?.updated_at ?? new Date().toISOString())
      toast.success('Seed brief saved')
    } catch (err) {
      console.error('save seed failed:', err)
      toast.error('Could not save seed brief')
    } finally {
      setSeedSaving(false)
    }
  }

  const toggleChannel = (channel: MissionChannel) => {
    setReq((prev) => {
      const has = prev.channels.includes(channel)
      return { ...prev, channels: has ? prev.channels.filter((c) => c !== channel) : [...prev.channels, channel] }
    })
  }

  const setProof = (idx: number, value: string) => {
    setReq((prev) => {
      const next = [...prev.proof_points]
      next[idx] = value
      return { ...prev, proof_points: next }
    })
  }

  const addProof = () => {
    setReq((prev) => ({ ...prev, proof_points: [...prev.proof_points, ''].slice(0, 10) }))
  }

  const removeProof = (idx: number) => {
    setReq((prev) => ({ ...prev, proof_points: prev.proof_points.filter((_, i) => i !== idx) }))
  }

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setResult(null)
    try {
      const payload: ActivateRequest = {
        ...req,
        company_name: req.company_name.trim(),
        company_one_liner: req.company_one_liner.trim(),
        target_customer: req.target_customer.trim(),
        customer_pain: req.customer_pain.trim(),
        our_promise: req.our_promise.trim(),
        proof_points: req.proof_points.map((p) => p.trim()).filter(Boolean),
        notes: req.notes?.trim() || null,
      }
      const { data } = await api.post<ActivationResult>('/company-mode/activate', payload)
      setResult(data)
      if (data.governance_warning) {
        toast.warning(data.governance_warning)
      } else {
        toast.success(
          `Activated. ${data.missions.length} missions, ${data.prospects_count} prospects, ${data.missions.reduce((n, m) => n + m.drafts_generated, 0)} drafts.`,
        )
      }
      // Refresh history ring buffer so the left rail shows this run.
      const hist = await api.get<ActivationHistoryEntry[]>('/company-mode/activations?limit=20')
      setHistory(hist.data ?? [])
    } catch (err: unknown) {
      console.error('activation failed:', err)
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Activation failed. See server logs.'
      toast.error(String(msg))
    } finally {
      setSubmitting(false)
    }
  }

  if (!isFounder) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <EmptyState
            icon={<ShieldCheck size={32} />}
            title="Founder-only area"
            description="Company Mode activation is restricted to the FOUNDER tier. Ask the workspace owner to run it."
            action={
              <Button variant="outline" size="sm" onClick={() => navigate('/departments')}>
                Go to Departments
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex flex-wrap items-center justify-between gap-3"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
              <Rocket size={22} className="text-primary-400" /> Company Mode
            </h1>
            <p className="text-sm text-starlight-400">
              Activate Daena to run autonomous GTM: prospect, draft, queue for approval.
              Sending is never unattended unless you opt in.
            </p>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: activation form */}
          <div className="lg:col-span-2 space-y-4">
            <Card variant="glass" padding="md">
              <div className="space-y-4">
                {/* Seed brief quick-fill row. "Load seed" needs a stashed brief
                    on the backend; "Save current as seed" needs the form to
                    pass client-side validation (errors memo empty). */}
                <div className="flex flex-wrap items-center gap-2 pb-3 border-b border-white/5">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!seedExists}
                    onClick={applySeed}
                  >
                    <span className="flex items-center gap-1.5">
                      <Download size={12} /> Load seed
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!canSaveSeed}
                    isLoading={seedSaving}
                    onClick={saveSeed}
                  >
                    <span className="flex items-center gap-1.5">
                      <Save size={12} /> Save current as seed
                    </span>
                  </Button>
                  {seedExists && seedUpdatedAt && (
                    <span className="text-[10px] text-starlight-500">
                      Last saved: {formatRelativeTime(seedUpdatedAt)}
                    </span>
                  )}
                </div>
                <Input
                  label="Company name"
                  placeholder="e.g. MAS-AI Technologies Inc."
                  value={req.company_name}
                  onChange={(e) => setReq({ ...req, company_name: e.target.value })}
                  error={errors.company_name}
                />
                <Textarea
                  label="One-liner"
                  placeholder="Governed multi-agent LLM orchestration platform for regulated teams."
                  value={req.company_one_liner}
                  onChange={(v) => setReq({ ...req, company_one_liner: v })}
                  rows={2}
                  error={errors.company_one_liner}
                />
                <Textarea
                  label="Target customer (ICP)"
                  placeholder="VP Engineering at 200-2000 person B2B SaaS with compliance pressure (SOC2, HIPAA, FINRA)."
                  value={req.target_customer}
                  onChange={(v) => setReq({ ...req, target_customer: v })}
                  rows={2}
                  error={errors.target_customer}
                />
                <Textarea
                  label="Customer pain"
                  placeholder="LLM agents that act without audit trails; single-model lock-in; shadow AI from employees bypassing IT."
                  value={req.customer_pain}
                  onChange={(v) => setReq({ ...req, customer_pain: v })}
                  rows={2}
                  error={errors.customer_pain}
                />
                <Textarea
                  label="Our promise"
                  placeholder="Governance-first orchestration across any runtime. Approval queues, tamper-evident audit, Shield always on."
                  value={req.our_promise}
                  onChange={(v) => setReq({ ...req, our_promise: v })}
                  rows={2}
                  error={errors.our_promise}
                />

                {/* Proof points (dynamic list) */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-starlight-300">
                    Proof points ({req.proof_points.length}/10)
                  </label>
                  <div className="space-y-2">
                    {req.proof_points.map((p, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          className="glass-input text-starlight-100 text-sm placeholder:text-starlight-400 focus-ring transition-all duration-200 flex-1"
                          placeholder={`Proof ${idx + 1} (e.g. "2 USPTO provisionals: PhiLattice + NBMF")`}
                          value={p}
                          onChange={(e) => setProof(idx, e.target.value)}
                        />
                        {req.proof_points.length > 1 && (
                          <button
                            onClick={() => removeProof(idx)}
                            className="p-2 rounded-lg text-starlight-400 hover:text-status-error hover:bg-status-error/10 transition-colors cursor-pointer"
                            aria-label="Remove proof point"
                            type="button"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                    {req.proof_points.length < 10 && (
                      <button
                        onClick={addProof}
                        type="button"
                        className="flex items-center gap-2 text-xs text-primary-400 hover:text-primary-300 transition-colors cursor-pointer"
                      >
                        <Plus size={12} /> Add proof point
                      </button>
                    )}
                  </div>
                </div>

                {/* Channels */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-starlight-300">Channels</label>
                  <div className="flex flex-wrap gap-2">
                    {CHANNELS.map((ch) => {
                      const active = req.channels.includes(ch.key)
                      return (
                        <button
                          key={ch.key}
                          onClick={() => toggleChannel(ch.key)}
                          type="button"
                          className={`px-3 py-1.5 rounded-lg text-xs border transition-all flex items-center gap-1.5 cursor-pointer ${
                            active
                              ? 'bg-primary-500/20 border-primary-500/40 text-primary-300'
                              : 'bg-white/[0.02] border-white/5 text-starlight-400 hover:border-white/10 hover:text-starlight-200'
                          }`}
                          title={ch.risk === 'tos' ? 'Auto-send violates LinkedIn ToS' : undefined}
                        >
                          {ch.icon}
                          {ch.label}
                          {ch.risk === 'tos' && <AlertTriangle size={11} className="text-status-warning" />}
                        </button>
                      )
                    })}
                  </div>
                  {errors.channels && <p className="text-xs text-status-error">{errors.channels}</p>}
                </div>

                {/* Knobs: limit + tone */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    type="number"
                    label="Prospect limit per mission (1-50)"
                    min={1}
                    max={50}
                    value={req.prospect_limit_per_mission}
                    onChange={(e) =>
                      setReq({
                        ...req,
                        prospect_limit_per_mission: Math.max(1, Math.min(50, Number(e.target.value) || 1)),
                      })
                    }
                    error={errors.prospect_limit_per_mission}
                  />
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-medium text-starlight-300" htmlFor="tone">
                      Tone
                    </label>
                    <select
                      id="tone"
                      className="glass-input text-starlight-100 text-sm focus-ring transition-all duration-200"
                      value={req.tone}
                      onChange={(e) => setReq({ ...req, tone: e.target.value })}
                    >
                      {TONE_OPTIONS.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Switches: auto_send + require_founder_approval */}
                <div className="space-y-3 border-t border-white/5 pt-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-starlight-200">Require founder approval</p>
                      <p className="text-[11px] text-starlight-500">
                        Every outbound draft queues in /governance/approvals before it sends. Leave ON for safety.
                      </p>
                    </div>
                    <Switch
                      checked={req.require_founder_approval}
                      onChange={(v) => setReq({ ...req, require_founder_approval: v })}
                    />
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-starlight-200 flex items-center gap-1.5">
                        Auto-send
                        {req.channels.includes('linkedin') && req.auto_send && (
                          <AlertTriangle size={12} className="text-status-warning" />
                        )}
                      </p>
                      <p className="text-[11px] text-starlight-500">
                        Send drafts without a human click. On LinkedIn this violates ToS and can trigger account
                        suspension.
                      </p>
                    </div>
                    <Switch checked={req.auto_send} onChange={(v) => setReq({ ...req, auto_send: v })} />
                  </div>
                </div>

                <Textarea
                  label="Notes (optional)"
                  placeholder="Anything else Daena should know about this push?"
                  value={req.notes ?? ''}
                  onChange={(v) => setReq({ ...req, notes: v })}
                  rows={2}
                />

                <div className="flex items-center justify-between border-t border-white/5 pt-4">
                  <span className="text-[11px] text-starlight-500">
                    Drafts land in{' '}
                    <button
                      onClick={() => navigate('/governance/approvals')}
                      className="text-primary-400 hover:underline cursor-pointer"
                      type="button"
                    >
                      /governance/approvals
                    </button>
                    . Nothing sends until you click.
                  </span>
                  <Button variant="premium" size="md" isLoading={submitting} disabled={!canSubmit} onClick={submit}>
                    <span className="flex items-center gap-2">
                      <Rocket size={14} /> Activate Daena
                    </span>
                  </Button>
                </div>
              </div>
            </Card>

            {/* Latest activation result */}
            {result && <ActivationResultCard result={result} />}
          </div>

          {/* Right: history */}
          <div className="space-y-3">
            <h2 className="text-sm font-display font-semibold text-starlight-100">Recent activations</h2>
            {historyLoading ? (
              <Shimmer count={3} layout="list" />
            ) : history.length === 0 ? (
              <EmptyState
                icon={<Clock size={28} />}
                title="No activations yet"
                description="Run one using the form on the left."
              />
            ) : (
              history.map((h) => (
                <Card key={h.activation_id} variant="glass" padding="md">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Building size={14} className="text-starlight-400" />
                    <span className="text-xs font-medium text-starlight-100 truncate">{h.company_name}</span>
                  </div>
                  <p className="text-[11px] text-starlight-500 mb-2">{new Date(h.created_at).toLocaleString()}</p>
                  <div className="flex items-center gap-3 text-[10px] text-starlight-400">
                    <span>{h.prospects} prospects</span>
                    <span>·</span>
                    <span>{h.drafts} drafts</span>
                  </div>
                  {h.summary && (
                    <p className="mt-2 text-[11px] text-starlight-400 line-clamp-2" title={h.summary}>
                      {h.summary}
                    </p>
                  )}
                </Card>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── sub-components ─────────────────────────────────────────────────

function Textarea({
  label,
  placeholder,
  value,
  onChange,
  rows = 3,
  error,
}: {
  label: string
  placeholder?: string
  value: string
  onChange: (v: string) => void
  rows?: number
  error?: string
}) {
  const id = label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-starlight-300">
        {label}
      </label>
      <textarea
        id={id}
        rows={rows}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`glass-input text-starlight-100 text-sm placeholder:text-starlight-400 focus-ring transition-all duration-200 resize-y ${
          error ? 'border-status-error/50 focus:ring-status-error/50' : ''
        }`}
      />
      {error && <p className="text-xs text-status-error">{error}</p>}
    </div>
  )
}

function ActivationResultCard({ result }: { result: ActivationResult }) {
  const totalDrafts = result.missions.reduce((n, m) => n + m.drafts_generated, 0)
  const [openMission, setOpenMission] = useState<ActivationMission | null>(null)

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <Card variant="glass" padding="md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-status-success" />
            <h3 className="text-sm font-display font-semibold text-starlight-100">Activation complete</h3>
          </div>
          <Badge variant="default" size="sm">
            {result.activation_id.slice(0, 8)}
          </Badge>
        </div>
        {result.governance_warning && (
          <div className="mb-3 p-2.5 rounded-lg border border-status-warning/30 bg-status-warning/10 text-status-warning text-xs flex items-start gap-2">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            {result.governance_warning}
          </div>
        )}
        <div className="grid grid-cols-3 gap-3 mb-4 text-xs">
          <Stat label="Prospects" value={result.prospects_count} />
          <Stat label="Drafts generated" value={totalDrafts} />
          <Stat label="Missions" value={result.missions.length} />
        </div>
        {result.summary && (
          <p className="text-xs text-starlight-300 mb-4 whitespace-pre-wrap leading-relaxed">{result.summary}</p>
        )}

        <div className="space-y-2">
          {result.missions.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setOpenMission(m)}
              className="w-full flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/5 hover:border-white/10 hover:bg-white/[0.04] transition-all text-left cursor-pointer"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <Badge variant="default" size="sm">
                    {m.department}
                  </Badge>
                  <span className="text-[11px] text-starlight-300 font-medium">{m.mind}</span>
                  <span className="text-[10px] text-starlight-500 font-mono">{m.channel}</span>
                </div>
                <p className="text-[11px] text-starlight-400 truncate" title={m.objective}>
                  {m.objective}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-3">
                <div className="text-right text-[10px] text-starlight-400">
                  <div>{m.prospects_found} prospects</div>
                  <div>{m.drafts_generated} drafts</div>
                  {m.drafts_awaiting_approval > 0 && (
                    <div className="text-status-warning">{m.drafts_awaiting_approval} awaiting</div>
                  )}
                </div>
                <ChevronRight size={14} className="text-starlight-500" />
              </div>
            </button>
          ))}
        </div>

        {result.next_steps.length > 0 && (
          <div className="mt-4 pt-4 border-t border-white/5">
            <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500 mb-2">Next steps</div>
            <ul className="space-y-1 text-xs text-starlight-300 list-disc list-inside">
              {result.next_steps.slice(0, 6).map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <MissionDraftsModal mission={openMission} onClose={() => setOpenMission(null)} />
    </motion.div>
  )
}

// ── Mission drill-down modal ────────────────────────────────────────
// Lazily fetches drafts for a single mission and lets the founder send
// any draft that is still awaiting_approval. Status updates inline so
// the founder can triage a full mission without closing the modal.

const DRAFT_STATUS_VARIANT: Record<DraftStatus, 'default' | 'warning' | 'success' | 'danger' | 'info'> = {
  awaiting_approval: 'warning',
  sending: 'info',
  sent: 'success',
  failed: 'danger',
  blocked: 'danger',
}

function MissionDraftsModal({
  mission,
  onClose,
}: {
  mission: ActivationMission | null
  onClose: () => void
}) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [sendingId, setSendingId] = useState<string | null>(null)

  const isOpen = mission !== null
  const missionId = mission?.id ?? null

  const loadDrafts = useCallback(
    async (id: string) => {
      setLoading(true)
      try {
        const { data } = await api.get<Draft[]>(`/company-mode/missions/${id}/drafts`)
        setDrafts(data ?? [])
      } catch (err) {
        console.error('Failed to load drafts:', err)
        toast.error('Could not load drafts for this mission')
        setDrafts([])
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (!isOpen || !missionId) {
      setDrafts([])
      setExpanded({})
      return
    }
    void loadDrafts(missionId)
  }, [isOpen, missionId, loadDrafts])

  const sendDraft = async (draftId: string) => {
    if (!missionId || sendingId) return
    setSendingId(draftId)
    // Flip local status to sending so the UI reflects the in-flight state.
    setDrafts((prev) =>
      prev.map((d) => (d.draft_id === draftId ? { ...d, status: 'sending' as DraftStatus } : d)),
    )
    try {
      const { data } = await api.post<{ outcome: SendOutcome; draft: Draft }>(
        `/company-mode/missions/${missionId}/drafts/${draftId}/send`,
      )
      setDrafts((prev) => prev.map((d) => (d.draft_id === draftId ? data.draft : d)))
      if (data.outcome.status === 'sent') {
        toast.success('Draft sent')
      } else if (data.outcome.status === 'blocked') {
        toast.warning(data.outcome.detail ?? 'Send blocked by governance')
      } else {
        toast.error(data.outcome.detail ?? 'Send failed')
      }
    } catch (err) {
      console.error('send draft failed:', err)
      toast.error('Could not send draft')
      // Revert to awaiting_approval so the founder can retry.
      setDrafts((prev) =>
        prev.map((d) =>
          d.draft_id === draftId ? { ...d, status: 'awaiting_approval' as DraftStatus } : d,
        ),
      )
    } finally {
      setSendingId(null)
    }
  }

  const allHandled =
    drafts.length > 0 &&
    drafts.every((d) => d.status === 'sent' || d.status === 'blocked' || d.status === 'failed')

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg">
      {mission && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="default" size="sm">
              {mission.department}
            </Badge>
            <span className="text-sm text-starlight-100 font-medium">{mission.mind}</span>
            <span className="text-xs text-starlight-500 font-mono">{mission.channel}</span>
          </div>
          <p className="text-xs text-starlight-400">{mission.objective}</p>

          <div className="pt-3 border-t border-white/5">
            {loading ? (
              <Shimmer count={3} layout="list" />
            ) : drafts.length === 0 ? (
              <EmptyState
                icon={<Mail size={24} />}
                title="No drafts yet"
                description="This mission did not produce any drafts."
              />
            ) : (
              <div className="space-y-2">
                {drafts.map((d) => {
                  const variant = DRAFT_STATUS_VARIANT[d.status] ?? 'default'
                  const isExpanded = expanded[d.draft_id] === true
                  const canSend = d.status === 'awaiting_approval'
                  return (
                    <div
                      key={d.draft_id}
                      className="p-3 rounded-lg bg-white/[0.02] border border-white/5"
                    >
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <Badge variant={variant} size="sm">
                          {d.status.replace('_', ' ')}
                        </Badge>
                        <span className="text-[11px] text-starlight-300 truncate">{d.recipient}</span>
                        {d.sent_at && (
                          <span className="text-[10px] text-starlight-500">
                            {new Date(d.sent_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                      {d.subject && (
                        <p className="text-xs font-medium text-starlight-200 mb-1">{d.subject}</p>
                      )}
                      <button
                        type="button"
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [d.draft_id]: !isExpanded }))
                        }
                        className={`text-[11px] text-starlight-400 whitespace-pre-wrap text-left w-full cursor-pointer hover:text-starlight-300 transition-colors ${
                          isExpanded ? '' : 'line-clamp-3'
                        }`}
                      >
                        {d.body}
                      </button>
                      {d.error && (
                        <p className="mt-1.5 text-[10px] text-status-error">{d.error}</p>
                      )}
                      {canSend && (
                        <div className="mt-2 flex flex-wrap justify-end gap-2">
                          {d.channel === 'linkedin' ? (
                            // LinkedIn automated sending violates ToS (permanent
                            // account ban risk). The user-facing path is
                            // "Copy + Open LinkedIn": Daena writes the body to
                            // the clipboard and opens the LinkedIn messaging UI
                            // in a new tab so the founder can paste + send
                            // from their own browser session. Zero ToS risk.
                            // See docs/LINKEDIN_COMPLIANCE.md for the rationale.
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={async () => {
                                  const payload = d.subject
                                    ? `Subject: ${d.subject}\n\n${d.body}`
                                    : d.body
                                  try {
                                    await navigator.clipboard.writeText(payload)
                                    window.open('https://www.linkedin.com/messaging/', '_blank', 'noopener,noreferrer')
                                    toast.success('Body copied. Paste into LinkedIn and send from your own session.')
                                  } catch {
                                    toast.error('Could not copy to clipboard. Select + Ctrl+C manually.')
                                  }
                                }}
                                title="Copy message body + open LinkedIn messaging in a new tab. ToS-safe."
                              >
                                <span className="flex items-center gap-1.5">
                                  <Copy size={12} /> Copy + Open LinkedIn <ExternalLink size={11} />
                                </span>
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                isLoading={sendingId === d.draft_id}
                                disabled={sendingId !== null}
                                onClick={() => sendDraft(d.draft_id)}
                                title="Updates status -- Daena records that you handled this draft manually via LinkedIn. No automated send."
                              >
                                <span className="flex items-center gap-1.5 text-[11px]">
                                  Mark handled
                                </span>
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="premium"
                              size="sm"
                              isLoading={sendingId === d.draft_id}
                              disabled={sendingId !== null}
                              onClick={() => sendDraft(d.draft_id)}
                            >
                              <span className="flex items-center gap-1.5">
                                <Send size={12} /> Send draft
                              </span>
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            {allHandled && (
              <div className="mt-3 p-2 rounded-lg bg-status-success/10 border border-status-success/30 text-[11px] text-status-success flex items-center gap-1.5">
                <CheckCircle2 size={12} /> All drafts handled
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

// Human-readable relative time for the seed-brief footer. Keeps the UI
// readable without pulling date-fns.
function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'unknown'
  const diffMs = Date.now() - then
  const sec = Math.round(diffMs / 1000)
  if (sec < 60) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min} min ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr} hr ago`
  const days = Math.round(hr / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  return new Date(iso).toLocaleDateString()
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500">{label}</div>
      <div className="text-lg font-display font-semibold text-starlight-100">{value}</div>
    </div>
  )
}

export default CompanyModePage
