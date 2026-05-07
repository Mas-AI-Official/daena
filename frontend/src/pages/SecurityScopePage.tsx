/**
 * SecurityScopePage -- founder-only editor for authorized_scope.
 *
 * YELLOW-tier security tools (nmap, sqlmap, BloodHound, ...) only
 * execute against targets the tenant has explicitly declared they
 * own. This page is where the founder declares what's owned.
 *
 * Four entry buckets:
 *   - exact_domains     (e.g. mas-ai.co)
 *   - wildcard_domains  (e.g. mas-ai.co matches app.mas-ai.co, api.a.mas-ai.co, etc.)
 *   - ipv4_cidrs        (e.g. 10.0.0.0/24)
 *   - source_paths      (e.g. github.com/mas-ai/)
 *
 * Consumes:
 *   GET  /security/authorized-scope         -- load current
 *   PUT  /security/authorized-scope         -- replace all
 *   POST /security/authorized-scope/test    -- dry-run a target
 */
import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck, Plus, X, Save, AlertTriangle, CheckCircle2, Lock } from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { toast } from '@/stores/toastStore'

interface ScopeResponse {
  exact_domains: string[]
  wildcard_domains: string[]
  ipv4_cidrs: string[]
  source_paths: string[]
  has_any_entry: boolean
}

interface ScopeTestResponse {
  target: string
  in_scope: boolean
  reason: string
}

type BucketKey = 'exact_domains' | 'wildcard_domains' | 'ipv4_cidrs' | 'source_paths'

const BUCKETS: { key: BucketKey; label: string; placeholder: string; hint: string }[] = [
  {
    key: 'exact_domains',
    label: 'Exact domains',
    placeholder: 'mas-ai.co',
    hint: 'Only this hostname. Subdomains NOT included.',
  },
  {
    key: 'wildcard_domains',
    label: 'Wildcard domains',
    placeholder: 'mas-ai.co',
    hint: 'This hostname AND every subdomain under it.',
  },
  {
    key: 'ipv4_cidrs',
    label: 'IPv4 CIDRs',
    placeholder: '10.0.0.0/24',
    hint: 'Any IPv4 range you own. Single IP = /32.',
  },
  {
    key: 'source_paths',
    label: 'Source paths',
    placeholder: 'github.com/mas-ai/',
    hint: 'Repository prefixes for source-code scanning. Trailing slash added automatically.',
  },
]

export function SecurityScopePage() {
  usePageTitle('Authorized Scope')
  const user = useAuthStore((s) => s.user)
  const isFounder = user?.role === 'FOUNDER'

  const [scope, setScope] = useState<ScopeResponse | null>(null)
  const [serverScope, setServerScope] = useState<ScopeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testTarget, setTestTarget] = useState('')
  const [testResult, setTestResult] = useState<ScopeTestResponse | null>(null)
  const [testing, setTesting] = useState(false)

  // Track diff between local edits and last-saved server state.
  const isDirty = !!scope && !!serverScope && (
    JSON.stringify({ ...scope, has_any_entry: undefined }) !==
    JSON.stringify({ ...serverScope, has_any_entry: undefined })
  )

  // beforeunload warning when local edits are unsaved.
  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // Client-side validators so format errors surface inline at add-time
  // rather than at PUT time after the operator's typed several entries.
  const validateEntry = (key: BucketKey, value: string): string | null => {
    const v = value.trim()
    if (!v) return 'Entry cannot be empty'
    if (key === 'ipv4_cidrs') {
      const cidr = /^(?:(?:\d{1,3}\.){3}\d{1,3})(?:\/(?:[0-9]|[12][0-9]|3[0-2]))?$/
      if (!cidr.test(v)) return 'Expected an IPv4 address (10.0.0.5) or CIDR (10.0.0.0/24)'
      const parts = v.split('/')[0].split('.').map(Number)
      if (parts.some((p) => p < 0 || p > 255)) return 'Each octet must be 0-255'
    }
    if (key === 'exact_domains' || key === 'wildcard_domains') {
      const dom = /^(?!-)[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*[A-Za-z0-9]$/
      if (!dom.test(v)) return 'Expected a hostname like mas-ai.co (no protocol, no path)'
    }
    if (key === 'source_paths') {
      if (v.length < 4) return 'Source path looks too short'
    }
    return null
  }

  // 2026-04-29 stabilization: bound the loading window and surface a
  // clear empty-state when the backend is unreachable. Previously the
  // page sat on "Loading scope..." for the full axios timeout (30s)
  // when the backend was offline, which read as an infinite skeleton.
  const [loadError, setLoadError] = useState<string | null>(null)
  const backendHealthStatus = useBackendHealthStore((s) => s.status)

  const loadScope = useCallback(async () => {
    setLoadError(null)
    try {
      const { data } = await api.get<ScopeResponse>('/security/authorized-scope', {
        timeout: 5000,
      })
      setScope(data)
      setServerScope(data)
    } catch (err) {
      console.error('Failed to load scope:', err)
      const message =
        err instanceof Error && err.message
          ? err.message
          : 'Could not load authorized scope'
      setLoadError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isFounder) void loadScope()
    else setLoading(false)
  }, [isFounder, loadScope])

  const setBucket = (key: BucketKey, values: string[]) => {
    setScope((prev) => (prev ? { ...prev, [key]: values } : prev))
  }

  const addEntry = (key: BucketKey, value: string) => {
    const v = value.trim()
    if (!v || !scope) return
    const validationError = validateEntry(key, v)
    if (validationError) {
      toast.error(validationError)
      return
    }
    const existing = scope[key] || []
    if (existing.includes(v)) {
      toast.info(`"${v}" already in ${key.replace('_', ' ')}`)
      return
    }
    setBucket(key, [...existing, v])
  }

  const removeEntry = (key: BucketKey, value: string) => {
    if (!scope) return
    setBucket(key, (scope[key] || []).filter((x) => x !== value))
  }

  const save = async () => {
    if (!scope || saving) return
    setSaving(true)
    try {
      const body = {
        exact_domains: scope.exact_domains,
        wildcard_domains: scope.wildcard_domains,
        ipv4_cidrs: scope.ipv4_cidrs,
        source_paths: scope.source_paths,
      }
      const { data } = await api.put<ScopeResponse>('/security/authorized-scope', body)
      setScope(data)
      setServerScope(data)
      toast.success('Authorized scope saved')
    } catch (err: unknown) {
      console.error('Save failed:', err)
      const msg =
        (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      toast.error(typeof msg === 'string' ? msg : 'Save failed. Check the CIDR format.')
    } finally {
      setSaving(false)
    }
  }

  const runTest = async () => {
    const t = testTarget.trim()
    if (!t) return
    setTesting(true)
    setTestResult(null)
    try {
      const { data } = await api.post<ScopeTestResponse>('/security/authorized-scope/test', {
        target: t,
      })
      setTestResult(data)
    } catch (err) {
      console.error('Test failed:', err)
      toast.error('Scope test failed')
    } finally {
      setTesting(false)
    }
  }

  if (!isFounder) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <EmptyState
            icon={<Lock size={32} />}
            title="Founder-only area"
            description="Authorized scope controls which targets YELLOW-tier security tools can run against. Only the FOUNDER tier can edit this."
          />
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-4xl mx-auto p-6">
          <p className="text-sm text-starlight-400">Loading scope...</p>
        </div>
      </div>
    )
  }

  // Honest empty state when the load failed (5s timeout or network error).
  // The BackendOfflineBanner at the top of the app already explains the
  // global health story; this card explains the per-page consequence.
  if (loadError && !scope) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-4xl mx-auto p-6">
          <Card variant="glass" padding="md" className="border-status-error/30 bg-status-error/5">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="text-status-error mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <h2 className="text-sm font-semibold text-starlight-100">Authorized scope unavailable</h2>
                <p className="mt-1 text-xs text-starlight-400">
                  {backendHealthStatus === 'down' || backendHealthStatus === 'degraded'
                    ? 'Backend is offline or degraded. Authorized scope cannot be edited until the backend is reachable.'
                    : 'Failed to load authorized scope. Check the network or backend logs.'}
                </p>
                <p className="mt-2 text-[11px] text-starlight-500 font-mono">
                  Detail: {loadError}
                </p>
                <button
                  onClick={() => { setLoading(true); void loadScope() }}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
                >
                  Retry
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-primary-400" />
            Scan Scope — Authorized Targets
          </h1>
          <p className="text-sm text-starlight-400 mt-1 max-w-2xl">
            Founder-only whitelist. Declare the exact domains, IPs, and repos you own.
            YELLOW-tier defensive validation tools (nmap, sqlmap, nuclei, BloodHound) only run against
            targets inside this list -- nothing else can be scanned.
          </p>
          <p className="text-xs text-starlight-600 mt-1">
            This is NOT the security dashboard. To see live shield activity and scan history,
            use <span className="text-primary-400">Security Ops</span> in the sidebar.
          </p>
        </motion.div>

        {/* Empty-scope warning */}
        {scope && !scope.has_any_entry && (
          <Card variant="glass" padding="md" className="border-status-warning/30 bg-status-warning/5">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="text-status-warning mt-0.5" />
              <div>
                <p className="text-sm text-status-warning font-medium">Scope is empty</p>
                <p className="text-xs text-starlight-400 mt-1">
                  Every YELLOW-tier security tool call is blocked until at least one entry is declared.
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* 4 buckets */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {BUCKETS.map((b) => (
            <BucketEditor
              key={b.key}
              bucket={b}
              values={scope ? scope[b.key] : []}
              onAdd={(v) => addEntry(b.key, v)}
              onRemove={(v) => removeEntry(b.key, v)}
            />
          ))}
        </div>

        {/* Save */}
        <div className="flex items-center justify-end gap-3">
          {isDirty && (
            <span className="text-[11px] px-2 py-1 rounded-md bg-status-warning/10 text-status-warning border border-status-warning/30">
              Unsaved changes
            </span>
          )}
          <Button variant="premium" size="md" isLoading={saving} disabled={!isDirty} onClick={save}>
            <span className="flex items-center gap-2">
              <Save size={14} /> Save scope
            </span>
          </Button>
        </div>

        {/* Test a target */}
        <Card variant="glass" padding="md">
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-2">
            Test a target
          </h2>
          <p className="text-xs text-starlight-400 mb-3">
            Dry-run: does this target fall inside the saved scope? (Uses what is already saved, not what&apos;s in the editor above.)
          </p>
          <div className="flex gap-2 items-start">
            <input
              type="text"
              className="glass-input text-starlight-100 text-sm placeholder:text-starlight-400 focus-ring transition-all duration-200 flex-1"
              placeholder="https://app.mas-ai.co/admin or 10.0.0.5"
              value={testTarget}
              onChange={(e) => setTestTarget(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void runTest()
              }}
            />
            <Button variant="outline" size="sm" isLoading={testing} onClick={runTest}>
              Test
            </Button>
          </div>
          {testResult && (
            <div
              className={`mt-3 p-2.5 rounded-lg border flex items-start gap-2 text-xs ${
                testResult.in_scope
                  ? 'border-status-success/30 bg-status-success/10 text-status-success'
                  : 'border-status-error/30 bg-status-error/10 text-status-error'
              }`}
            >
              {testResult.in_scope ? (
                <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-medium">
                  {testResult.target} -{' '}
                  {testResult.in_scope ? 'in scope' : 'blocked'}
                </p>
                <p className="text-[11px] opacity-80 mt-0.5">{testResult.reason}</p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function BucketEditor({
  bucket,
  values,
  onAdd,
  onRemove,
}: {
  bucket: { key: BucketKey; label: string; placeholder: string; hint: string }
  values: string[]
  onAdd: (value: string) => void
  onRemove: (value: string) => void
}) {
  const [draft, setDraft] = useState('')
  return (
    <Card variant="glass" padding="md">
      <div className="mb-2">
        <h3 className="text-sm font-display font-semibold text-starlight-100">{bucket.label}</h3>
        <p className="text-[11px] text-starlight-500 mt-0.5">{bucket.hint}</p>
      </div>
      <div className="flex gap-1 mb-3">
        <input
          type="text"
          className="glass-input text-starlight-100 text-xs placeholder:text-starlight-400 focus-ring transition-all duration-200 flex-1"
          placeholder={bucket.placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && draft.trim()) {
              onAdd(draft)
              setDraft('')
            }
          }}
        />
        <button
          type="button"
          onClick={() => {
            if (draft.trim()) {
              onAdd(draft)
              setDraft('')
            }
          }}
          className="p-1.5 rounded-lg text-primary-400 hover:bg-primary-500/10 transition-colors cursor-pointer"
          aria-label="Add entry"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="space-y-1">
        {values.length === 0 ? (
          <p className="text-[11px] text-starlight-500 italic">No entries yet.</p>
        ) : (
          values.map((v) => (
            <div
              key={v}
              className="flex items-center justify-between p-1.5 rounded bg-white/[0.02] border border-white/5"
            >
              <Badge variant="default" size="sm">
                {v}
              </Badge>
              <button
                type="button"
                onClick={() => onRemove(v)}
                className="p-1 rounded text-starlight-400 hover:text-status-error hover:bg-status-error/10 transition-colors cursor-pointer"
                aria-label={`Remove ${v}`}
              >
                <X size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </Card>
  )
}

export default SecurityScopePage
