/**
 * GovernanceUpsellNotice -- inline routing-upsell callout for the chat surface.
 *
 * Rendered when a Council/Quintessence request gracefully degraded to STANDARD
 * (Rule 13) and the backend emitted a governance_notice carrying a structured
 * `upgrade` payload (chat.py, the only emitter that does). It turns the routing
 * wall into a click-to-checkout path that mirrors the org/402 wall, instead of
 * leaving the limit as a faded, non-actionable line in the thinking-log.
 *
 * Honest + additive (Rule 17): plan/feature come straight from the real event;
 * no fabricated perks, no always-on nag. Dismissible. The billing page stays
 * the source of truth for what is purchasable -- this only routes the user there.
 */
import { Link } from 'react-router-dom'
import { Sparkles, X, ArrowUpRight } from 'lucide-react'

interface GovernanceUpsellNoticeProps {
  feature: string
  plan: string
  onDismiss: () => void
}

export function GovernanceUpsellNotice({ feature, plan, onDismiss }: GovernanceUpsellNoticeProps) {
  const planLabel = plan.toUpperCase()
  return (
    <div className="flex justify-center py-2">
      <div className="flex items-start gap-3 max-w-xl w-full px-4 py-2.5 rounded-lg
                      border border-primary-500/40 bg-primary-500/10 backdrop-blur-sm">
        <Sparkles size={16} className="text-primary-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-starlight-100">
            {feature} routing needs the {planLabel} plan.
          </p>
          <p className="text-[12px] text-starlight-400 mt-0.5">
            You got a Standard answer this time.
          </p>
          <Link
            to="/account/billing#billing"
            className="inline-flex items-center gap-1 mt-2 px-3 py-1.5 rounded-md text-[12px]
                       font-medium text-white bg-primary-500/90 hover:bg-primary-500
                       border border-primary-400/40 transition-colors"
          >
            Upgrade to {planLabel}
            <ArrowUpRight size={12} />
          </Link>
        </div>
        <button
          onClick={onDismiss}
          className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer shrink-0"
          title="Dismiss"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
