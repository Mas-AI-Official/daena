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
import { Lock, Sparkles } from 'lucide-react'

import {
  type PluginCard,
  type SkillReadiness,
  skillReadiness,
  skillReadinessReason,
  skillReadinessTone,
} from './pluginCard'

interface SkillBundleSectionProps {
  plugin: PluginCard
}

export default function SkillBundleSection({ plugin }: SkillBundleSectionProps) {
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

              {isActive && (
                <div
                  role="status"
                  className="absolute left-0 right-auto top-full z-10 mt-1.5 w-64 rounded-md border border-white/10 bg-midnight-900/95 px-2.5 py-2 text-[11px] text-starlight-200 shadow-xl"
                >
                  {readiness === 'ready' ? (
                    <>
                      <p className="font-medium text-starlight-100">
                        {humanize(skill)}
                      </p>
                      <p className="mt-1 text-starlight-400">
                        Skill execution wiring pending. The next PR
                        connects this skill name to a prompt template
                        + tool call against {plugin.name}.
                      </p>
                    </>
                  ) : readiness === 'ready_metadata_only' ? (
                    <>
                      <p className="font-medium text-starlight-100">
                        {humanize(skill)}
                      </p>
                      <p className="mt-1 text-starlight-400">
                        This is a skill-pack prompt. Pair with a
                        runtime, MCP, or app that exposes the matching
                        tool to actually run it.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="font-medium text-starlight-100">
                        Locked: {humanize(skill)}
                      </p>
                      <p className="mt-1 text-starlight-400">{reason}</p>
                    </>
                  )}
                </div>
              )}
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
