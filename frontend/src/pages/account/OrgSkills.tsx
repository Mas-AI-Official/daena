/**
 * OrgSkills -- Organization-level skill management.
 * Equivalent to Perplexity's /account/org/skills
 */
import { Zap, Shield, Star } from 'lucide-react'

export function OrgSkills() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Skills</h1>
        <p className="text-sm text-starlight-400 mt-1">Organization-level skill policies and trust tiers</p>
      </div>

      <div className="space-y-4 max-w-lg">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Shield size={14} /> Skill governance
        </h3>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Auto-approve T2+ skills</p>
            <p className="text-[10px] text-starlight-500">Skills at Refined tier or above skip approval</p>
          </div>
          <input type="checkbox" defaultChecked className="rounded" />
        </label>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Allow skill extraction from chat</p>
            <p className="text-[10px] text-starlight-500">Skill Refinery can extract skills from conversations</p>
          </div>
          <input type="checkbox" defaultChecked className="rounded" />
        </label>

        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 pt-4">
          <Star size={14} /> Skill trust tiers
        </h3>
        <div className="space-y-1.5">
          {[
            { tier: 'T0', label: 'Raw', desc: 'Newly extracted, unverified', color: 'text-starlight-500' },
            { tier: 'T1', label: 'Draft', desc: 'Initial refinement pass', color: 'text-starlight-400' },
            { tier: 'T2', label: 'Refined', desc: 'Gap finder + improver + critic verified', color: 'text-accent-cyan' },
            { tier: 'T3', label: 'Production', desc: 'Founder-approved for production use', color: 'text-accent-amber' },
            { tier: 'T4', label: 'Compound', desc: 'Multi-skill compositions', color: 'text-accent-purple' },
          ].map((t) => (
            <div key={t.tier} className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-midnight-300/20">
              <span className={`text-xs font-mono font-bold ${t.color}`}>{t.tier}</span>
              <div>
                <p className="text-xs text-starlight-300">{t.label}</p>
                <p className="text-[10px] text-starlight-500">{t.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default OrgSkills
