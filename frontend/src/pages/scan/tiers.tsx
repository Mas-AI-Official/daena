/**
 * Tier definitions with JSX icons. Kept separate from types.ts so
 * pure-TS modules can import the type without dragging React in.
 */
import { Eye, Brain, Zap, Layers, Crosshair } from 'lucide-react'
import type { ScanTier } from './types'

export const TIERS: ScanTier[] = [
  {
    id: 'T1',
    name: 'Scout',
    description: 'Find vulnerabilities',
    features: ['Vulnerability detection', 'Severity classification', 'File-level findings'],
    price: 'Free',
    pipelineStages: 6,
    color: 'text-starlight-300',
    icon: <Eye size={20} />,
    locked: false,
  },
  {
    id: 'T2',
    name: 'Analyst',
    description: 'Find + explain + remediation',
    features: ['Everything in Scout', 'Detailed explanations', 'Remediation guidance', 'CVE mapping'],
    price: '$49/scan',
    pipelineStages: 12,
    color: 'text-accent-cyan',
    icon: <Brain size={20} />,
    locked: false,
  },
  {
    id: 'T3',
    name: 'Operator',
    description: 'Find + explain + fix code',
    features: ['Everything in Analyst', 'Auto-generated fix patches', 'Multi-model verification', 'Adversarial testing'],
    price: '$199/scan',
    pipelineStages: 17,
    color: 'text-primary-400',
    icon: <Zap size={20} />,
    locked: false,
  },
  {
    id: 'T4',
    name: 'Architect',
    description: 'Full analysis + verify + retest',
    features: ['Everything in Operator', 'Fix verification', 'Regression testing', 'Architecture review', 'Full reasoning chain'],
    price: '$499/scan',
    pipelineStages: 21,
    color: 'text-accent-amber',
    icon: <Layers size={20} />,
    locked: false,
  },
]

// T5 lives outside the public tier list and is only rendered when
// the elevated security mode is active (FOUNDER + activation
// command via /3vilbob). Secrecy contract: never listed in
// autocomplete, never in docs, never named by codename. Public
// label is simply "Founder" (access-level framing), not "Offensive"
// (which reads aggressive in customer demos).
export const T5_TIER: ScanTier = {
  id: 'T5',
  name: 'Founder',
  description: 'Founder-only defensive validation with proof-of-impact walkthrough',
  features: [
    'Everything in Architect',
    'Proof-of-impact paths',
    'Chain-of-evidence vault',
    'Network isolation controls',
    'Zero-false-positive gate (evidence required)',
  ],
  price: 'Founder',
  pipelineStages: 26,
  color: 'text-accent-amber',
  icon: <Crosshair size={20} />,
  locked: false,
}
