/**
 * FirstSkillRunBlock -- Sprint-7 PR-4 (2026-05-04).
 *
 * Hero block in the plugin detail drawer that surfaces the FIRST
 * recommended read-only skill for that plugin. For Filesystem MCP
 * the recommended first skill is `find_files`. Click runs the skill
 * via the existing Phase 2 read-only executor (SkillExecuteModal).
 *
 * Honesty contract:
 *   - The block is rendered ONLY when:
 *       (a) the plugin has a registered first-run skill below, AND
 *       (b) the (plugin, skill) pair is in the Phase 2 allowlist, AND
 *       (c) plugin.skillReadiness === 'ready'.
 *     If any of those is false, the block returns null gracefully.
 *   - When the plugin exists but is not yet callable, the block
 *     instead renders a small "Install + probe first" hint pointing
 *     at the FirstCallableWizard's Continue path. We never claim
 *     callable when the V2 row says otherwise.
 *   - The actual run goes through SkillExecuteModal, which already
 *     surfaces the no-writes/no-deletes/no-external-network
 *     confirmation BEFORE the operator hits Run. We do NOT bypass
 *     that confirmation.
 *
 * Out of scope (deferred):
 *   - Inline result preview (Phase 2 returns "planned" -- the modal
 *     already shows the preview).
 *   - Auto-fill of the folder input. The operator MUST type or
 *     paste a path themselves.
 */

import { useState } from 'react'
import { FolderOpen, Play, Sparkles } from 'lucide-react'

import {
  type PluginCard,
  skillReadiness,
} from './pluginCard'
import SkillExecuteModal, {
  type Phase2AllowlistRow,
} from './SkillExecuteModal'
import { usePhase2SkillAllowlist } from '@/hooks/usePhase2SkillAllowlist'


// Plugin -> recommended first-run skill. Conservative: only map plugins
// where we have HIGH confidence the skill is read-only AND useful at
// first-run AND in the Phase 2 allowlist. Others go to the existing
// chip flow.
const FIRST_RUN_SKILLS: Record<string, {
  skill_id: string
  pretty_label: string
  why: string
}> = {
  'mcp-filesystem': {
    skill_id: 'find_files',
    pretty_label: 'Run find_files',
    why: 'Search for files by name pattern in a folder you allow. Read-only -- never writes, deletes, or sends.',
  },
}


interface FirstSkillRunBlockProps {
  plugin: PluginCard
}


export default function FirstSkillRunBlock({ plugin }: FirstSkillRunBlockProps) {
  const recipe = FIRST_RUN_SKILLS[plugin.id]
  const readiness = skillReadiness(plugin)
  const { lookup: lookupPhase2 } = usePhase2SkillAllowlist()
  const [modalOpen, setModalOpen] = useState(false)

  // Sync lookup -- the hook keeps the allowlist cached after first load.
  const allowlistRow: Phase2AllowlistRow | null = recipe
    ? lookupPhase2(plugin.id, recipe.skill_id) ?? null
    : null

  // No recipe registered for this plugin -- block is silent.
  if (!recipe) return null

  // Plugin recognized but not callable yet -- show a small hint and
  // route the operator back to the install + probe path. We do NOT
  // pretend the run is available.
  if (readiness !== 'ready') {
    return (
      <section
        data-testid="first-skill-run-block-locked"
        className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3"
      >
        <div className="flex items-start gap-2">
          <Sparkles size={14} className="mt-0.5 shrink-0 text-amber-300" />
          <div>
            <h4 className="text-xs font-semibold text-amber-100">
              Try your first Daena skill (almost there)
            </h4>
            <p className="mt-1 text-[11px] text-amber-200/80">
              Once {plugin.name} is callable, this block will let you run{' '}
              <code className="rounded bg-amber-500/10 px-1">{recipe.skill_id}</code>{' '}
              read-only with one click. To get there: install via the MCP Store,
              then click <strong>Probe</strong> on the V2 row.
            </p>
          </div>
        </div>
      </section>
    )
  }

  // Recipe exists + plugin is callable, but the (plugin, skill) pair
  // isn't in the Phase 2 allowlist (yet). Don't fabricate a button --
  // fall back silently.
  if (!allowlistRow) return null

  return (
    <>
      <section
        data-testid="first-skill-run-block"
        className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-300">
              <FolderOpen size={16} />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-[0.22em] text-emerald-300">
                Try your first Daena skill
              </p>
              <h3 className="mt-1 text-sm font-semibold text-starlight-100">
                {recipe.pretty_label}{' '}
                <span className="ml-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-emerald-200">
                  read-only
                </span>
              </h3>
              <p className="mt-1 max-w-xl text-[11px] text-starlight-300">
                {recipe.why}
              </p>
            </div>
          </div>
          <button
            data-testid="first-skill-run-button"
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 hover:bg-emerald-500/20"
          >
            <Play size={12} />
            Run {recipe.skill_id}
          </button>
        </div>

        <p className="mt-3 text-[10px] text-starlight-400">
          The run goes through Daena's Phase 2 read-only executor. You'll see
          a confirmation modal that lists exactly what {recipe.skill_id} reads
          before it runs. Phase 2 NEVER writes, deletes, or sends external
          messages -- those require explicit Phase 3 enablement which is
          still off.
        </p>
      </section>

      {modalOpen && allowlistRow && (
        <SkillExecuteModal
          pluginId={plugin.id}
          pluginName={plugin.name}
          skillId={recipe.skill_id}
          allowlistRow={allowlistRow}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  )
}
