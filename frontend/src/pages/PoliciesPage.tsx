/**
 * PoliciesPage -- the Policy Rules editor for cross-department approvals.
 *
 * Session D. Lets the operator view, toggle, edit, and seed the rules
 * that DaenaVP consults during routing. The same rules drive what
 * the chat orchestrator fires as inter-department asks at execution
 * time (Session C messaging).
 *
 * Minimal v1 editor: create / enable-disable / delete. Editing the
 * trigger_condition JSON is exposed as a raw textarea since the
 * schema is small and operators who write policies will be comfortable
 * with JSON. A structured builder can replace it later.
 */
import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  CheckCircle2,
  Gavel,
  Plus,
  RotateCw,
  ShieldCheck,
  Trash2,
  XCircle,
} from 'lucide-react'

import { Card } from '@/components/common'
import { usePageTitle } from '@/hooks/usePageTitle'
import {
  useDepartmentPolicies,
  type DepartmentPolicy,
  type PolicyDraft,
  type PolicyType,
} from '@/hooks/useDepartmentPolicies'
import { toast } from '@/stores/toastStore'

const DEPARTMENTS = [
  'Engineering',
  'Product',
  'Marketing',
  'Sales',
  'Finance',
  'Operations',
  'Research',
  'Legal & Compliance',
  'Skill Governance',
  'Security Operations',
]

const POLICY_TYPES: PolicyType[] = [
  'EXPENSE',
  'DEPLOYMENT',
  'EXTERNAL_COMMS',
  'EXTERNAL_DATA',
  'NEW_VENDOR',
  'CUSTOM',
]

const TYPE_COLORS: Record<PolicyType, string> = {
  EXPENSE: 'text-accent-green bg-accent-green/10 border-accent-green/30',
  DEPLOYMENT: 'text-primary-400 bg-primary-500/10 border-primary-500/30',
  EXTERNAL_COMMS: 'text-accent-amber bg-accent-amber/10 border-accent-amber/30',
  EXTERNAL_DATA: 'text-accent-red bg-accent-red/10 border-accent-red/30',
  NEW_VENDOR: 'text-accent-purple bg-accent-purple/10 border-accent-purple/30',
  CUSTOM: 'text-starlight-300 bg-white/5 border-white/10',
}


// ── Compose / edit form ───────────────────────────────────────

function PolicyForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (draft: PolicyDraft) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [policyType, setPolicyType] = useState<PolicyType>('EXPENSE')
  const [triggerJson, setTriggerJson] = useState(
    '{\n  "conditions": [\n    {"field": "amount", "op": "gte", "value": 500}\n  ]\n}',
  )
  const [approvers, setApprovers] = useState<string[]>(['Finance'])
  const [saving, setSaving] = useState(false)

  const toggleApprover = (dept: string) => {
    setApprovers((prev) =>
      prev.includes(dept) ? prev.filter((d) => d !== dept) : [...prev, dept],
    )
  }

  const handleSubmit = async () => {
    if (!name.trim() || approvers.length === 0) return
    let trigger: PolicyDraft['trigger_condition']
    try {
      trigger = JSON.parse(triggerJson)
    } catch {
      toast.error('Trigger condition is not valid JSON')
      return
    }
    setSaving(true)
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        policy_type: policyType,
        trigger_condition: trigger,
        required_approvers: approvers,
        enabled: true,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Plus size={14} className="text-primary-400" />
        <p className="text-xs font-semibold text-starlight-200 uppercase tracking-wider">
          New Policy
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Campaigns over $1k need Legal"
            className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-midnight-500 border border-white/5 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
            Type
          </label>
          <select
            value={policyType}
            onChange={(e) => setPolicyType(e.target.value as PolicyType)}
            className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-midnight-500 border border-white/5 text-starlight-200 focus:outline-none focus:border-primary-500/40"
          >
            {POLICY_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
          Description
        </label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Why this rule exists"
          className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-midnight-500 border border-white/5 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
        />
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
          Trigger condition (JSON)
        </label>
        <textarea
          value={triggerJson}
          onChange={(e) => setTriggerJson(e.target.value)}
          rows={5}
          className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-midnight-500 border border-white/5 text-starlight-200 font-mono focus:outline-none focus:border-primary-500/40 resize-none"
        />
        <p className="text-[10px] text-starlight-500 mt-1">
          Operators: <span className="font-mono">eq / ne / gt / gte / lt / lte / in / contains</span>.
          Common fields: <span className="font-mono">amount, action_type, from_department, tags, description</span>.
        </p>
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-wider text-starlight-400 font-semibold">
          Required approvers (click to toggle)
        </label>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {DEPARTMENTS.map((dept) => {
            const on = approvers.includes(dept)
            return (
              <button
                key={dept}
                onClick={() => toggleApprover(dept)}
                className={`px-2.5 py-1 rounded-md text-[11px] border transition-colors cursor-pointer ${
                  on
                    ? 'bg-primary-500/20 border-primary-500/50 text-primary-300'
                    : 'bg-white/5 border-white/10 text-starlight-400 hover:bg-white/10'
                }`}
              >
                {dept}
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
        <button
          onClick={onCancel}
          className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:bg-white/5 cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving || !name.trim() || approvers.length === 0}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-400 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <Plus size={12} />
          {saving ? 'Saving...' : 'Save policy'}
        </button>
      </div>
    </Card>
  )
}


// ── One row ────────────────────────────────────────────────────

function PolicyRow({
  policy,
  onToggle,
  onDelete,
}: {
  policy: DepartmentPolicy
  onToggle: (id: string, enabled: boolean) => void
  onDelete: (id: string) => void
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-xl bg-midnight-400/40 border ${
        policy.enabled ? 'border-white/5' : 'border-white/5 opacity-60'
      }`}
    >
      <div className="flex items-start gap-3 mb-2">
        <div className="w-9 h-9 rounded-lg bg-midnight-500 flex items-center justify-center text-starlight-300 shrink-0">
          <ShieldCheck size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <p className="text-sm font-semibold text-starlight-100">{policy.name}</p>
            <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${TYPE_COLORS[policy.policy_type]}`}>
              {policy.policy_type}
            </span>
            {policy.seed_key && (
              <span className="px-1.5 py-0.5 rounded bg-white/5 text-[9px] uppercase tracking-wider text-starlight-500">
                seeded
              </span>
            )}
          </div>
          {policy.description && (
            <p className="text-[12px] text-starlight-400 mt-1">{policy.description}</p>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onToggle(policy.id, !policy.enabled)}
            role="switch"
            aria-checked={policy.enabled}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-all duration-200 cursor-pointer ${
              policy.enabled
                ? 'bg-accent-green border border-accent-green'
                : 'bg-white/10 border border-white/15'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${
                policy.enabled ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </button>
          <button
            onClick={() => onDelete(policy.id)}
            className="p-1.5 rounded hover:bg-accent-red/10 text-starlight-500 hover:text-accent-red cursor-pointer"
            title="Delete policy"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Trigger + approvers summary */}
      <div className="pt-2 border-t border-white/5 grid grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-1">
            Trigger
          </p>
          <pre className="text-[10px] text-starlight-300 font-mono bg-midnight-500/60 p-2 rounded max-h-28 overflow-y-auto">
            {JSON.stringify(policy.trigger_condition, null, 2)}
          </pre>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-1">
            Required approvers
          </p>
          <div className="flex flex-wrap gap-1.5">
            {policy.required_approvers.map((dept) => (
              <span
                key={dept}
                className="px-2 py-0.5 rounded-md text-[11px] bg-primary-500/10 text-primary-400 border border-primary-500/20"
              >
                {dept}
              </span>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}


// ── Page ───────────────────────────────────────────────────────

export default function PoliciesPage() {
  usePageTitle('Policy Rules')
  const { policies, loading, error, createPolicy, updatePolicy, deletePolicy, seedDefaults } =
    useDepartmentPolicies()
  const [showForm, setShowForm] = useState(false)

  const enabledCount = useMemo(
    () => policies.filter((p) => p.enabled).length,
    [policies],
  )

  const handleCreate = async (draft: PolicyDraft) => {
    const result = await createPolicy(draft)
    if (result) {
      toast.success(`Policy "${result.name}" created`)
      setShowForm(false)
    } else {
      toast.error('Failed to create policy')
    }
  }

  const handleToggle = async (id: string, enabled: boolean) => {
    const result = await updatePolicy(id, { enabled })
    if (result) {
      toast.success(`Policy ${enabled ? 'enabled' : 'disabled'}`)
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this policy? Seeded policies can be recreated via Seed defaults.')) return
    const ok = await deletePolicy(id)
    if (ok) toast.success('Policy deleted')
  }

  const handleSeed = async () => {
    const count = await seedDefaults()
    if (count > 0) {
      toast.success(`Installed ${count} default policies`)
    } else {
      toast.info('All default policies already present')
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-5">
        {/* Hero */}
        <div className="p-5 rounded-xl bg-gradient-to-r from-primary-500/10 via-accent-purple/10 to-accent-cyan/10 border border-primary-500/20">
          <h1 className="text-lg font-display font-semibold text-starlight-100 mb-1">
            Policy Rules
          </h1>
          <p className="text-xs text-starlight-400 mb-4">
            Cross-department approval rules. Daena VP consults this list before routing every subtask.
          </p>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={12} className="text-accent-green" />
              <span className="text-starlight-300">
                <span className="font-mono font-semibold text-starlight-100">{enabledCount}</span> enabled
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Gavel size={12} className="text-starlight-500" />
              <span className="text-starlight-300">
                <span className="font-mono font-semibold text-starlight-100">{policies.length - enabledCount}</span> disabled
              </span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={handleSeed}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
              >
                <RotateCw size={11} /> Seed defaults
              </button>
              <button
                onClick={() => setShowForm(!showForm)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
              >
                {showForm ? <XCircle size={12} /> : <Plus size={12} />}
                {showForm ? 'Close' : 'New policy'}
              </button>
            </div>
          </div>
        </div>

        {showForm && <PolicyForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />}

        {error && (
          <Card className="p-4 border-accent-red/30 bg-accent-red/5">
            <div className="flex items-center gap-2 text-xs text-accent-red">
              <AlertTriangle size={12} /> {error}
            </div>
          </Card>
        )}

        {loading && policies.length === 0 ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-midnight-400/40 border border-white/5 animate-pulse h-28"
              />
            ))}
          </div>
        ) : policies.length === 0 ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-starlight-400 mb-3">No policies yet.</p>
            <button
              onClick={handleSeed}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-400 cursor-pointer"
            >
              <RotateCw size={12} /> Install default policies
            </button>
          </Card>
        ) : (
          <div className="space-y-3">
            {policies.map((p) => (
              <PolicyRow
                key={p.id}
                policy={p}
                onToggle={handleToggle}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
