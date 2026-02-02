import { useState } from "react";

const SUGGESTIONS = [
  {
    id: "token",
    icon: "⛓️",
    title: "DAENA TOKEN — The Backbone",
    priority: "CRITICAL",
    status: "Not built yet",
    summary: "This is the single biggest missing piece. Daena already has governance, agents, DeFi scanning — but no economic layer to tie it all together. The token IS the company's currency, incentive system, and proof of ownership all in one.",
    details: [
      {
        subtitle: "What it is",
        text: "DAENA is a utility + governance token. Holders can: (1) stake to vote on Council decisions alongside AI experts, (2) earn rewards when Daena's agents complete profitable tasks, (3) pay for premium agent compute time, (4) participate in treasury decisions about where the company invests next."
      },
      {
        subtitle: "Where to deploy it",
        text: "Deploy on Solana first — fastest finality, cheapest fees, already has huge DeFi ecosystem. Use SPL token standard. This also gives you a perfect hackathon pivot if Solana is a sponsored track. Secondary: bridge to Ethereum via Wormhole later."
      },
      {
        subtitle: "Token economics (simple)",
        text: "Total supply: 100M tokens. Founder reserve: 20% (vested over 3 years). Ecosystem/treasury: 40% (released by Council vote). Team & advisors: 15% (vested). Hackathon/community: 10%. Early investors: 15%. The treasury funds agent compute, model hosting, and development. When agents make money (DeFi arbitrage, research sales), profit flows back to treasury."
      },
      {
        subtitle: "Smart contract",
        text: "Write a basic SPL token + a simple staking contract. This is 200 lines of code in Rust. You already have the `contracts/` folder in your repo. The demo: 'Watch Daena earn tokens by completing a DeFi audit, then stake them to vote on the next Council decision.' This is a complete story."
      }
    ],
    code: `# What goes in contracts/daena_token/
contracts/
├── daena_token/
│   ├── src/
│   │   ├── lib.rs          # SPL token mint + transfer
│   │   ├── staking.rs      # Stake DAENA to earn voting power
│   │   ├── treasury.rs     # Council-controlled treasury
│   │   └── rewards.rs      # Auto-distribute rewards from agent earnings
│   └── Cargo.toml
├── sample_contracts/       # For demo scanning
│   ├── vulnerable_v1.sol   # Has reentrancy bug (demo target)
│   └── safe_v2.sol         # Clean version after fix
└── tests/`
  },
  {
    id: "nft",
    icon: "🎨",
    title: "DAENA NFTs — Agent Identity + Proof",
    priority: "HIGH",
    status: "Not built yet",
    summary: "Each AI agent in Daena's company gets an NFT identity. This sounds like hype — it's actually functional. The NFT IS the agent's on-chain credential, skill record, and performance history. Investors and partners can verify what each agent has done.",
    details: [
      {
        subtitle: "Why NFTs matter here (not just hype)",
        text: "On-chain identity solves a real problem: how do you prove an AI agent is trustworthy? An NFT with a track record of successful audits, zero false positives, and community votes is actual proof. Other protocols can check it before trusting Daena's agents with their contracts."
      },
      {
        subtitle: "What the NFTs contain",
        text: "Each agent NFT has: agent name + role, performance stats (audits completed, bugs found, false positive rate), skills earned over time (like leveling up in a game), and a trust score voted by the community. The metadata updates automatically as the agent works."
      },
      {
        subtitle: "How to sell them",
        text: "Phase 1: Free mint for early community members who help test Daena. Phase 2: Auction rare 'legendary' agents (top performers). Phase 3: Agents with NFTs can be hired by other DeFi protocols for external audits — the NFT holder earns DAENA tokens from that work. This creates a marketplace of trusted AI auditors."
      },
      {
        subtitle: "Technical implementation",
        text: "Mint on Solana as well (Metaplex standard). Store metadata on Arweave for permanence. The backend's agent activity logs (already tracked in daena.db) feed directly into the NFT metadata via an update script. One new route: POST /api/v1/nft/update-agent-stats — runs after each task completion."
      }
    ],
    code: `# NFT structure
nft/
├── mint_agent.py           # Creates NFT for each new agent
├── update_stats.py         # Updates NFT metadata after task completion  
├── metadata_template.json  # Arweave-hosted metadata schema
└── marketplace.py          # Simple buy/hire interface

# Example metadata
{
  "name": "DeFiAgent-#0042",
  "attributes": [
    {"trait": "Role", "value": "Security Scanner"},
    {"trait": "Audits Completed", "value": 847},
    {"trait": "Bugs Found", "value": 23},
    {"trait": "False Positive Rate", "value": "0.3%"},
    {"trait": "Trust Score", "value": 94},
    {"trait": "Rarity", "value": "Legendary"}
  ]
}`
  },
  {
    id: "hidden",
    icon: "👁️",
    title: "Hidden Security Layer — The Trap Floor",
    priority: "HIGH",
    status: "Partially exists (honeypots designed, not fully wired)",
    summary: "You already have the Deception Layer blueprint (honeypots, canary tokens, decoy routes). What's missing is making it invisible, autonomous, and connected to Daena's intelligence. This becomes Daena's own secret weapon that she monitors and learns from — completely hidden from everyone except you.",
    details: [
      {
        subtitle: "How it works",
        text: "Three invisible layers run at all times. Layer A: Shadow Routes — fake admin endpoints that look real but log everything. Anyone probing your API hits these first. Layer B: Honey Treasury — a fake DeFi treasury endpoint showing 'holdings' that don't exist. If anyone tries to interact with it, instant alert to your phone. Layer C: Canary Agents — fake sub-agents that appear in the system but do nothing. If someone tries to control them externally, you know someone is trying to hijack your agent swarm."
      },
      {
        subtitle: "What makes it 'hidden'",
        text: "These don't show up in the normal dashboard. They have their own private tab in Control Plane — accessible only with a secret URL parameter or founder key. Daena monitors them autonomously and sends you weekly reports on 'threat activity detected.' This is the department that protects the company."
      },
      {
        subtitle: "Intelligence gathering (legal)",
        text: "When someone probes your system, you learn their attack patterns, tools, and timing. This intelligence feeds back into Daena's Integrity Shield — making her better at detecting manipulation in external data. The deception layer isn't just defense, it's a learning engine."
      },
      {
        subtitle: "What to build first",
        text: "Start with: (1) 3 shadow admin routes that log IP + headers + payload, (2) a canary API key that alerts via webhook when used, (3) a 'security intel' dashboard tab hidden behind ?mode=shadow. Wire it to push notifications via your existing WebSocket. Total: maybe 150 lines of backend code."
      }
    ],
    code: `# backend/routes/shadow.py — THE HIDDEN LAYER
# Only accessible via ?_auth=<founder_key>

@router.get("/admin/users")  # Looks real, is fake
async def shadow_admin_users(request):
    log_intrusion(request)  # Log everything
    return {"users": [], "count": 0}  # Empty but believable

@router.get("/treasury/holdings")  # Fake treasury
async def shadow_treasury():
    log_intrusion(request)
    alert_founder("Someone probed the treasury!")
    return {"holdings": [...fake data...]}

# Canary token: a fake API key in .env.example
# If anyone ever uses it → instant alert
CANARY_KEY = "sk-daena-canary-xxxx"  # Looks real, triggers alert`
  },
  {
    id: "frontend",
    icon: "🖥️",
    title: "Frontend-Backend Sync — The Real Dashboard",
    priority: "CRITICAL — Do this before hackathon",
    status: "WebSocket exists but not fully synced",
    summary: "This is what you specifically called out. The backend is powerful — agents running, Council debating, DeFi scanning — but the frontend doesn't show it happening in real-time. This is the gap between 'cool architecture' and 'holy shit, watch this work.' Fix this and your demo becomes undeniable.",
    details: [
      {
        subtitle: "What needs to sync (currently broken)",
        text: "Agent status (active/idle/thinking/executing) — should pulse green in real-time on dashboard. Council debates — each expert's opinion should appear as it's generated, like a live chat room. DeFi scan progress — show which tool is running (Slither... Mythril... AI Analysis...) with a progress bar. Approval queue — new items ping your phone AND light up on the dashboard. Audit log — scrolling feed of every action, timestamped."
      },
      {
        subtitle: "How to wire it (antigravity prompt)",
        text: "The backend already has event_bus.py and /ws/events WebSocket. The frontend templates already have WebSocket client code. The gap is: (1) not all backend events are being emitted to the event bus, (2) the frontend isn't rendering them as real-time updates. Two fixes needed: add emit() calls in daena_agent.py and defi.py for every state change, then update dashboard.html to render those events live."
      },
      {
        subtitle: "The 'wow' moment",
        text: "When you demo at the hackathon, this is what judges need to see: You type 'audit this contract.' Three agent cards light up simultaneously. A progress bar shows the scan pipeline moving. Council cards populate one by one as experts finish. A verdict appears. You tap Approve. Done. All of this visible, all real-time, all in under 90 seconds. That's the demo that wins."
      },
      {
        subtitle: "Quick implementation priority",
        text: "Step 1: Add event emission in defi.py scan endpoint (every tool start/finish). Step 2: Add agent status changes to event bus in daena_agent.py. Step 3: Update dashboard.html to listen for these events and update DOM. Step 4: Add Council debate rendering in control_plane.html. This is 3-4 hours of focused work."
      }
    ],
    code: `# backend/services/daena_agent.py — ADD THESE EMISSIONS
class SubAgent:
    async def start_task(self, task):
        event_bus.emit("agent_status", {  # ADD THIS
            "agent_id": self.id,
            "status": "active",
            "task": task.name
        })
        # ... existing code ...

# backend/routes/defi.py — ADD THESE EMISSIONS  
async def run_scan(scan_id):
    for tool in ["slither", "mythril", "echidna", "ai_audit"]:
        event_bus.emit("scan_progress", {  # ADD THIS
            "scan_id": scan_id,
            "tool": tool,
            "status": "running"
        })
        result = await run_tool(tool)
        event_bus.emit("scan_progress", {  # AND THIS
            "scan_id": scan_id,
            "tool": tool,
            "status": "complete",
            "findings": result.findings
        })

# frontend/templates/dashboard.html — LISTEN AND RENDER
wsClient.on("agent_status", (data) => {
    const card = document.getElementById(`agent-${data.agent_id}`);
    card.className = `agent-card status-${data.status}`;
    card.querySelector('.status-dot').style.background = 
        data.status === 'active' ? '#2ed573' : '#64748b';
});`
  },
  {
    id: "departments",
    icon: "🏢",
    title: "Expanding Departments — The Company Grows",
    priority: "MEDIUM — After token + frontend",
    status: "Council exists, departments are conceptual",
    summary: "Right now Daena has agents and a Council. But a real company has departments that specialize, compete internally, and grow. Here's how to structure the expansion so each department has purpose and revenue.",
    details: [
      {
        subtitle: "The 5 Core Departments",
        text: "R&D (Research & Development): Agents that scan for new opportunities, monitor DeFi trends, and test new strategies. This is Daena's 'eyes.' Marketing: Agents that create content, post to social media, and promote Daena's services. Yes — they actually write posts and manage accounts. Finance: Manages the DAENA treasury, tracks token economics, runs arbitrage strategies (with approval). Security: The hidden layer + Integrity Shield + all defense operations. Engineering: Builds, tests, and deploys smart contracts and integrations. Each department has its own sub-agents, its own budget (from treasury), and reports to Daena VP."
      },
      {
        subtitle: "How departments earn money",
        text: "R&D: Sells research reports to DeFi protocols. Marketing: Builds brand value → increases DAENA token price. Finance: Earns from approved DeFi strategies + treasury management. Security: Sells audit-as-a-service to other protocols. Engineering: Builds integrations that other projects pay for. Each department's earnings flow back to treasury. Council allocates budget between departments quarterly."
      },
      {
        subtitle: "Department growth mechanic",
        text: "Each department starts with 2-3 agents. When a department consistently performs well (measured by outcome tracking), Council votes to 'hire' — spawn a new agent in that department. Bad performance → agents get 'reassigned' (retired). This creates natural selection. Departments that deliver value grow. Those that don't shrink. It's evolution, not just automation."
      },
      {
        subtitle: "Implementation",
        text: "Add a departments table to daena.db. Each department has: name, agents[], budget, performance_score, last_review_date. The Council's quarterly review checks performance and votes on hiring/budget. Add a 'Company Structure' tab to Control Plane showing the org chart. This is mostly data modeling + UI — maybe 200 lines of backend, 150 lines of frontend."
      }
    ],
    code: `# Database schema addition
departments = {
    "R&D": {
        "agents": ["ResearchAgent", "TrendAnalyzer"],
        "budget_tokens": 5000,
        "revenue_tokens": 12000,
        "performance_score": 87,
        "next_review": "2026-02-15"
    },
    "Security": {
        "agents": ["DeFiAgent", "IntegrityShield", "ShadowMonitor"],
        "budget_tokens": 8000,
        "revenue_tokens": 25000,  # Highest earner
        "performance_score": 94,
        "next_review": "2026-02-15"
    },
    "Marketing": {
        "agents": ["ContentAgent", "SocialAgent"],
        "budget_tokens": 3000,
        "revenue_tokens": 2000,   # Still growing
        "performance_score": 72,
        "next_review": "2026-02-15"
    }
    // ... Finance, Engineering
}`
  },
  {
    id: "marketing",
    icon: "📢",
    title: "Daena Advertises Itself — The Marketing Department",
    priority: "MEDIUM — Start after token launch",
    status: "Not built",
    summary: "You said the company should advertise itself. This is the Marketing department — agents that actually create content, post to social media, and build Daena's brand autonomously. Not a chatbot generating posts. Agents that plan campaigns, track performance, and adapt.",
    details: [
      {
        subtitle: "What the Marketing agents do",
        text: "ContentAgent: Writes blog posts about DeFi security, AI governance trends, and Daena's achievements. Posts them to a blog (auto-deployed). Tracks which topics get engagement. SocialAgent: Manages Twitter/X account. Posts updates about Daena's work ('Today our Security team audited 3 contracts and found 2 critical vulnerabilities'). Responds to comments. Follows relevant accounts. AnalyticsAgent: Tracks all marketing metrics. Reports to Council weekly. Suggests what's working."
      },
      {
        subtitle: "The approval loop",
        text: "Nothing goes public without approval. ContentAgent drafts → Council reviews → Daena VP approves → SocialAgent posts. You can set approval to 'auto' for routine posts or 'manual' for anything mentioning money, partnerships, or claims. This keeps the brand safe while letting the company market itself."
      },
      {
        subtitle: "Why this matters for investors",
        text: "Showing that Daena can market herself is a massive differentiator. 'Our AI company literally promotes itself' is a story investors remember. It also demonstrates the governance loop working end-to-end: agents propose, Council debates, Daena approves, action happens. Marketing is the most visible proof that the system works."
      }
    ],
    code: `# Marketing agent workflow
ContentAgent → drafts post about "DeFi hack prevented"
    ↓
Council review (auto-approve for factual content)
    ↓  
Daena VP approves
    ↓
SocialAgent posts to Twitter/X
    ↓
AnalyticsAgent tracks: impressions, clicks, followers gained
    ↓
Weekly report to Council: "Marketing earned 2,400 impressions, 
    drove 47 visitors to GitHub, 3 new stars"`
  },
  {
    id: "sync_priority",
    icon: "⚡",
    title: "IMMEDIATE Priority Order — What to Do TODAY",
    priority: "NOW",
    status: "Action items",
    summary: "Based on everything above, here's the exact order. Consensus HK is Feb 11. You have 10 days. Not everything can be done before the hackathon, but these can.",
    details: [
      {
        subtitle: "TODAY (Feb 1) — 3 hours max",
        text: "(1) Rotate Azure + HuggingFace keys. Remove .env_azure_openai from git. (2) Merge reality_pass_full_e2e → main. (3) Install Slither: pip install slither-analyzer. (4) Write the basic DAENA SPL token contract (or at minimum, a token deployment script on Solana devnet — this is your 'blockchain' story for the hackathon)."
      },
      {
        subtitle: "Feb 2-3 — Frontend sync sprint",
        text: "Wire the event emissions. Make agents pulse green. Make scan progress visible. Make Council debates appear in real-time. This is your demo. Everything else is secondary until this works."
      },
      {
        subtitle: "Feb 4-5 — Token + NFT for demo",
        text: "Deploy DAENA token on Solana devnet. Mint one agent NFT. Add a 'Token & NFT' tab to Control Plane showing the token balance and agent NFT cards. This doesn't need to be fully functional — it needs to be visible and impressive in the demo."
      },
      {
        subtitle: "Feb 6-8 — Polish + record",
        text: "Record the demo video. Create Google Slides deck. Clean the README. Test everything on a fresh browser. Have a pre-recorded backup."
      },
      {
        subtitle: "After hackathon (Feb 13+)",
        text: "Build out the full token economics. Launch NFT minting. Wire the Marketing department. Expand departments. Apply for SR&ED, IRAP, CDL."
      }
    ],
    code: `# TODAY's commands (copy-paste ready)
# 1. Security fix
git rm --cached .env_azure_openai
echo ".env_azure_openai" >> .gitignore
echo ".env*" >> .gitignore  
echo "!.env.example" >> .gitignore
git add .gitignore
git commit -m "security: remove exposed env, update gitignore"
git push origin main

# 2. Merge the working branch
git checkout main
git merge reality_pass_full_e2e
git push origin main

# 3. Install Slither
pip install slither-analyzer

# 4. Quick Solana token check (if solana-cli installed)
solana config set --url https://api.devnet.solana.com
solana-keygen new -o ~/.config/solana/id.json
solana airdrop 2`
  }
];

const priorityColors = {
  "CRITICAL": { bg: "rgba(255,71,87,0.15)", border: "rgba(255,71,87,0.5)", text: "#ff4757" },
  "HIGH": { bg: "rgba(212,168,67,0.12)", border: "rgba(212,168,67,0.4)", text: "#d4a843" },
  "MEDIUM": { bg: "rgba(0,212,255,0.1)", border: "rgba(0,212,255,0.3)", text: "#00d4ff" },
  "NOW": { bg: "rgba(46,213,115,0.15)", border: "rgba(46,213,115,0.4)", text: "#2ed573" }
};

export default function App() {
  const [selected, setSelected] = useState(0);
  const [expandedDetails, setExpandedDetails] = useState({});

  const s = SUGGESTIONS[selected];
  const pColor = priorityColors[s.priority.split(" ")[0]] || priorityColors["MEDIUM"];

  const toggleDetail = (idx) => {
    setExpandedDetails(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0e1a",
      color: "#e2e8f0",
      fontFamily: "'Rajdhani', 'Segoe UI', sans-serif",
      position: "relative",
      overflow: "hidden"
    }}>
      {/* Grid background */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        backgroundImage: "linear-gradient(rgba(212,168,67,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(212,168,67,0.04) 1px, transparent 1px)",
        backgroundSize: "40px 40px"
      }} />

      <div style={{ position: "relative", zIndex: 1, maxWidth: 1100, margin: "0 auto", padding: "24px 20px" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: 11, color: "#d4a843", letterSpacing: 4,
            textTransform: "uppercase", marginBottom: 8
          }}>Daena × New Suggestions</div>
          <div style={{
            fontFamily: "'Orbitron', sans-serif",
            fontSize: 26, fontWeight: 700, color: "#d4a843",
            textShadow: "0 0 40px rgba(212,168,67,0.3)"
          }}>EXPANSION ROADMAP</div>
          <div style={{ fontSize: 14, color: "#64748b", marginTop: 6 }}>
            Token · NFT · Hidden Layer · Frontend Sync · Departments · Marketing
          </div>
        </div>

        {/* Navigation pills */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", marginBottom: 28 }}>
          {SUGGESTIONS.map((s, i) => (
            <button key={s.id} onClick={() => { setSelected(i); setExpandedDetails({}); }} style={{
              background: i === selected ? "rgba(212,168,67,0.15)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${i === selected ? "rgba(212,168,67,0.5)" : "rgba(212,168,67,0.15)"}`,
              color: i === selected ? "#d4a843" : "#64748b",
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: 11, padding: "7px 14px", borderRadius: 4, cursor: "pointer",
              transition: "all 0.2s", letterSpacing: 0.5
            }}>
              {s.icon} {s.title.split(" — ")[0].replace("DAENA ", "")}
            </button>
          ))}
        </div>

        {/* Main card */}
        <div style={{
          background: "rgba(255,255,255,0.03)",
          border: `1px solid ${pColor.border}`,
          borderRadius: 12, padding: 32, marginBottom: 24,
          boxShadow: `0 0 30px ${pColor.bg}`
        }}>
          {/* Title row */}
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#e2e8f0" }}>
                {s.icon} {s.title}
              </div>
              <div style={{
                fontSize: 13, color: "#64748b", marginTop: 4,
                fontFamily: "'Share Tech Mono', monospace"
              }}>
                Status: {s.status}
              </div>
            </div>
            <div style={{
              background: pColor.bg, border: `1px solid ${pColor.border}`,
              color: pColor.text, fontFamily: "'Share Tech Mono', monospace",
              fontSize: 11, padding: "4px 12px", borderRadius: 4, letterSpacing: 1,
              whiteSpace: "nowrap"
            }}>
              {s.priority}
            </div>
          </div>

          {/* Summary */}
          <div style={{
            marginTop: 20, fontSize: 15, color: "#cbd5e1", lineHeight: 1.7,
            borderLeft: `3px solid ${pColor.border}`, paddingLeft: 16
          }}>
            {s.summary}
          </div>

          {/* Details */}
          <div style={{ marginTop: 24 }}>
            {s.details.map((d, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <button onClick={() => toggleDetail(i)} style={{
                  width: "100%", background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(212,168,67,0.15)", borderRadius: 6,
                  padding: "12px 16px", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  transition: "all 0.2s"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ color: "#d4a843", fontSize: 12 }}>
                      {expandedDetails[i] ? "▼" : "▶"}
                    </span>
                    <span style={{
                      fontFamily: "'Orbitron', sans-serif", fontSize: 12,
                      fontWeight: 700, color: "#d4a843", letterSpacing: 0.5
                    }}>
                      {d.subtitle}
                    </span>
                  </div>
                </button>
                {expandedDetails[i] && (
                  <div style={{
                    background: "rgba(255,255,255,0.02)", borderRadius: 6,
                    padding: "16px 20px", marginTop: 4,
                    border: "1px solid rgba(212,168,67,0.08)",
                    fontSize: 14, color: "#94a3b8", lineHeight: 1.7
                  }}>
                    {d.text}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Code block */}
        {s.code && (
          <div style={{
            background: "#0d1117", border: "1px solid rgba(212,168,67,0.2)",
            borderRadius: 10, overflow: "hidden", marginBottom: 24
          }}>
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 16px", background: "rgba(212,168,67,0.08)",
              borderBottom: "1px solid rgba(212,168,67,0.15)"
            }}>
              <div style={{ display: "flex", gap: 8 }}>
                <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
                <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
                <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
              </div>
              <span style={{
                fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                color: "#64748b", letterSpacing: 1
              }}>CODE REFERENCE</span>
            </div>
            <pre style={{
              padding: "20px", margin: 0, overflowX: "auto",
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: 12, lineHeight: 1.8, color: "#7dd3fc",
              whiteSpace: "pre-wrap", wordBreak: "break-word"
            }}>
              {s.code}
            </pre>
          </div>
        )}

        {/* Connection map */}
        <div style={{
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(212,168,67,0.15)",
          borderRadius: 10, padding: 24, marginBottom: 24
        }}>
          <div style={{
            fontFamily: "'Orbitron', sans-serif", fontSize: 13,
            fontWeight: 700, color: "#d4a843", marginBottom: 16, letterSpacing: 1
          }}>
            HOW IT ALL CONNECTS
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: 4 }}>
            {[
              { label: "FOUNDER", color: "#d4a843" },
              { label: "→", color: "#64748b", arrow: true },
              { label: "DAENA VP", color: "#00d4ff" },
              { label: "→", color: "#64748b", arrow: true },
              { label: "COUNCIL", color: "#d4a843" },
              { label: "→", color: "#64748b", arrow: true },
              { label: "DEPARTMENTS", color: "#2ed573" },
              { label: "→", color: "#64748b", arrow: true },
              { label: "TOKEN + NFT", color: "#7dd3fc" },
            ].map((item, i) => item.arrow ? (
              <span key={i} style={{ color: item.color, fontSize: 18 }}>{item.label}</span>
            ) : (
              <div key={i} style={{
                background: "rgba(255,255,255,0.05)", border: `1px solid ${item.color}44`,
                borderRadius: 6, padding: "8px 14px",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                color: item.color, letterSpacing: 1, fontWeight: 700
              }}>
                {item.label}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 13, color: "#64748b", textAlign: "center", marginTop: 16, lineHeight: 1.8 }}>
            Founder sets policy → Daena orchestrates → Council debates & approves →<br />
            Departments execute & earn → Token rewards flow → NFTs prove track record<br />
            <span style={{ color: "#d4a843", fontSize: 12 }}>Every layer feeds the next. The company is self-sustaining.</span>
          </div>
        </div>

        {/* Bottom note */}
        <div style={{
          background: "rgba(46,213,115,0.08)", border: "1px solid rgba(46,213,115,0.25)",
          borderRadius: 8, padding: "16px 20px", textAlign: "center"
        }}>
          <div style={{ fontSize: 13, color: "#2ed573", fontWeight: 600, marginBottom: 4 }}>
            ✓ Consensus HK hackathon — Feb 11-12 — 10 days
          </div>
          <div style={{ fontSize: 12, color: "#64748b" }}>
            Token + Frontend Sync can be demo-ready in time. NFT + Departments are post-hackathon expansion.
          </div>
        </div>
      </div>
    </div>
  );
}
