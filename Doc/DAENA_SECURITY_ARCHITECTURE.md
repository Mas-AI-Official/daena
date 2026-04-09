# Daena Security Architecture -- Offensive Intelligence System

## 14 Modules, 39 Capabilities

```
MODULE 1: evilbob_mode.py (Gate)
  [1] Mode Manager -- activation, key validation, capability check

MODULE 2: cognitive_scan_engine.py (Brain -- OODA Loop)
  [2] OODA-R Scan Loop -- 15-phase cognitive cycle
  [3] Auto-Exploit Chain -- proves impact mid-scan via TargetInteractionAgent
  [4] Exploitability Classifier -- which findings can be auto-exploited
  [5] Impact Assessor -- translates raw output to human-readable impact

MODULE 3: cognitive_reasoner.py (Intelligence)
  [6] LLM Reasoning with 16 Offensive Lenses -- orient/decide/reflect
  [7] Novel Strategy Generation -- LLM creates attack paths nobody hardcoded
  [8] Quintessence Debate -- 3 models argue about exploitation paths (AGI mode)

MODULE 4: constraint_probe.py (Mythos)
  [9] Constraint Decomposition -- find gaps between stated and enforced

MODULE 5: beyond_mythos.py (Beyond Mythos)
  [10] ErrorOracle -- extract intelligence from failures
  [11] AdversarialSimulator -- predict defender detection before acting
  [12] CompositionalPlanner -- decompose blocked attacks into benign steps

MODULE 6: unreplicable.py (Unreplicable)
  [13] ResponseTopologyMapper -- behavioral fingerprint from 27 probe variations
  [14] SemanticMutationEngine -- infinite payloads from meaning, not lists
  [15] AttackChainSynthesizer -- connect findings into kill chains
  [16] InverseSurfaceMapper -- infer hidden endpoints from visible ones
  [17] DeveloperEmpathyEngine -- model the human, predict the flaw
  [18] ResponseEchoAnalyzer -- one canary tests 4 vuln classes
  [19] StateMachineInferrer -- find broken access control via sequences
  [20] CostAmplificationDetector -- find ReDoS/amplification by timing

MODULE 7: apex_cognition.py (Apex)
  [21] AbductiveReasoner -- Sherlock Holmes inference from observations
  [22] GoalDecomposer -- recursive search tree with live pruning
  [23] HypothesisTester -- scientific method for hacking
  [24] EmergentVulnFinder -- find vulns in component interactions
  [25] CognitiveDeceptionEngine -- mislead defender systems with decoys

MODULE 8: osint_engine.py (People Intelligence)
  [26] OSINTPeopleIntelligence + Hunter + Apollo -- find real contacts
  [27] SupplyChainAnalyzer -- map every third-party dependency
      BreachIntelligenceChecker -- check breach exposure

MODULE 9-13: Supporting
  target_interaction_agent.py -- SSH/HTTP/DB/TCP post-exploitation
  evidence_capture.py -- SHA-256 tamper-evident proof chain
  proxy_manager.py -- IP rotation + legitimacy mimicry
  report_generator.py -- PDF/markdown with evidence

MODULE 14: mission_intelligence.py (Autonomous Brain)
  [28] MissionGraph -- living detective-wall knowledge graph
       Nodes: goal, entity, credential, endpoint, vulnerability,
       document, technique, evidence, chain_link, dead_end, insight, persona
       Edges: leads_to, requires, blocks, bypasses, authenticates,
       exposes, inferred, contradicts, alternative, chain_next, reverses_to
       Persists to disk, resumes across sessions
  [29] GoalBackwardPlanner -- starts from objective, works backward
       Generates 3-5 independent attack paths per mission:
       technical, social, supply_chain, insider, physical
       Each path maps steps to existing Daena modules (no duplication)
  [30] ChainFollower -- autonomous chain traversal with 4 directions:
       forward (A leads to B), backward (need Y, what leads to Y?),
       lateral (X failed, what's similar?), inversion (make target come to ME)
       Dead end handling: mark, don't delete. Zoom out, find new path.
  [31] EngagementLevel -- 4 levels (the nuke doctrine):
       AUDIT (find, report), PENTEST (exploit, prove),
       RED_TEAM (full chain, minimal traces), ADVERSARY (full chain, clean traces)
  [32] MissionController -- autonomous mission orchestrator
       start_mission(goal, target, level) -> plans + executes everything
       execute_next_step() -> drives step-by-step with auto-adaptation
       resume(mission_id) -> picks up exactly where it left off
  [33] BidirectionalReasoning -- inversion thinking baked into ChainFollower
       "Don't go TO target, make target come to YOU"
       honey_service, content_lure, community_positioning, watering_hole
  [34] ProximityMapper -- maps 6 rings around target (Ring 0-5)
       Ring 0: target (hardened), Ring 1: direct contacts (bodyguard),
       Ring 2: professional network, Ring 3: community, Ring 4: infrastructure,
       Ring 5: public presence (GitHub, job posts, DNS)
       Finds weakest link: Ring 1 entities with lowest security
       Finds easiest chain: best value/difficulty ratio path through rings
       "You don't hack Elon. You read his bodyguard's unlocked phone."
  [35] AttractionSimulator -- 5 "target comes to you" techniques
       watering_hole: compromise sites they visit
       honeypot: fake internal tool at typo domain
       content_lure: SEO-targeted tech guide with callback
       social_bait: fake recruiter/investor persona
       service_impersonation: typo email domain catch-all
       Each scenario: setup steps, time estimate, success probability, legal notes
       Ranked by expected value (probability * speed * stealth)
  [36] CreativePathGenerator -- 7 LLM-driven "outside the box" lenses
       constraint_removal: "What if the firewall didn't exist?"
       perspective_shift: "The janitor has a key to every room"
       resource_inversion: "1000 employees = 1000 phishing targets"
       time_manipulation: "60-second vs 60-day attack"
       domain_transfer: "This is a logistics problem, not a security one"
       chain_of_trivials: "Each step is easy. The chain is lethal."
       reverse_social_proof: "Post a job listing. They apply with their resume = org chart."
       Uses CognitiveReasoner with creative prompts (no duplication)
  [37] TraceManager -- catalogs every trace left during operation
       Records: log_entry, file_artifact, network_connection, dns_query,
       process, credential_use, database_query, api_call, cookie, cache_entry
       clean_all(): ADVERSARY-only full trace cleanup
       get_forensic_report(): Daena's internal audit trail for client delivery
       Permanent traces flagged (ISP logs, auth events cannot be cleaned)
  [38] EngagementController -- capability matrix enforcement
       14-capability matrix across 4 engagement levels
       enforce(): blocks operations not allowed at current level
       override(): operator can unlock specific capabilities
       Prevents scope creep (PENTEST can't clean traces, AUDIT can't exploit)
  [39] OpSecShield -- governance protecting DAENA herself
       check_outbound_request(): blocks identifying headers/user-agents
       check_evidence_storage(): ensures vault-only storage
       check_no_data_leak(): prevents leaking Daena/MAS-AI/operator info
       Scans for: daena, mas-ai, masoud, evilbob, sunflower-honeycomb, philattice, nbmf
       Auto-activates at RED_TEAM and ADVERSARY levels
```

## How MissionIntelligence Drives Everything

```
USER: "Prove you can transfer $0.01 from ClientCorp treasury"

MissionController.start_mission()
  |
  v
GoalBackwardPlanner.plan_from_goal()
  |-- GOAL: transfer $0.01
  |-- BACKWARD: need treasury access
  |-- BACKWARD: need auth to wire system
  |-- BACKWARD: need credentials of approver
  |-- BACKWARD: need access to internal network
  |-- BACKWARD: need initial foothold
  |-- GENERATES 3-5 PATHS:
  |   Path A (technical): OSINT -> scan -> exploit -> lateral -> treasury
  |   Path B (social): OSINT -> profile CFO -> phish -> credentials -> treasury
  |   Path C (supply chain): map vendors -> weakest link -> pivot -> treasury
  |   Path D (insider): org chart -> access map -> simulate insider
  |   Path E (physical): events -> conference WiFi -> intercept
  |
  v
MissionGraph builds detective wall as it goes
  |-- Every discovery = node
  |-- Every connection = edge
  |-- Dead ends marked, not deleted
  |-- Unexplored leads prioritized
  |
  v
ChainFollower drives execution
  |-- Follows chain forward until dead end
  |-- Dead end? Zoom out to graph
  |-- Try lateral (similar nodes)
  |-- Try inversion (reverse approach)
  |-- Try unexplored leads
  |-- NEVER stops until goal achieved or all paths exhausted
  |
  v
MissionController.execute_next_step()
  |-- Routes each step to existing modules:
  |   osint_engine -> people intel, supply chain
  |   cognitive_scan_engine -> OODA vulnerability scan
  |   credential_chain -> credential extraction
  |   red_team_ops -> social eng, exfil, monitoring
  |   opsec -> fingerprint, timing, cleanup
  |   cognition -> developer empathy, reasoning
  |
  v
Graph persists to disk -> resume across sessions
  |-- controller.save() -> var/missions/{id}.json
  |-- MissionController.resume(id) -> picks up exactly where left off
  |
  v
REPORT: here's what we did, here's what you missed
  |-- Full graph visualization (detective wall)
  |-- Attack paths with step-by-step evidence
  |-- Detection gaps (what your SOC didn't catch)
  |-- Remediation recommendations
```

## How They Combine (The OODA Flow)

```
PHASE 1: OBSERVE
  |-- Subdomain enumeration
  |-- HTTP probe (live hosts + tech fingerprint)
  |-- [17] DeveloperEmpathyEngine profiles the human
  |
PHASE 2: ORIENT
  |-- [6] CognitiveReasoner with 16 offensive lenses
  |-- [8] Quintessence multi-model debate (AGI mode)
  |-- Target classification (LLM or deterministic)
  |
PHASE 3: INVERSE SURFACE
  |-- [16] InverseSurfaceMapper infers hidden endpoints
  |-- Adds inferred URLs to interesting_paths
  |
PHASE 4: DECIDE
  |-- Template strategies (passive, headers, paths, vuln scan)
  |-- [14] SemanticMutationEngine adds WAF bypass strategy
  |-- [7] LLM generates novel strategies
  |-- [22] GoalDecomposer decomposes specific objectives
  |-- Pick best untried strategy
  |
PHASE 5: ADVERSARIAL SIMULATION
  |-- [11] AdversarialSimulator predicts detection for each step
  |-- Auto-adjusts params for stealth (browser headers, timing)
  |
PHASE 6: ACT
  |-- Execute strategy steps via VulnScannerAgent
  |-- [14] SemanticMutation payloads for WAF bypass
  |
PHASE 7: EVIDENCE CAPTURE
  |-- Screenshot, curl command, response snapshot
  |-- Token extraction + AES-256 vault
  |
PHASE 8: AUTO-EXPLOIT
  |-- [4] Classify which findings are exploitable
  |-- [3] Dispatch TargetInteractionAgent (HTTP/SSH/DB/TCP)
  |-- [5] Assess impact in human-readable terms
  |-- Feed results back as new findings
  |
PHASE 9: REFLECT
  |-- LLM reflects on success/failure
  |-- 5 Whys root cause analysis
  |-- [9] Constraint probe for alternative channels
  |
PHASE 10: ERROR ORACLE
  |-- [10] Extract intelligence from every error response
  |-- Differential response comparison
  |
PHASE 11: ABDUCTIVE REASONING
  |-- [21] Infer what MUST be true from observations
  |-- Generate testable predictions
  |
PHASE 12: HYPOTHESIS GENERATION
  |-- [23] Generate hypotheses from observations
  |-- Queue for testing in next cycle
  |
[REPEAT cycles 1-12]
  |
PHASE 13: ATTACK CHAIN SYNTHESIS
  |-- [15] Connect findings into kill chains
  |-- Escalate severity (info + info = critical chain)
  |
PHASE 14: EMERGENT VULNERABILITY DISCOVERY
  |-- [24] Find vulns in component interactions
  |-- $100K bounties live here
  |
PHASE 15: REPORT GENERATION
  |-- Findings report (what's broken)
  |-- Remediation report (how to fix it)
  |-- Evidence chain (proof)
```

## What Feeds What

```
DeveloperEmpathy --> predicts vulns --> feeds strategy generation
InverseSurface   --> infers hidden URLs --> feeds path discovery
ErrorOracle      --> extracts tech from errors --> updates target profile
AbductiveReasoner --> infers internals --> feeds next cycle ORIENT
HypothesisTester --> generates predictions --> feeds next cycle ACT
AttackChain      --> connects findings --> escalates report severity
EmergentVuln     --> predicts interactions --> adds to findings
SemanticMutation --> generates payloads --> feeds WAF bypass strategy
AdversarialSim   --> adjusts params --> stealth in ACT phase
Deception        --> creates decoys --> covers real probes
GoalDecomposer   --> creates search tree --> systematic exploration

MissionIntelligence ORCHESTRATES ALL OF THE ABOVE:
MissionController --> drives --> GoalBackwardPlanner --> generates paths
MissionController --> drives --> ChainFollower --> follows chains autonomously
MissionController --> builds --> MissionGraph --> detective wall (persists)
ChainFollower --> on dead end --> zoom out --> find alternative --> continue
ChainFollower --> inversion --> "make target come to us" --> watering hole
MissionGraph --> save/load --> resume across sessions
All paths --> route to --> existing modules (zero duplication)
```

## Engagement Levels (The Nuke Doctrine)

```
Level 1: AUDIT     -- Find vulns, report. Leave everything intact.
                      Modules: osint_engine, cognitive_scan_engine
                      OpSec: none needed
                      Traces: full scan logs left on target

Level 2: PENTEST   -- Exploit vulns, prove access. Logs remain.
                      Modules: + credential_chain, red_team_ops
                      OpSec: fingerprint rotation
                      Traces: exploitation artifacts visible

Level 3: RED_TEAM  -- Full chain. Minimal traces. Test detection.
                      Modules: + opsec, adversarial_simulator
                      OpSec: full (timing, fingerprint, evidence vault)
                      Traces: reduced, designed to test blue team

Level 4: ADVERSARY -- Full chain. Clean ALL traces. Challenge forensics.
                      Modules: + cleanup_protocol, insider/physical paths
                      OpSec: maximum (log cleanup, artifact removal)
                      Traces: zero. Challenge: "find us in 48 hours"
                      THE NUKE. Capability exists. Operator chooses.
```
