/**
 * SkillBundleSection -- honeycomb-style skill chip cluster.
 *
 * PR-CONN-PLUGIN-SKILLS-UX-WIRING (2026-05-03): renders a plugin's
 * `default_skills` as visually distinct chips inside the detail
 * drawer. Each chip is a rounded pill prefixed with a small hexagon
 * glyph -- a subtle nod to Daena's sunflower-honeycomb topology
 * codename without turning the drawer into a spiral dashboard.
 *
 * Honesty (founder rule 11):
 *   - The component NEVER executes a skill. Click handlers only
 *     surface a placeholder -- "Skill execution wiring pending" for
 *     ready chips, "Connect <plugin> first" for locked chips.
 *   - Lock truth comes from `skillReadiness(plugin)` so the chip can
 *     never disagree with the card's status pill.
 *   - When the bundle is empty (catalog entry hasn't been bumped yet)
 *     we fall back to the plugin's legacy `included_skills` so old
 *     entries still surface SOMETHING instead of an empty section.
 *
 * Layout (Daena math, lightly applied):
 *   - Chips wrap as a flex grid.
 *   - Every other ROW is shifted right by 6px to evoke a honeycomb
 *     pack without computing real hex coordinates.
 *   - Single hex SVG glyph as the leading icon (clip-path polygon).
 *
 * No new dependencies; pure CSS + Tailwind.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Lock, Play, ShieldAlert, Sparkles } from 'lucide-react'

import {
  type PluginCard,
  type SkillReadiness,
  skillReadiness,
  skillReadinessReason,
  skillReadinessTone,
} from './pluginCard'
// PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1 (2026-05-03): chip clicks now
// resolve through a typed action registry. Phase 1 only drafts into
// chat -- never executes a tool, never sends external messages.
import {
  resolveSkillAction,
  type ResolvedSkillAction,
} from './skillActionRegistry'
import { draftMessage } from '@/lib/composerBridge'
import { toast } from '@/stores/toastStore'
// PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03):
// Phase 2 surfaces a "Run read-only skill" button on chips whose
// (plugin, skill) pair is in the backend allowlist AND whose plugin
// readiness is "ready". Phase 1 chat-draft path stays available
// regardless -- Phase 2 is additive.
import SkillExecuteModal, {
  type Phase2AllowlistRow,
} from './SkillExecuteModal'
import { usePhase2SkillAllowlist } from '@/hooks/usePhase2SkillAllowlist'

interface SkillBundleSectionProps {
  plugin: PluginCard
  /** Optional: parent (drawer) hands us its onClose so a successful
   * draft hand-off can close the drawer before navigating to /chat,
   * mirroring the suggested-prompt button flow. */
  onCloseParent?: () => void
}

export default function SkillBundleSection({
  plugin, onCloseParent,
}: SkillBundleSectionProps) {
  // Prefer bundle skills (Codex-style snake_case names); fall back to
  // legacy capabilities so entries that haven't been bumped to the
  // new schema still render something. The catalog adapter already
  // populates `included_skills` with the same precedence, so we read
  // from the canonical view-model field for consistency.
  const skills = plugin.included_skills
  const readiness = skillReadiness(plugin)
  const tone = skillReadinessTone(readiness)
  const reason = skillReadinessReason(plugin)
  const [activeChip, setActiveChip] = useState<string | null>(null)
  const [phase2Modal, setPhase2Modal] = useState<{
    skill_id: string
    row: Phase2AllowlistRow
  } | null>(null)
  const navigate = useNavigate()
  const { lookup: lookupPhase2 } = usePhase2SkillAllowlist()

  if (skills.length === 0) {
    return (
      <p className="text-[11px] text-starlight-500">
        This plugin has no declared skill bundle yet. Once Daena documents
        a default skill list, it will appear here.
      </p>
    )
  }

  // Convert snake_case skill identifier into a human-readable label.
  // "triage_issues" -> "Triage issues", "review_pull_request" ->
  // "Review pull request". Single-word skills capitalize as-is.
  function humanize(skill: string): string {
    const words = skill.split('_')
    if (words.length === 0) return skill
    return words
      .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
      .join(' ')
  }

  function handleChipClick(skill: string) {
    // Toggle the inline reveal under the chip. Never invokes a tool.
    setActiveChip((cur) => (cur === skill ? null : skill))
  }

  /** PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1: drop the resolved
   * draft_text into the chat composer and navigate. NEVER auto-sends.
   * Mirrors the suggested-prompt flow in PluginDetailDrawer.DaenaIntent. */
  function handleUseInChat(skill: string, resolved: ResolvedSkillAction) {
    if (!resolved.draft_text) {
      // Defensive: if a registry entry has no template (shouldn't
      // happen for allowed entries; would happen for unsupported)
      // surface a toast and bail rather than silently doing nothing.
      toast.info('No draft template registered for this skill yet.')
      return
    }
    draftMessage(resolved.draft_text, {
      surface: 'connections.skill_chip',
      plugin_id: plugin.id,
      plugin_name: plugin.name,
    })
    const fromLabel =
      resolved.effective_action === 'blocked_high_risk_consent_missing'
        ? `Drafted plan from ${plugin.name}: opening chat...`
        : `Drafted skill from ${plugin.name}: opening chat...`
    toast.success(fromLabel)
    onCloseParent?.()
    setTimeout(() => navigate('/chat'), 80)
  }

  return (
    <div>
      {/* Cluster header: status indicator + plain-English readiness */}
      <div
        className={`mb-2 flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-[11px] ${tone.border} ${tone.bg}`}
      >
        {readiness === 'ready' ? (
          <Sparkles size={12} className={`mt-0.5 shrink-0 ${tone.hex}`} />
        ) : readiness === 'ready_metadata_only' ? (
          <Sparkles size={12} className={`mt-0.5 shrink-0 ${tone.hex}`} />
        ) : (
          <Lock size={11} className={`mt-0.5 shrink-0 ${tone.hex}`} />
        )}
        <span className={tone.text}>{reason}</span>
      </div>

      {/* Honeycomb cluster: flex-wrap grid, every other row offset 6px.
          The offset is achieved by giving even-index chips a small
          left margin via a CSS counter trick (nth-child). */}
      <ul className="flex flex-wrap gap-1.5 honeycomb-cluster">
        {skills.map((skill) => {
          const isActive = activeChip === skill
          return (
            <li key={skill} className="relative">
              <button
                type="button"
                onClick={() => handleChipClick(skill)}
                title={
                  readiness === 'ready'
                    ? 'Skill ready. Click for details.'
                    : reason
                }
                className={`group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition-colors ${tone.border} ${tone.bg} ${tone.text} hover:bg-white/[0.06]`}
              >
                <HexGlyph className={tone.hex} />
                <span className="font-medium">{humanize(skill)}</span>
                {readiness !== 'ready' && readiness !== 'ready_metadata_only' && (
                  <Lock size={9} className={`${tone.hex} opacity-80`} />
                )}
              </button>

              {isActive && (() => {
                // PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1: chip click
                // opens the registry-driven popover. The popover
                // surfaces an action button when the registry has a
                // safe draft for this (plugin, skill) pair; falls
                // back to an explanatory locked / pending state
                // otherwise.
                const resolved = resolveSkillAction(plugin, skill, readiness)
                const isBlocked =
                  resolved.effective_action === 'blocked_high_risk_consent_missing'
                const isPlan = resolved.effective_action === 'action_plan'
                const isDraft = resolved.effective_action === 'composer_draft'
                const offersChatAction = isDraft || isPlan || (isBlocked && resolved.draft_text)
                const buttonLabel = isBlocked
                  ? 'Draft plan in chat'
                  : isPlan
                    ? 'Draft action plan'
                    : 'Use in chat'
                // PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY:
                // surface "Run read-only skill" only when the backend
                // allowlist returns an entry AND the plugin is callable
                // (readiness === 'ready'). Phase 2 NEVER offers Run on
                // a locked / not-callable plugin.
                const phase2Row = readiness === 'ready'
                  ? lookupPhase2(plugin.id, skill)
                  : undefined
                const offersPhase2Run = !!phase2Row
                return (
                  <div
                    role="status"
                    className="absolute left-0 right-auto top-full z-10 mt-1.5 w-72 rounded-md border border-white/10 bg-midnight-900/95 px-2.5 py-2 text-[11px] text-starlight-200 shadow-xl"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-starlight-100">
                        {humanize(skill)}
                      </p>
                      {isBlocked && (
                        <ShieldAlert size={11} className="mt-0.5 shrink-0 text-amber-300" />
                      )}
                    </div>
                    <p className="mt-1 text-starlight-400">
                      {resolved.inline_message}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {offersChatAction && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleUseInChat(skill, resolved)
                          }}
                          className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors ${
                            isBlocked
                              ? 'border-amber-500/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20'
                              : 'border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20'
                          }`}
                        >
                          {buttonLabel} <ArrowRight size={9} />
                        </button>
                      )}
                      {offersPhase2Run && phase2Row && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPhase2Modal({ skill_id: skill, row: phase2Row })
                            setActiveChip(null)
                          }}
                          className="inline-flex items-center gap-1 rounded-md border border-primary-500/40 bg-primary-500/15 px-2 py-1 text-[10px] font-medium text-primary-100 hover:bg-primary-500/25"
                          title="Phase 2 read-only: opens a confirmation modal with required inputs"
                        >
                          <Play size={9} /> Run read-only skill
                        </button>
                      )}
                    </div>
                  </div>
                )
              })()}
            </li>
          )
        })}
      </ul>

      {/* Footer hint -- "what next" copy ties chip cluster to the
          rest of the drawer (test button / setup steps). */}
      <p className="mt-2 text-[10px] text-starlight-500">
        Skills become executable once {plugin.name} reaches{' '}
        <code className="rounded bg-white/[0.04] px-1">callable</code>{' '}
        in the probe ladder above.
      </p>

      {/* PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY: confirmation
          modal for the Run button. Mounted at section root so its
          fixed-position overlay isn't trapped inside the chip popover. */}
      {phase2Modal && (
        <SkillExecuteModal
          pluginId={plugin.id}
          pluginName={plugin.name}
          skillId={phase2Modal.skill_id}
          allowlistRow={phase2Modal.row}
          onClose={() => setPhase2Modal(null)}
        />
      )}
    </div>
  )
}

/** Tiny hex glyph rendered as a clip-path on a colored block. Avoids
 * adding an SVG asset; the polygon is hard-coded for a flat-top hex. */
function HexGlyph({ className }: { className: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-2 w-2 ${className} bg-current`}
      style={{
        clipPath:
          'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
      }}
    />
  )
}

// Re-export readiness for parents that want to gate other UX on it
// without re-importing from pluginCard.
export type { SkillReadiness }
