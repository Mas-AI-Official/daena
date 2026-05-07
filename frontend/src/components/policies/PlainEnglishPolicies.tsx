/**
 * PlainEnglishPolicies -- Phase 2 F8 (2026-04-24).
 *
 * The user authors governance rules in natural English. The backend
 * /api/v1/policies/compile endpoint translates each rule to a
 * structured policy (trigger / condition / action / enforcement_mode /
 * tier) via Claude CLI. The user reviews the compiled YAML, edits any
 * field if desired, and saves. SecurityGate watches the on-disk YAML
 * pack and reloads on change so saves take effect without a restart.
 *
 * Effect chains for every interactive element:
 *
 *   [Compile now]:
 *     -> POST /api/v1/policies/compile {plain_english, name_hint}
 *     -> backend invokes Claude CLI with strict JSON schema
 *     -> response renders compiled YAML preview + reasoning + confidence
 *     -> [Save policy] becomes enabled
 *     -> audit: 'policy.compiled' (in backend) with prompt + result
 *
 *   [Save policy]:
 *     -> POST /api/v1/policies {name, plain_english, ...compiled fields}
 *     -> YAML written to backend/app/config/policies/<tenant>/<id>.yaml
 *     -> SecurityGate file-watcher fires reload on next eval
 *     -> list refreshes
 *     -> audit: 'policy.created'
 *     -> toast "Policy saved. Active immediately."
 *
 *   [Toggle enabled]:
 *     -> PUT /api/v1/policies/{id} {enabled: bool}
 *     -> version bump + on-disk rewrite
 *     -> SecurityGate sees new state on next eval
 *     -> audit: 'policy.toggled'
 *
 *   [Delete]:
 *     -> confirmDialog -> DELETE /api/v1/policies/{id}
 *     -> file removed from disk + cache
 *     -> audit: 'policy.deleted'
 *
 *   [Load defaults]:
 *     -> POST /api/v1/policies/seeds/load
 *     -> idempotent: skips names that already exist
 *     -> list refreshes
 *     -> toast "Loaded N seed policies, skipped M duplicates"
 *
 * Empty / loading / error states all render explicit copy so the user
 * is never staring at a blank pane.
 */

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Loader2,
  Plus,
  RotateCw,
  Save,
  Sparkles,
  Trash2,
  Wand2,
} from 'lucide-react'

import { Card } from '@/components/common'
import { api } from '@/lib/api'
import { confirmDialog } from '@/stores/confirmStore'
import { toast } from '@/stores/toastStore'

// ── Types ────────────────────────────────────────────────────

type PolicyAction = 'BLOCK' | 'APPROVE' | 'LOG' | 'REDACT' | 'REQUIRE_APPROVAL'
type PolicyEnforcement = 'ALWAYS' | 'BALANCED_ONLY' | 'GOVERNED_ONLY'

interface CompiledPreview {
  name: string
  plain_english: string
  trigger: string
  condition: string
  action: PolicyAction
  enforcement_mode: PolicyEnforcement
  governance_tier: number
  confidence: number
  reasoning: string
  matched_intents: string[]
  compiled_by: string
  compiled_yaml: string
}

interface SavedPolicy extends CompiledPreview {
  id: string
  enabled: boolean
  version: number
  created_at: string
  compiled_at: string
  notes: string
}

interface PolicyListResponse {
  data: SavedPolicy[]
  meta: { count: number }
}

const ACTION_COLORS: Record<PolicyAction, string> = {
  BLOCK: 'text-accent-red bg-accent-red/10 border-accent-red/30',
  REQUIRE_APPROVAL: 'text-accent-amber bg-accent-amber/10 border-accent-amber/30',
  APPROVE: 'text-accent-green bg-accent-green/10 border-accent-green/30',
  REDACT: 'text-accent-purple bg-accent-purple/10 border-accent-purple/30',
  LOG: 'text-starlight-300 bg-white/5 border-white/10',
}

const TIER_LABELS = ['0 · log', '1 · auto-proceed', '2 · ack', '3 · approval', '4 · block by default']

// ── Component ────────────────────────────────────────────────

export function PlainEnglishPolicies() {
  const [policies, setPolicies] = useState<SavedPolicy[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [seeding, setSeeding] = useState(false)

  // Composer state
  const [plainEnglish, setPlainEnglish] = useState('')
  const [nameHint, setNameHint] = useState('')
  const [compiling, setCompiling] = useState(false)
  const [compiled, setCompiled] = useState<CompiledPreview | null>(null)
  const [compileError, setCompileError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Selected policy for inspection
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selected = useMemo(
    () => policies.find((p) => p.id === selectedId) ?? null,
    [policies, selectedId],
  )

  const loadPolicies = async () => {
    setLoadError(null)
    try {
      const { data } = await api.get<PolicyListResponse>('/policies')
      setPolicies(data?.data ?? [])
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setPolicies([])
      } else {
        setLoadError('Could not load policies. Try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPolicies()
  }, [])

  // Effect chain: Compile now
  const handleCompile = async () => {
    if (!plainEnglish.trim() || plainEnglish.trim().length < 3) {
      toast.error('Write at least one sentence describing the rule.')
      return
    }
    setCompiling(true)
    setCompileError(null)
    setCompiled(null)
    try {
      const { data } = await api.post<CompiledPreview>('/policies/compile', {
        plain_english: plainEnglish.trim(),
        name_hint: nameHint.trim(),
      })
      setCompiled(data)
    } catch (err) {
      console.error('Compile failed:', err)
      setCompileError(
        'Compiler is unavailable right now (Claude CLI may need refresh). Heuristic fallback may still work next time.',
      )
    } finally {
      setCompiling(false)
    }
  }

  // Effect chain: Save policy
  const handleSave = async () => {
    if (!compiled) return
    setSaving(true)
    try {
      const { data } = await api.post<SavedPolicy>('/policies', {
        name: compiled.name,
        plain_english: compiled.plain_english,
        trigger: compiled.trigger,
        condition: compiled.condition,
        action: compiled.action,
        enforcement_mode: compiled.enforcement_mode,
        governance_tier: compiled.governance_tier,
        enabled: true,
        confidence: compiled.confidence,
        compiled_by: compiled.compiled_by,
        matched_intents: compiled.matched_intents,
        notes: '',
      })
      setPolicies((prev) => [data, ...prev])
      setSelectedId(data.id)
      setPlainEnglish('')
      setNameHint('')
      setCompiled(null)
      toast.success('Policy saved. Active immediately.')
    } catch (err) {
      console.error('Save failed:', err)
      toast.error('Could not save policy.')
    } finally {
      setSaving(false)
    }
  }

  // Effect chain: Toggle enabled
  const handleToggle = async (policy: SavedPolicy) => {
    const next = !policy.enabled
    try {
      const { data } = await api.put<SavedPolicy>(`/policies/${policy.id}`, {
        enabled: next,
      })
      setPolicies((prev) => prev.map((p) => (p.id === policy.id ? data : p)))
      toast.success(next ? `Enabled "${policy.name}"` : `Disabled "${policy.name}"`)
    } catch (err) {
      console.error('Toggle failed:', err)
      toast.error('Could not update policy.')
    }
  }

  // Effect chain: Delete
  const handleDelete = async (policy: SavedPolicy) => {
    const ok = await confirmDialog({
      title: `Delete policy "${policy.name}"?`,
      message: 'This removes it from disk. Cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/policies/${policy.id}`)
      setPolicies((prev) => prev.filter((p) => p.id !== policy.id))
      if (selectedId === policy.id) setSelectedId(null)
      toast.success(`Deleted "${policy.name}"`)
    } catch (err) {
      console.error('Delete failed:', err)
      toast.error('Could not delete policy.')
    }
  }

  // Effect chain: Load defaults
  const handleLoadDefaults = async () => {
    setSeeding(true)
    try {
      const { data } = await api.post<{ created: string[]; skipped: string[] }>(
        '/policies/seeds/load',
        {},
      )
      const created = data?.created?.length ?? 0
      const skipped = data?.skipped?.length ?? 0
      toast.success(
        `Loaded ${created} default policies. ${skipped} already existed.`,
      )
      await loadPolicies()
    } catch (err) {
      console.error('Seed load failed:', err)
      toast.error('Could not load defaults.')
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="grid grid-cols-12 gap-6">
      {/* ─── Composer (left) ─── */}
      <div className="col-span-12 xl:col-span-7 space-y-4">
        <Card className="p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Wand2 size={16} className="text-primary-400" />
            <h2 className="text-sm font-semibold text-starlight-100 uppercase tracking-wider">
              New policy in plain English
            </h2>
          </div>
          <p className="text-xs text-starlight-400">
            Describe the rule the way you'd say it. Daena compiles it into structured
            governance YAML and applies it immediately on save.
          </p>

          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
                Policy
              </label>
              <textarea
                value={plainEnglish}
                onChange={(e) => setPlainEnglish(e.target.value)}
                placeholder="e.g. Daena should never post to my Twitter without showing me the draft first."
                rows={4}
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-midnight-500 border border-white/5 text-starlight-100 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 resize-none"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
                Short name (optional)
              </label>
              <input
                type="text"
                value={nameHint}
                onChange={(e) => setNameHint(e.target.value)}
                placeholder="Twitter post review"
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-midnight-500 border border-white/5 text-starlight-100 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCompile}
                disabled={compiling || plainEnglish.trim().length < 3}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-400 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold text-midnight-700 transition-colors"
              >
                {compiling ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {compiling ? 'Compiling…' : 'Compile now'}
              </button>
              {compiled && (
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-green hover:bg-accent-green/90 disabled:opacity-50 text-sm font-semibold text-midnight-700 transition-colors"
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  Save policy
                </button>
              )}
              {(compiled || compileError) && !compiling && (
                <button
                  type="button"
                  onClick={() => {
                    setCompiled(null)
                    setCompileError(null)
                  }}
                  className="text-xs text-starlight-400 hover:text-starlight-200 transition-colors"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {compileError && (
            <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 p-3 flex items-start gap-2">
              <AlertTriangle size={14} className="text-accent-red mt-0.5" />
              <p className="text-xs text-accent-red leading-relaxed">{compileError}</p>
            </div>
          )}

          {compiled && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              className="space-y-3 pt-3 border-t border-white/5"
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${ACTION_COLORS[compiled.action]}`}
                >
                  {compiled.action}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-starlight-400">
                  Tier {TIER_LABELS[compiled.governance_tier] ?? compiled.governance_tier}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-starlight-400">
                  · {compiled.enforcement_mode}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-starlight-400 ml-auto">
                  Confidence {Math.round(compiled.confidence * 100)}%
                  · via {compiled.compiled_by}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <KV label="Trigger" value={compiled.trigger} />
                <KV label="Condition" value={compiled.condition} mono />
              </div>
              {compiled.reasoning && (
                <p className="text-xs text-starlight-300 italic leading-relaxed">
                  {compiled.reasoning}
                </p>
              )}
              <pre className="text-[11px] font-mono bg-midnight-700 border border-white/5 rounded-lg p-3 text-starlight-200 overflow-x-auto">
                {compiled.compiled_yaml}
              </pre>
            </motion.div>
          )}
        </Card>

        {/* ─── Saved policies list ─── */}
        <Card className="p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-starlight-100 uppercase tracking-wider">
              Saved policies ({policies.length})
            </h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadPolicies()}
                className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-starlight-400 hover:text-starlight-100 transition-colors"
              >
                <RotateCw size={12} /> Refresh
              </button>
              <button
                type="button"
                onClick={handleLoadDefaults}
                disabled={seeding}
                className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-primary-400 hover:text-primary-300 disabled:opacity-50 transition-colors"
              >
                {seeding ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                Load defaults
              </button>
            </div>
          </div>

          {loading && (
            <div className="rounded-lg border border-white/5 bg-midnight-500/40 p-4 text-xs text-starlight-400">
              Loading policies…
            </div>
          )}

          {loadError && (
            <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 p-3 flex items-center justify-between gap-2">
              <p className="text-xs text-accent-red">{loadError}</p>
              <button
                type="button"
                onClick={() => void loadPolicies()}
                className="text-[10px] uppercase tracking-wider text-accent-red hover:underline"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !loadError && policies.length === 0 && (
            <div className="rounded-lg border border-dashed border-white/10 bg-midnight-500/30 p-6 text-center">
              <p className="text-sm text-starlight-300 font-semibold">No policies yet.</p>
              <p className="text-xs text-starlight-400 mt-1">
                Click <span className="text-primary-300">Load defaults</span> to seed
                six starting rules, or write a new one above.
              </p>
            </div>
          )}

          {!loading && policies.length > 0 && (
            <ul className="space-y-2">
              {policies.map((p) => (
                <li
                  key={p.id}
                  onClick={() => setSelectedId(p.id === selectedId ? null : p.id)}
                  className={`rounded-lg border bg-midnight-500/40 hover:bg-midnight-500/70 cursor-pointer transition-colors ${
                    selectedId === p.id ? 'border-primary-500/50' : 'border-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider shrink-0 ${ACTION_COLORS[p.action]}`}
                    >
                      {p.action}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-starlight-100 truncate">
                        {p.name}
                      </p>
                      <p className="text-[11px] text-starlight-400 truncate">
                        {p.plain_english}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleToggle(p)
                      }}
                      className={`shrink-0 inline-flex items-center justify-center w-9 h-5 rounded-full transition-colors ${
                        p.enabled ? 'bg-accent-green' : 'bg-midnight-700 border border-white/10'
                      }`}
                      title={p.enabled ? 'Click to disable' : 'Click to enable'}
                    >
                      <span
                        className={`block w-3.5 h-3.5 rounded-full bg-midnight-700 shadow transition-transform ${
                          p.enabled ? 'translate-x-2' : '-translate-x-2'
                        }`}
                      />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleDelete(p)
                      }}
                      className="shrink-0 text-starlight-500 hover:text-accent-red transition-colors"
                      title="Delete policy"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* ─── Detail (right) ─── */}
      <div className="col-span-12 xl:col-span-5">
        <Card className="p-5 space-y-3 sticky top-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-accent-green" />
            <h2 className="text-sm font-semibold text-starlight-100 uppercase tracking-wider">
              Policy detail
            </h2>
          </div>

          {!selected ? (
            <div className="text-xs text-starlight-400 leading-relaxed">
              Select a saved policy to inspect its compiled YAML, version history,
              and audit trail. Or write a new one in plain English on the left.
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-sm font-semibold text-starlight-100">{selected.name}</p>
                <p className="text-[11px] text-starlight-400 mt-1">
                  Saved {new Date(selected.created_at).toLocaleString()} · v{selected.version}
                </p>
              </div>
              <p className="text-xs text-starlight-300 italic border-l-2 border-primary-500/40 pl-2">
                {selected.plain_english}
              </p>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <KV label="Trigger" value={selected.trigger} />
                <KV label="Action" value={selected.action} />
                <KV label="Tier" value={TIER_LABELS[selected.governance_tier] ?? String(selected.governance_tier)} />
                <KV label="Mode" value={selected.enforcement_mode} />
                <KV label="Compiled by" value={selected.compiled_by} />
                <KV label="Confidence" value={`${Math.round(selected.confidence * 100)}%`} />
              </div>
              <div className="pt-2 border-t border-white/5">
                <button
                  type="button"
                  onClick={() => {
                    void navigator.clipboard.writeText(selected.compiled_yaml)
                    toast.success('Compiled YAML copied to clipboard')
                  }}
                  className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-starlight-400 hover:text-starlight-100 transition-colors"
                >
                  <Copy size={11} /> Copy compiled YAML
                </button>
              </div>
              <pre className="text-[11px] font-mono bg-midnight-700 border border-white/5 rounded-lg p-3 text-starlight-200 overflow-x-auto">
                {selected.compiled_yaml}
              </pre>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-wider text-starlight-400 font-semibold">
        {label}
      </p>
      <p className={`text-xs ${mono ? 'font-mono' : ''} text-starlight-200 break-words`}>
        {value || '—'}
      </p>
    </div>
  )
}

export default PlainEnglishPolicies
