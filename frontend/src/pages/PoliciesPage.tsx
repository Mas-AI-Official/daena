/**
 * PoliciesPage -- the Policy Rules editor.
 *
 * Two tabs:
 *   Plain English -- global policies authored in natural language, compiled
 *                    to YAML by the backend and enforced by SecurityGate.
 *   Department Policies -- same plain-English composer, but every compiled
 *                          policy is scoped to a single department.
 */
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  Building2,
  ChevronDown,
  Loader2,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react'

import { Card } from '@/components/common'
import { usePageTitle } from '@/hooks/usePageTitle'
import { PlainEnglishPolicies } from '@/components/policies/PlainEnglishPolicies'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'

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


// ── Page ───────────────────────────────────────────────────────

type PoliciesTab = 'plain_english' | 'department_rules'

function readTabFromUrl(sp: URLSearchParams): PoliciesTab {
  const t = sp.get('tab')
  return t === 'department_rules' ? 'department_rules' : 'plain_english'
}

export default function PoliciesPage() {
  usePageTitle('Policy Rules')
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, _setActiveTab] = useState<PoliciesTab>(() => readTabFromUrl(searchParams))
  const setActiveTab = (next: PoliciesTab) => {
    _setActiveTab(next)
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev)
      if (next === 'plain_english') sp.delete('tab')
      else sp.set('tab', next)
      return sp
    }, { replace: true })
  }
  // Sync state when URL changes externally (back/forward).
  useEffect(() => {
    const fromUrl = readTabFromUrl(searchParams)
    if (fromUrl !== activeTab) _setActiveTab(fromUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto p-6 space-y-5">
        {/* Hero */}
        <div className="p-5 rounded-xl bg-gradient-to-r from-primary-500/10 via-accent-purple/10 to-accent-cyan/10 border border-primary-500/20">
          <h1 className="text-lg font-display font-semibold text-starlight-100 mb-1">
            Policy Rules
          </h1>
          <p className="text-xs text-starlight-400">
            Author governance in plain English. Daena compiles each rule into structured YAML
            that the security gate evaluates on every request.
          </p>

          {/* Tabs */}
          <div className="mt-4 flex items-center gap-1 border-b border-white/5">
            <TabButton
              active={activeTab === 'plain_english'}
              onClick={() => setActiveTab('plain_english')}
              label="Plain English"
              hint="Recommended"
            />
            <TabButton
              active={activeTab === 'department_rules'}
              onClick={() => setActiveTab('department_rules')}
              label="Department Policies"
              hint="per-dept scope"
            />
          </div>
        </div>

        {activeTab === 'plain_english' && <PlainEnglishPolicies />}

        {activeTab === 'department_rules' && <DepartmentPoliciesComposer />}
      </div>
    </div>
  )
}


// ── Department Policies Composer ────────────────────────────────────────────
// Same plain-English flow as the global tab, but scoped to one department.
// Each compiled policy is stored in /api/v1/policies with department_id.

interface DeptCompiledPreview {
  name: string
  plain_english: string
  trigger: string
  condition: string
  action: string
  enforcement_mode: string
  governance_tier: number
  confidence: number
  reasoning: string
  matched_intents: string[]
  compiled_by: string
}

interface DeptSavedPolicy extends DeptCompiledPreview {
  id: string
  enabled: boolean
  version: number
  created_at: string
  department_id: string | null
}

const ACTION_COLORS: Record<string, string> = {
  BLOCK: 'text-accent-red bg-accent-red/10 border-accent-red/30',
  REQUIRE_APPROVAL: 'text-accent-amber bg-accent-amber/10 border-accent-amber/30',
  APPROVE: 'text-accent-green bg-accent-green/10 border-accent-green/30',
  REDACT: 'text-accent-purple bg-accent-purple/10 border-accent-purple/30',
  LOG: 'text-starlight-300 bg-white/5 border-white/10',
}

function DepartmentPoliciesComposer() {
  const [selectedDept, setSelectedDept] = useState(DEPARTMENTS[0])
  const [plainEnglish, setPlainEnglish] = useState('')
  const [compiling, setCompiling] = useState(false)
  const [compiled, setCompiled] = useState<DeptCompiledPreview | null>(null)
  const [compileError, setCompileError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deptPolicies, setDeptPolicies] = useState<DeptSavedPolicy[]>([])
  const [loadingPolicies, setLoadingPolicies] = useState(false)

  const loadDeptPolicies = useCallback(async (dept: string) => {
    setLoadingPolicies(true)
    try {
      const { data } = await api.get<{ data: DeptSavedPolicy[] }>(
        `/policies?department_id=${encodeURIComponent(dept)}`,
      )
      setDeptPolicies(data?.data ?? [])
    } catch {
      setDeptPolicies([])
    } finally {
      setLoadingPolicies(false)
    }
  }, [])

  useEffect(() => { void loadDeptPolicies(selectedDept) }, [selectedDept, loadDeptPolicies])

  const handleDeptChange = (dept: string) => {
    setSelectedDept(dept)
    setCompiled(null)
    setCompileError(null)
    setPlainEnglish('')
  }

  const handleCompile = async () => {
    if (!plainEnglish.trim()) return
    setCompiling(true)
    setCompileError(null)
    setCompiled(null)
    try {
      const { data } = await api.post<DeptCompiledPreview>('/policies/compile', {
        plain_english: plainEnglish.trim(),
        department_id: selectedDept,
      })
      setCompiled(data)
    } catch {
      setCompileError('Compilation failed. Try rephrasing or check that Claude Code is connected.')
    } finally {
      setCompiling(false)
    }
  }

  const handleSave = async () => {
    if (!compiled) return
    setSaving(true)
    try {
      await api.post('/policies', {
        ...compiled,
        department_id: selectedDept,
        enabled: true,
      })
      toast.success(`Policy saved for ${selectedDept}. Active immediately.`)
      setCompiled(null)
      setPlainEnglish('')
      void loadDeptPolicies(selectedDept)
    } catch {
      toast.error('Failed to save policy')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    const ok = await confirmDialog({
      title: 'Delete this department policy?',
      message: 'This cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/policies/${id}`)
      void loadDeptPolicies(selectedDept)
      toast.success('Policy deleted')
    } catch {
      toast.error('Delete failed')
    }
  }

  return (
    <div className="space-y-5">
      {/* Department selector */}
      <Card className="p-4">
        <div className="flex items-center gap-3">
          <Building2 size={16} className="text-primary-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-xs font-medium text-starlight-300 mb-1">
              Select department -- the policy below will apply only to this department's agents.
            </p>
            <div className="relative">
              <select
                value={selectedDept}
                onChange={e => handleDeptChange(e.target.value)}
                className="w-full appearance-none px-3 py-2 rounded-lg bg-starlight-800 border border-starlight-700
                           text-sm text-starlight-200 focus:outline-none focus:border-primary-500/50 pr-8"
              >
                {DEPARTMENTS.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-starlight-500 pointer-events-none" />
            </div>
          </div>
        </div>
      </Card>

      {/* Plain-English composer */}
      <Card className="p-4 space-y-3">
        <p className="text-xs font-semibold text-starlight-300 flex items-center gap-1.5">
          <Sparkles size={12} className="text-primary-400" />
          Write a policy for <span className="text-primary-300">{selectedDept}</span>
        </p>
        <textarea
          value={plainEnglish}
          onChange={e => setPlainEnglish(e.target.value)}
          placeholder={`e.g. "The ${selectedDept} department should require my approval before sending any email to a customer."`}
          rows={3}
          className="w-full px-3 py-2.5 rounded-lg bg-starlight-900 border border-starlight-700 text-sm text-starlight-200
                     placeholder:text-starlight-600 focus:outline-none focus:border-primary-500/50 resize-none"
        />
        <div className="flex items-center justify-between">
          {compileError && (
            <p className="text-xs text-accent-red flex items-center gap-1">
              <AlertTriangle size={11} /> {compileError}
            </p>
          )}
          <button
            onClick={handleCompile}
            disabled={compiling || !plainEnglish.trim()}
            className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold
                       bg-primary-500 text-white hover:bg-primary-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {compiling ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {compiling ? 'Compiling...' : 'Compile'}
          </button>
        </div>

        {compiled && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
            className="border border-primary-500/20 rounded-lg p-3 bg-primary-500/5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-starlight-200">{compiled.name}</span>
              <div className="flex items-center gap-1.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${ACTION_COLORS[compiled.action] ?? ACTION_COLORS.LOG}`}>
                  {compiled.action}
                </span>
                <span className="text-[10px] text-starlight-500">tier {compiled.governance_tier}</span>
              </div>
            </div>
            <p className="text-[11px] text-starlight-400">{compiled.reasoning}</p>
            <div className="flex items-center justify-between pt-1">
              <span className="text-[10px] text-starlight-600">
                confidence {Math.round(compiled.confidence * 100)}%
              </span>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                           bg-accent-green/20 text-accent-green hover:bg-accent-green/30 disabled:opacity-50 cursor-pointer"
              >
                {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                Save policy
              </button>
            </div>
          </motion.div>
        )}
      </Card>

      {/* Saved policies for this department */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-starlight-400 uppercase tracking-wider">
          Saved policies for {selectedDept} ({deptPolicies.length})
        </p>
        {loadingPolicies ? (
          <div className="space-y-2">
            {[1, 2].map(i => (
              <div key={i} className="h-14 rounded-xl bg-starlight-800/50 animate-pulse" />
            ))}
          </div>
        ) : deptPolicies.length === 0 ? (
          <Card className="p-5 text-center">
            <p className="text-sm text-starlight-500">
              No policies for {selectedDept} yet. Write one above.
            </p>
          </Card>
        ) : (
          deptPolicies.map(p => (
            <Card key={p.id} className="p-3 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-starlight-200 truncate">{p.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium flex-shrink-0 ${ACTION_COLORS[p.action] ?? ACTION_COLORS.LOG}`}>
                    {p.action}
                  </span>
                </div>
                <p className="text-xs text-starlight-500 truncate mt-0.5">{p.plain_english}</p>
              </div>
              <button
                onClick={() => handleDelete(p.id)}
                className="p-1.5 rounded-lg text-starlight-600 hover:text-accent-red hover:bg-accent-red/10 transition-colors cursor-pointer"
                title="Delete policy"
              >
                <Trash2 size={13} />
              </button>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}


function TabButton({
  active,
  onClick,
  label,
  hint,
}: {
  active: boolean
  onClick: () => void
  label: string
  hint?: string
}) {
  return (
    <button
      onClick={onClick}
      type="button"
      className={`relative px-4 py-2 text-xs font-semibold transition-colors ${
        active
          ? 'text-primary-300 border-b-2 border-primary-400 -mb-px'
          : 'text-starlight-400 hover:text-starlight-200 border-b-2 border-transparent -mb-px'
      }`}
    >
      <span className="uppercase tracking-wider">{label}</span>
      {hint && (
        <span
          className={`ml-2 text-[10px] uppercase tracking-wider ${
            active ? 'text-primary-400/80' : 'text-starlight-500'
          }`}
        >
          · {hint}
        </span>
      )}
    </button>
  )
}
