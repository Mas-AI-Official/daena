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
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testTarget, setTestTarget] = useState('')
  const [testResult, setTestResult] = useState<ScopeTestResponse | null>(null)
  const [testing, setTesting] = useState(false)

  const loadScope = useCallback(async () => {
    try {
      const { data } = await api.get<ScopeResponse>('/security/authorized-scope')
      setScope(data)
    } catch (err) {
      console.error('Failed to load scope:', err)
      toast.error('Could not load authorized scope')
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

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-primary-400" />
            Authorized Scope
          </h1>
          <p className="text-sm text-starlight-400 mt-1 max-w-2xl">
            Declare the domains, IPs, and repos this tenant owns. YELLOW-tier security tools
            (nmap, sqlmap, nuclei, BloodHound) only execute against targets inside this scope.
            Empty scope blocks all YELLOW tools for the tenant.
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
        <div className="flex justify-end">
          <Button variant="premium" size="md" isLoading={saving} onClick={save}>
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
