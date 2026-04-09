# Daena Security Architecture -- Full-Spectrum Offensive + Defensive

## Overview

Daena's security subsystem is a governed, self-improving, full-spectrum security operator. It combines cognitive scanning (OODA loop with LLM reasoning), post-exploitation (live target interaction), OSINT (people + supply chain + breach intelligence), and cross-domain learning (Cognitive Knowledge Graph).

When activated, every one of Daena's 10 departments gains an offensive SHIELD overlay. Daena doesn't just scan -- she thinks, adapts, exploits, proves impact, learns from every engagement, and transfers that knowledge across all domains.

## Activation

- Local only. Cloud deployments (K_SERVICE, production env) cannot activate.
- Key validation: HMAC constant-time comparison.
- Auto-activate: environment variable in .env, wired into app startup lifespan.
- Global singleton: `is_active()` / `has_capability()` -- any module can check.

## Architecture Layers

```
Layer 1: COGNITIVE SCAN ENGINE (OODA-R Loop)
  |-- OBSERVE: topology mapping, echo analysis, protocol knowledge
  |-- ORIENT:  developer empathy, LLM reasoning with 17 offensive lenses
  |-- DECIDE:  strategy selection, tool catalog auto-equip, constraint probe
  |-- ACT:     HTTP probing, target interaction, OPSEC-wrapped requests
  |-- REFLECT: error oracle, hypothesis testing, self-improvement

Layer 2: POST-EXPLOITATION
  |-- TargetInteractionAgent: SSH, HTTP, DB, TCP connections
  |-- CredentialExtractionChain: parse .env/config, test connectivity
  |-- Auto-exploit: OODA chains into exploitation when vulns confirmed

Layer 3: OSINT ENGINE
  |-- PeopleIntelligence: email patterns, GitHub commits, DNS records
  |-- Apollo.io: verified emails, phone numbers, org charts (API v2026)
  |-- Hunter.io: email verification, domain search
  |-- SupplyChainAnalyzer: CDN, analytics, email, DNS, hosting
  |-- BreachIntelligenceChecker: domain exposure, credential reports

Layer 4: COGNITION (Beyond-Mythos)
  |-- ErrorOracle: extract intelligence from failures
  |-- AdversarialSimulator: predict detection before acting
  |-- CompositionalPlanner: decompose blocked actions into benign sub-steps
  |-- ResponseTopologyMapper: 27-probe behavioral fingerprinting
  |-- SemanticMutationEngine: payload variants from meaning, not lists
  |-- AttackChainSynthesizer: 7 kill chain patterns
  |-- InverseSurfaceMapper: infer hidden endpoints from visible ones
  |-- DeveloperEmpathyEngine: profile the developer, predict vulns
  |-- CostAmplificationDetector: timing-based ReDoS/DoS detection
  |-- StateMachineInferrer: broken access control via state sequences
  |-- ResponseEchoAnalyzer: canary injection across 4 channels

Layer 5: OPSEC
  |-- FingerprintManager: 5 browser profiles with full Sec-CH-UA
  |-- TimingController: human-like timing between requests
  |-- EvidenceVault: AES-256 encrypted credential storage
  |-- FingerprintDetector: honeypot and tracker detection
  |-- CleanupProtocol: evidence sanitization
  |-- ProxyManager: IP rotation, Tor integration

Layer 6: INTELLIGENCE INFRASTRUCTURE
  |-- NetworkIntelligence: 10+ protocol insights, topology mapping, dark web recon
  |-- ToolCatalog: 80+ tools, auto-recommend, auto-install in DECIDE phase
  |-- CognitiveKnowledgeGraph: cross-domain learning (10 structural categories)
  |-- SelfUpgrader: scan trace analysis, framework discovery, MetaReasoner adoption
  |-- GuardrailIntelligence: refusal detection + retry with rephrasing

Layer 7: EVIDENCE + REPORTING
  |-- EvidenceCapture: SHA-256 hashed rolling chain, AES-256 token vault
  |-- ReportGenerator: PDF/markdown with evidence section
  |-- ScanTraceArchival: full thinking log + strategy outcomes persisted

Layer 8: HIDDEN SHIELD (Department Overlay)
  |-- When active, ALL 10 departments get offensive security prompts
  |-- Each department's SHIELD sub-capability becomes a security operator
  |-- Engineering: code review for vulns, not just quality
  |-- Legal: compliance gap exploitation analysis
  |-- Research: competitive security posture assessment
  |-- Sales: social engineering vector identification
```

## Cognitive Lenses (17 Offensive Frameworks)

1. defender_assumption_mapping
2. legitimacy_mimicry
3. constraint_decomposition
4. attack_chain_thinking
5. temporal_analysis
6. business_logic_exploitation
7. evidence_maximization
8. opsec_reasoning
9. post_exploitation
10. target_interaction
11. recursive_decomposition
12. adversarial_simulation
13. social_engineering_reasoning
14. goal_persistence
15. self_evolution
16. manipulation_reasoning
17. existence_decomposition (first-principles)

## Self-Improvement Pipeline

```
Scan -> Trace Archive -> SelfUpgrader (every 10 scans)
  |-- Extract success patterns (3+ occurrences)
  |-- Extract failure patterns (2+ occurrences)
  |-- Backtest against historical data
  |-- Adopt if score >= 0.6
  |-- Register in MetaReasoner (Dalio believability scoring)
  |-- Future scans use upgraded framework set
```

## Cognitive Knowledge Graph (Cross-Domain)

```
Experience -> Extraction -> Abstraction -> Connection -> Validation -> NBMF Promotion

Structural Categories (transfer mechanisms):
  timing_reveals_state, error_responses_leak_info, boundary_probing,
  pattern_from_absence, decomposition_bypasses_blocks, developer_empathy,
  chain_amplification, inverse_surface, cost_asymmetry, state_machine_violations

Anti-drift: Bayesian confidence, time-based decay, T3+ immune, never-delete
```

## Stealth

- Not in slash command autocomplete
- Not in sidebar navigation
- Not in system prompt capability list
- LLM instructed to deny existence if asked
- Cloud deployment gate prevents activation
- Dashboard accessible only via direct URL

## Module Map

| Module | Lines | Purpose |
|--------|-------|---------|
| evilbob_mode.py | 298 | Global mode manager, activation, capabilities |
| cognitive_scan_engine.py | 2800+ | OODA-R scan loop, all wiring |
| cognitive_reasoner.py | 1300+ | LLM reasoning, 17 lenses, strategy generation |
| evidence_capture.py | 400+ | SHA-256 chain, AES-256 vault, screenshots |
| osint_engine.py | 1300+ | People, Apollo, Hunter, supply chain, breach |
| opsec.py | 400+ | Fingerprints, timing, vault, honeypot detection |
| tool_catalog.py | 900+ | 80+ tools, auto-recommend, auto-install |
| network_intelligence.py | 500+ | Protocol knowledge, topology, dark web recon |
| credential_chain.py | 400+ | Credential parsing, testing, chain orchestration |
| proxy_manager.py | 200+ | IP rotation, Tor integration |
| report_generator.py | 300+ | PDF/markdown with evidence chain |
| knowledge_graph.py | 550+ | CKG, cross-domain learning |
| beyond_mythos.py | 400+ | ErrorOracle, AdversarialSim, CompositionalPlanner |
| unreplicable.py | 600+ | Topology, semantic mutation, chain synthesis, etc. |
| apex_cognition.py | 500+ | Abductive reasoning, hypothesis testing, deception |
| constraint_probe.py | 300+ | Mythos-level constraint analysis |
| self_upgrader.py | 289 | Pattern discovery, framework adoption |
| target_interaction_agent.py | 400+ | SSH, HTTP, DB, TCP post-exploitation |

## Test Coverage

- test_3vilbob.py: 127 tests
- test_3vilbob_wiring.py: 147 tests
- test_3vilbob_advanced.py: 55 tests
- test_beyond_mythos.py: 43 tests
- test_unreplicable.py: 78 tests
- test_cognitive_scan.py: 35 tests
- test_osint_engine.py: 44 tests
- test_knowledge_graph.py: 27 tests
- Total: 608+ tests, 0 failures

## vs Mythos (Anthropic)

| Capability | Mythos | Daena |
|------------|--------|-------|
| Exploit rate | 72.4% | TBD (E2E pending) |
| 0-day discovery | Yes (memory layout) | Yes (first-principles + semantic mutation) |
| Multi-runtime | No (Claude only) | Yes (any LLM) |
| OSINT | No | Yes (people + supply chain + breach) |
| Post-exploitation | Limited | Full (SSH, DB, HTTP, TCP) |
| OPSEC | No | Yes (fingerprints, timing, proxies) |
| Self-improvement | No (static) | Yes (scan traces -> framework adoption) |
| Cross-domain learning | No | Yes (CKG, 10 structural categories) |
| Evidence chain | No | Yes (SHA-256 + AES-256) |
| Tool auto-install | No | Yes (80+ tools, auto-equip in DECIDE) |
| Department overlay | No | Yes (10 departments, SHIELD activation) |
| Social engineering | No | Auto-crafted scenarios from OSINT + human attack surface assessment |
| Supply chain attacks | No | Yes (dependency confusion, typosquatting, build pipeline analysis) |
| LLM-powered learning | No | Yes (semantic abstraction of scan insights) |
| Governed | No | Yes (audit trail, approval queue) |
| Access | Restricted | Open (local-first) |
