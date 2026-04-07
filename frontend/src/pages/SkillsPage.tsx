/**
 * SkillsPage -- Claude Desktop-style layout with left sidebar category nav.
 *
 * Layout: left sidebar (All / Web / Local / Custom / System) + main content
 * grid of skill cards. Each card shows name, description, category badge,
 * governance tier badge, and a per-skill Allow / Ask / Block permission
 * dropdown (same PermissionDropdown pattern as ConnectionsPage).
 *
 * Data: fetched from GET /skills on mount, filtered client-side by category
 * and search query.
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles,
  Search,
  Shield,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Wrench,
  LayoutGrid,
  Upload,
  Code2,
  Layers,
  Megaphone,
  Settings2,
  Palette,
  DollarSign,
  MessageSquare,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { SkillResponse, ApiResponse, PermissionLevel } from '@/types/api'

// ── Constants ──────────────────────────────────────────────────────────────

const TIER_LABELS: Record<number, { label: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'amber' }> = {
  0: { label: 'Silent', variant: 'default' },
  1: { label: 'Logged', variant: 'default' },
  2: { label: 'Notified', variant: 'warning' },
  3: { label: 'Approval', variant: 'amber' },
  4: { label: 'Council', variant: 'danger' },
}

type CategoryKey = 'all' | 'system' | 'web' | 'engineering' | 'product' | 'marketing' | 'research' | 'operations' | 'design' | 'sales' | 'communication' | 'other'

const CATEGORIES: { key: CategoryKey; label: string; icon: React.ReactNode; match: (s: SkillResponse) => boolean }[] = [
  { key: 'all', label: 'All Skills', icon: <LayoutGrid size={14} />, match: () => true },
  { key: 'system', label: 'System', icon: <Settings2 size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['system', 'local'].includes(cat) ||
      /\b(file|terminal|shell|command|desktop|screen|mouse|keyboard|python|package|install)\b/.test(name + ' ' + desc)
  }},
  { key: 'web', label: 'Web', icon: <Search size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['web', 'browser', 'search'].includes(cat) ||
      /\b(web|browser|http|api|scrape|search|navigate|screenshot|url)\b/.test(name + ' ' + desc)
  }},
  { key: 'engineering', label: 'Engineering', icon: <Code2 size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['engineering', 'code', 'development', 'testing'].includes(cat) ||
      /\b(code|debug|test|build|deploy|git|refactor|lint|compile|typescript|python|review|pr|commit)\b/.test(name + ' ' + desc)
  }},
  { key: 'product', label: 'Product', icon: <Layers size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['product', 'feature', 'spec', 'planning'].includes(cat) ||
      /\b(product|roadmap|spec|feature|prd|sprint|backlog|requirement|user.?story|metric|stakeholder)\b/.test(name + ' ' + desc)
  }},
  { key: 'marketing', label: 'Marketing', icon: <Megaphone size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['marketing', 'content', 'seo', 'social'].includes(cat) ||
      /\b(marketing|seo|content|brand|email|campaign|social|blog|newsletter|outreach|copywriting)\b/.test(name + ' ' + desc)
  }},
  { key: 'research', label: 'Research', icon: <Search size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['research', 'analysis', 'competitive'].includes(cat) ||
      /\b(research|analysis|competitive|survey|insight|data|report|intelligence|benchmark)\b/.test(name + ' ' + desc)
  }},
  { key: 'operations', label: 'Operations', icon: <Settings2 size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['operations', 'ops', 'automation', 'workflow'].includes(cat) ||
      /\b(operations|ops|automation|workflow|process|schedule|vendor|runbook|incident|standup|status)\b/.test(name + ' ' + desc)
  }},
  { key: 'design', label: 'Design', icon: <Palette size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['design', 'ui', 'ux'].includes(cat) ||
      /\b(design|figma|ui|ux|accessibility|wireframe|prototype|layout|style|css|theme|visual)\b/.test(name + ' ' + desc)
  }},
  { key: 'sales', label: 'Sales & Finance', icon: <DollarSign size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['sales', 'finance', 'billing'].includes(cat) ||
      /\b(sales|finance|billing|invoice|payment|revenue|pipeline|deal|lead|prospect|forecast|budget|cost|expense)\b/.test(name + ' ' + desc)
  }},
  { key: 'communication', label: 'Communication', icon: <MessageSquare size={14} />, match: (s) => {
    const cat = s.category?.toLowerCase() ?? ''
    const name = s.name?.toLowerCase() ?? ''
    const desc = s.description?.toLowerCase() ?? ''
    return ['communication', 'messaging'].includes(cat) ||
      /\b(slack|gmail|email|chat|message|notification|announcement|calendar|meeting|agenda)\b/.test(name + ' ' + desc)
  }},
  { key: 'other', label: 'Other', icon: <Wrench size={14} />, match: () => true },
]

// ── PermissionDropdown (same pattern as ConnectionsPage) ───────────────────

const PERM_OPTIONS: { value: PermissionLevel; label: string; color: string }[] = [
  { value: 'ALWAYS_ALLOW', label: 'Always allow', color: 'text-accent-green' },
  { value: 'ASK_EACH_TIME', label: 'Needs approval', color: 'text-accent-amber' },
  { value: 'BLOCK', label: 'Blocked', color: 'text-accent-red' },
]

function PermissionDropdown({
  value,
  onChange,
}: {
  value: PermissionLevel
  onChange: (level: PermissionLevel) => void
}) {
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, right: 0, openUp: false })
  const current = PERM_OPTIONS.find((o) => o.value === value) || PERM_OPTIONS[1]

  const MENU_HEIGHT = 108 // 3 options * ~36px each

  const handleOpen = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!open && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      const spaceBelow = window.innerHeight - rect.bottom
      const openUp = spaceBelow < MENU_HEIGHT + 8
      setPos({
        top: openUp ? rect.top - MENU_HEIGHT - 4 : rect.bottom + 4,
        right: Math.max(4, window.innerWidth - rect.right),
        openUp,
      })
    }
    setOpen(!open)
  }

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={handleOpen}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border border-white/10 hover:border-white/20 transition-all cursor-pointer"
      >
        {current.value === 'ALWAYS_ALLOW' && <CheckCircle2 size={11} className="text-accent-green" />}
        {current.value === 'ASK_EACH_TIME' && <Shield size={11} className="text-accent-amber" />}
        {current.value === 'BLOCK' && <XCircle size={11} className="text-accent-red" />}
        <span className={current.color}>{current.label}</span>
        <ChevronDown size={9} className="text-starlight-500" />
      </button>
      {open && createPortal(
        <AnimatePresence>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <motion.div
            ref={menuRef}
            initial={{ opacity: 0, y: pos.openUp ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: pos.openUp ? 4 : -4 }}
            style={{ top: Math.max(4, pos.top), right: pos.right }}
            className="fixed w-40 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-[9999] overflow-hidden"
          >
            {PERM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={(e) => { e.stopPropagation(); onChange(opt.value); setOpen(false) }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-white/5 transition-colors cursor-pointer ${
                  opt.value === value ? 'bg-white/[0.03]' : ''
                }`}
              >
                {opt.value === 'ALWAYS_ALLOW' && <CheckCircle2 size={12} className="text-accent-green" />}
                {opt.value === 'ASK_EACH_TIME' && <Shield size={12} className="text-accent-amber" />}
                {opt.value === 'BLOCK' && <XCircle size={12} className="text-accent-red" />}
                <span className={opt.color}>{opt.label}</span>
              </button>
            ))}
          </motion.div>
        </AnimatePresence>,
        document.body,
      )}
    </div>
  )
}

// ── SkillCard ──────────────────────────────────────────────────────────────

interface SkillCardProps {
  skill: SkillResponse
  permission: PermissionLevel
  onPermissionChange: (id: string, level: PermissionLevel) => void
  index: number
}

function SkillCard({ skill, permission, onPermissionChange, index }: SkillCardProps) {
  const [expanded, setExpanded] = useState(false)
  const tier = TIER_LABELS[skill.governance_tier] ?? { label: `Tier ${skill.governance_tier}`, variant: 'default' as const }

  const categoryColor: Record<string, string> = {
    web: 'text-accent-cyan',
    local: 'text-primary-400',
    custom: 'text-accent-purple',
    system: 'text-accent-amber',
  }
  const iconColor = categoryColor[skill.category?.toLowerCase() ?? ''] || 'text-starlight-400'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
    >
      <Card variant="glass" padding="none" className="overflow-hidden hover:border-white/10 transition-all">
        {/* Header row -- always visible */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-start gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
        >
          <div className={`mt-0.5 w-8 h-8 rounded-lg border border-white/5 bg-white/[0.03] flex items-center justify-center shrink-0`}>
            <Code2 size={15} className={iconColor} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-display font-semibold text-starlight-100 truncate">{skill.name}</h3>
              {skill.category && (
                <Badge variant="default" size="sm">{skill.category}</Badge>
              )}
              <Badge variant={tier.variant as 'default' | 'success' | 'warning' | 'danger' | 'amber'} size="sm">
                {tier.label}
              </Badge>
              {!skill.is_active && (
                <Badge variant="danger" size="sm">Inactive</Badge>
              )}
            </div>
            {skill.description && (
              <p className="text-xs text-starlight-400 mt-1 line-clamp-2">{skill.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0 mt-0.5">
            {expanded ? (
              <ChevronDown size={14} className="text-starlight-500" />
            ) : (
              <ChevronRight size={14} className="text-starlight-500" />
            )}
          </div>
        </button>

        {/* Footer row with permission control -- always visible */}
        <div
          className="flex items-center justify-between px-4 pb-3 pt-0 relative z-10"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-3 text-[10px] text-starlight-500">
            <span className="flex items-center gap-1">
              <Shield size={10} />
              Tier {skill.governance_tier}
            </span>
            <span>v{skill.version}</span>
            <span>{skill.usage_count} uses</span>
          </div>
          <PermissionDropdown
            value={permission}
            onChange={(level) => onPermissionChange(skill.id, level)}
          />
        </div>

        {/* Expanded detail panel */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 pt-1 border-t border-white/5 space-y-3">
                {/* Schema preview */}
                {skill.schema_def && Object.keys(skill.schema_def).length > 0 && (
                  <div>
                    <p className="text-[10px] text-starlight-500 font-semibold uppercase tracking-wider mb-1.5">Schema</p>
                    <pre className="text-[10px] text-starlight-300 font-mono bg-midnight-800/60 border border-white/5 rounded-lg p-2.5 overflow-x-auto">
                      {JSON.stringify(skill.schema_def, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Implementation preview */}
                {skill.implementation && (
                  <div>
                    <p className="text-[10px] text-starlight-500 font-semibold uppercase tracking-wider mb-1.5">Implementation</p>
                    <pre className="text-[10px] text-starlight-300 font-mono bg-midnight-800/60 border border-white/5 rounded-lg p-2.5 overflow-x-auto max-h-40">
                      {skill.implementation.length > 600
                        ? skill.implementation.slice(0, 600) + '\n...'
                        : skill.implementation}
                    </pre>
                  </div>
                )}

                {/* Metadata row */}
                <div className="flex items-center gap-4 text-[10px] text-starlight-500 pt-1">
                  <span>ID: <span className="font-mono text-starlight-400">{skill.id.slice(0, 8)}</span></span>
                  <span>Created: {new Date(skill.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export function SkillsPage() {
  usePageTitle('Skills')

  const [skills, setSkills] = useState<SkillResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('all')
  const [permissions, setPermissions] = useState<Record<string, PermissionLevel>>(() => {
    try {
      const saved = localStorage.getItem('daena:skill_permissions')
      return saved ? JSON.parse(saved) : {}
    } catch { return {} }
  })

  const fetchSkills = useCallback(async () => {
    try {
      // Try DB skills first, then fall back to filesystem-scanned skills
      const res = await api.get<ApiResponse<SkillResponse[]>>('/skills', {
        params: { active_only: true, page: 1, page_size: 200 },
      })
      let list = res.data.data || []

      // If no DB skills, try filesystem scan
      if (list.length === 0) {
        try {
          const fsRes = await api.get<ApiResponse<Array<Record<string, unknown>>>>('/skills/installed')
          const fsSkills = fsRes.data.data || []
          // Map filesystem skills to SkillResponse shape, using backend category
          list = fsSkills.map((s, i) => ({
            id: s.source as string || `fs-${i}`,
            name: s.name as string || 'Unknown',
            description: s.description as string || '',
            category: (s.category as string) || 'other',
            governance_tier: 1,
            is_active: s.status === 'active',
            tags: [] as string[],
            version: '1.0',
            created_at: s.last_modified as string || '',
            updated_at: null as string | null,
          })) as unknown as SkillResponse[]
        } catch {
          // Filesystem scan not available
        }
      }

      setSkills(list)
      setPermissions((prev) => {
        const next = { ...prev }
        list.forEach((s) => {
          if (!next[s.id]) next[s.id] = 'ASK_EACH_TIME'
        })
        return next
      })
    } catch {
      setSkills([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSkills()
  }, [fetchSkills])

  const handlePermissionChange = useCallback((id: string, level: PermissionLevel) => {
    setPermissions((prev) => {
      const next = { ...prev, [id]: level }
      localStorage.setItem('daena:skill_permissions', JSON.stringify(next))
      return next
    })
    // Sync to backend: map permission to governance tier
    const tierMap: Record<PermissionLevel, number> = { ALWAYS_ALLOW: 0, ASK_EACH_TIME: 2, BLOCK: 4 }
    api.patch(`/skills/${id}`, { governance_tier: tierMap[level] }).catch(() => {})
  }, [])

  // Active category matcher
  const categoryDef = CATEGORIES.find((c) => c.key === activeCategory) ?? CATEGORIES[0]

  // Apply category + search filters
  const filtered = skills.filter((s) => {
    if (!categoryDef.match(s)) return false
    if (!search) return true
    const q = search.toLowerCase()
    return (
      s.name.toLowerCase().includes(q) ||
      s.description?.toLowerCase().includes(q) ||
      s.category?.toLowerCase().includes(q)
    )
  })

  // When viewing 'other', exclude skills matched by any specific category
  const finalFiltered = activeCategory === 'other'
    ? filtered.filter(s => !CATEGORIES.filter(c => c.key !== 'all' && c.key !== 'other').some(c => c.match(s)))
    : filtered

  // Count per category for badges
  const countFor = (key: CategoryKey) => {
    const def = CATEGORIES.find((c) => c.key === key)
    if (!def) return 0
    if (key === 'other') {
      const specificCategories = CATEGORIES.filter(c => c.key !== 'all' && c.key !== 'other')
      return skills.filter(s => !specificCategories.some(c => c.match(s))).length
    }
    return skills.filter((s) => def.match(s)).length
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* Left sidebar -- category nav, matches ConnectionsPage pattern */}
      <nav className="w-48 flex-shrink-0 border-r border-white/5 overflow-y-auto py-4 px-2">
        <div className="flex items-center gap-2 px-3 mb-4">
          <Sparkles size={14} className="text-starlight-500" />
          <h2 className="text-xs font-semibold text-starlight-500 uppercase tracking-wider">Skills</h2>
        </div>
        {CATEGORIES.map((cat) => {
          const count = countFor(cat.key)
          return (
            <button
              key={cat.key}
              onClick={() => setActiveCategory(cat.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-all mb-0.5 cursor-pointer ${
                activeCategory === cat.key
                  ? 'bg-primary-500/10 text-primary-400'
                  : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/[0.03]'
              }`}
            >
              {cat.icon}
              <span className="flex-1">{cat.label}</span>
              {count > 0 && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeCategory === cat.key
                    ? 'bg-primary-500/20 text-primary-400'
                    : 'bg-white/5 text-starlight-500'
                }`}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Main content area */}
      <div className="flex-1 overflow-y-auto p-6">
        <motion.div
          key={activeCategory}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.15 }}
          className="max-w-3xl space-y-4"
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-display font-bold text-starlight-100">
                {categoryDef.label}
              </h1>
              <p className="text-xs text-starlight-400">
                {activeCategory === 'all'
                  ? 'All registered skills with governance and permission controls'
                  : `Skills in the ${categoryDef.label} category`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* Batch permission controls */}
              <select
                onChange={(e) => {
                  const level = e.target.value as PermissionLevel
                  if (!level) return
                  const updated = { ...permissions }
                  finalFiltered.forEach((s) => { updated[s.id] = level })
                  setPermissions(updated)
                  localStorage.setItem('daena:skill_permissions', JSON.stringify(updated))
                  // Sync to backend
                  finalFiltered.forEach((s) => {
                    api.patch(`/skills/${s.id}`, { governance_tier: level === 'ALWAYS_ALLOW' ? 0 : level === 'ASK_EACH_TIME' ? 2 : 4 }).catch(() => {})
                  })
                  toast.success(`Set ${finalFiltered.length} skills to ${level === 'ALWAYS_ALLOW' ? 'Always Allow' : level === 'ASK_EACH_TIME' ? 'Needs Approval' : 'Blocked'}`)
                  e.target.value = ''
                }}
                className="px-2 py-1.5 rounded-lg text-xs bg-white/5 border border-white/10 text-starlight-400 cursor-pointer"
              >
                <option value="">Batch: Set all visible...</option>
                <option value="ALWAYS_ALLOW">Allow All</option>
                <option value="ASK_EACH_TIME">Ask All</option>
                <option value="BLOCK">Block All</option>
              </select>

              {/* Import Skill */}
              <button
                onClick={() => {
                  const input = document.createElement('input')
                  input.type = 'file'
                  input.accept = '.json,.md'
                  input.onchange = async (e) => {
                    const file = (e.target as HTMLInputElement).files?.[0]
                    if (!file) return
                    try {
                      const text = await file.text()
                      if (file.name.endsWith('.json')) {
                        const data = JSON.parse(text)
                        await api.post('/skills', {
                          name: data.name || file.name.replace('.json', ''),
                          description: data.description || 'Imported skill',
                          category: data.category || 'custom',
                          schema_def: data.schema || data,
                          governance_tier: 2,
                        })
                        toast.success(`Imported skill: ${data.name || file.name}`)
                        fetchSkills()
                      } else {
                        toast.info('Markdown skill import: file received. Manual registration needed.')
                      }
                    } catch (err) {
                      toast.error('Failed to import skill. Check file format.')
                    }
                  }
                  input.click()
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-primary-400 bg-primary-500/10 border border-primary-500/20 hover:bg-primary-500/20 cursor-pointer"
              >
                <Upload size={12} />
                Import Skill
              </button>
            </div>
          </div>

          {/* Search bar */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search skills by name or description..."
              className="w-full glass-input pl-9 pr-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
            />
          </div>

          {/* Content */}
          {loading ? (
            <Shimmer count={4} layout="list" />
          ) : finalFiltered.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title={
                search
                  ? 'No skills match your search'
                  : skills.length === 0
                    ? 'No skills registered yet'
                    : `No skills in ${categoryDef.label}`
              }
              description={
                search
                  ? undefined
                  : skills.length === 0
                    ? 'Import or create your first skill to get started.'
                    : `Switch to "All Skills" to see all ${skills.length} registered skills.`
              }
              action={
                skills.length === 0 && !search
                  ? {
                      label: 'Browse Skills',
                      onClick: () => setActiveCategory('all'),
                    }
                  : undefined
              }
            />
          ) : (
            <AnimatePresence mode="popLayout">
              <div className="space-y-2">
                {finalFiltered.map((skill, i) => (
                  <SkillCard
                    key={skill.id}
                    skill={skill}
                    permission={permissions[skill.id] ?? 'ASK_EACH_TIME'}
                    onPermissionChange={handlePermissionChange}
                    index={i}
                  />
                ))}
              </div>
            </AnimatePresence>
          )}
        </motion.div>
      </div>
    </div>
  )
}

export default SkillsPage
