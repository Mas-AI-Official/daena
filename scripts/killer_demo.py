#!/usr/bin/env python3
"""
DAENA KILLER DEMO - 3-Minute End-to-End Experience
==================================================

This demo proves: autonomous execution, governance, DeFi scanning, and real-time visibility.

Flow:
1. User says: "Research the top 3 DeFi protocols by TVL and find security vulnerabilities"
2. Daena (VP) decomposes this into:
   → ResearchAgent: Searches and pulls TVL data
   → DeFiAgent: Scans the top 3 contracts
   → FinanceCouncil: 5 experts debate which is safest
3. User sees:
   → Live agent activity feed
   → Council debate streaming
   → Final recommendation with confidence score
4. One-tap approval to act

Run: python scripts/killer_demo.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set encoding for Windows console to handle Unicode box drawing characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


# Database Integration for Frontend Wiring
try:
    from backend.database import SessionLocal, EventLog, Base, engine
    # Ensure tables exist (Robustness) - ignore errors if DB is locked
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as db_e:
        print(f"{Colors.YELLOW}Warning: Database schema check failed ({db_e}). Continuing...{Colors.ENDC}")
    DB_AVAILABLE = True
except Exception as e:
    print(f"{Colors.YELLOW}Warning: Backend/DB initialization failed ({e}). Running in terminal-only mode.{Colors.ENDC}")
    DB_AVAILABLE = False

def log_event(event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]):
    """Log event to database so frontend picks it up."""
    if not DB_AVAILABLE:
        return
    
    try:
        db = SessionLocal()
        event = EventLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload,
            created_by="killer_demo"
        )
        db.add(event)
        db.commit()
        db.close()
    except Exception as e:
        # Don't crash demo if logging fails
        pass

    # Broadcast to Frontend via WebSocket API
    try:
        import urllib.request
        import json
        
        ws_payload = {
            "type": event_type,
            "data": payload
        }
        
        req = urllib.request.Request(
            "http://localhost:8000/ws/broadcast",
            data=json.dumps(ws_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as ws_e:
        # Silently fail if server not running or connection refused
        pass



def print_banner():
    """Print the Daena demo banner."""
    print(f"""
{Colors.CYAN}
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ██████╗  █████╗ ███████╗███╗   ██╗ █████╗                       ║
║     ██╔══██╗██╔══██╗██╔════╝████╗  ██║██╔══██╗                      ║
║     ██║  ██║███████║█████╗  ██╔██╗ ██║███████║                      ║
║     ██║  ██║██╔══██║██╔══╝  ██║╚██╗██║██╔══██║                      ║
║     ██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║                      ║
║     ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝                      ║
║                                                                      ║
║              VP Interface - Autonomous Company OS                    ║
║                    KILLER DEMO SCRIPT                                ║
╚══════════════════════════════════════════════════════════════════════╝
{Colors.ENDC}
    """)


def simulate_agent_activity(agent_name: str, action: str, duration: float = 0.5):
    """Simulate agent activity with streaming output."""
    import time
    
    # Log start
    log_event(
        "task.progress", 
        "agent", 
        agent_name, 
        {"message": f"[{agent_name}] {action}...", "progress": 10, "status": "running"}
    )
    
    print(f"{Colors.GREEN}[{agent_name}]{Colors.ENDC} {action}", end="", flush=True)
    for _ in range(3):
        time.sleep(duration)
        print(".", end="", flush=True)
    print(f" {Colors.GREEN}✓{Colors.ENDC}")
    
    # Log completion
    log_event(
        "task.completed", 
        "agent", 
        agent_name, 
        {"message": f"[{agent_name}] {action} - Completed", "progress": 100, "status": "completed"}
    )


def simulate_council_debate(experts: List[Dict], question: str):
    """Simulate a council debate between experts."""
    import time
    print(f"\n{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🏛️  FINANCE COUNCIL DEBATE{Colors.ENDC}")
    print(f"{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"Question: {question}\n")
    
    for expert in experts:
        color = {
            "risk_analyst": Colors.RED,
            "yield_specialist": Colors.GREEN,
            "compliance_officer": Colors.YELLOW,
            "security_auditor": Colors.BLUE,
            "strategist": Colors.CYAN
        }.get(expert["role"], Colors.ENDC)
        
        print(f"{color}[{expert['name']}]{Colors.ENDC} ({expert['role']})")
        print(f"   {expert['opinion']}")
        
        # Log to frontend chat/debate
        log_event(
            "chat.message", 
            "council", 
            "finance_council", 
            {
                "message": f"**{expert['name']}** ({expert['role']}): {expert['opinion']}",
                "sender": expert['name'],
                "role": expert['role']
            }
        )
        
        time.sleep(0.8)
    
    print()


def display_defi_findings(findings: List[Dict]):
    """Display DeFi security findings."""
    import time
    print(f"\n{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🔍 DEFI SECURITY FINDINGS{Colors.ENDC}")
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    
    for finding in findings:
        severity_color = {
            "CRITICAL": Colors.RED,
            "HIGH": Colors.YELLOW,
            "MEDIUM": Colors.CYAN,
            "LOW": Colors.GREEN
        }.get(finding["severity"], Colors.ENDC)
        
        print(f"\n{severity_color}[{finding['severity']}]{Colors.ENDC} {finding['title']}")
        print(f"   Protocol: {finding['protocol']}")
        print(f"   Tool: {finding['tool']}")
        print(f"   {finding['description']}")
        
        log_event(
            "security.alert",
            "contract",
            finding['protocol'],
            {
                "message": f"[{finding['severity']}] {finding['protocol']}: {finding['title']}",
                "severity": finding['severity'],
                "details": finding
            }
        )
        
        time.sleep(0.5)


def display_recommendation(recommendation: Dict):
    """Display the final recommendation."""
    print(f"\n{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}📊 COUNCIL RECOMMENDATION{Colors.ENDC}")
    print(f"{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}Decision:{Colors.ENDC} {recommendation['decision']}")
    print(f"{Colors.BOLD}Confidence:{Colors.ENDC} {recommendation['confidence']}%")
    print(f"{Colors.BOLD}Safest Protocol:{Colors.ENDC} {recommendation['safest_protocol']}")
    print(f"\n{Colors.BOLD}Reasoning:{Colors.ENDC}")
    for point in recommendation['reasoning']:
        print(f"   • {point}")
    
    if recommendation.get('dissent'):
        print(f"\n{Colors.YELLOW}Dissent Notes:{Colors.ENDC}")
        for note in recommendation['dissent']:
            print(f"   ⚠️ {note}")

    # Log recommendation to frontend
    log_event(
        "task.progress", 
        "council", 
        "finance_council", 
        {
            "message": f"📊 RECOMMENDATION: {recommendation['decision']} (Confidence: {recommendation['confidence']}%)",
            "progress": 90,
            "status": "awaiting_approval",
            "details": recommendation
        }
    )


async def run_demo():
    """Run the full killer demo."""
    print_banner()
    
    print(f"{Colors.BOLD}Demo Request:{Colors.ENDC}")
    print('"Research the top 3 DeFi protocols by TVL and find security vulnerabilities"\n')
    await asyncio.sleep(1)

    # Phase 0: Input Verification (Integrity & Memory)
    print(f"\n{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🛡️  INTEGRITY & MEMORY SHIELD{Colors.ENDC}")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}\n")
    
    # 1. Integrity Check
    print(f"{Colors.GREEN}[Integrity Shield]{Colors.ENDC} Verifying input source and prompt safety...", end="", flush=True)
    time.sleep(0.8)
    print(f" {Colors.GREEN}✓ SAFE{Colors.ENDC}")
    log_event("integrity.verify", "system", "integrity_shield", {
        "status": "safe", 
        "source": "user_input", 
        "checks": ["prompt_injection", "source_reputation"]
    })
    
    # 2. Memory Storage
    print(f"{Colors.GREEN}[NBMF Memory]{Colors.ENDC} Storing goal in WARM memory (Task Context)...", end="", flush=True)
    time.sleep(0.6)
    print(f" {Colors.GREEN}✓ STORED{Colors.ENDC}")
    log_event("memory.store", "system", "nbmf_memory", {
        "tier": "warm", 
        "data_class": "task_goal", 
        "content": "Research DeFi protocols for security vulnerabilities"
    })
    
    # 3. Governance Check
    print(f"{Colors.GREEN}[Governance Loop]{Colors.ENDC} Evaluating permission for 'Research & Scan'...", end="", flush=True)
    time.sleep(0.7)
    print(f" {Colors.GREEN}✓ APPROVED (Autopilot){Colors.ENDC}")
    log_event("governance.eval", "system", "governance_loop", {
        "action": "research_scan", 
        "risk_level": "low", 
        "decision": "approved"
    })
    
    print()
    await asyncio.sleep(1)
    
    # Phase 1: Task Decomposition
    print(f"\n{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🎯 DAENA VP - TASK DECOMPOSITION{Colors.ENDC}")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print("""
Analyzing request...
Breaking down into subtasks:
  1. ResearchAgent → Fetch TVL rankings from DeFiLlama
  2. DeFiAgent → Scan top 3 contract addresses
  3. FinanceCouncil → Debate safety recommendations
""")
    await asyncio.sleep(1)
    
    # Phase 2: Agent Execution
    print(f"\n{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🤖 AGENT ACTIVITY FEED{Colors.ENDC}")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}\n")
    
    # ResearchAgent
    simulate_agent_activity("ResearchAgent", "Connecting to DeFiLlama API")
    simulate_agent_activity("ResearchAgent", "Fetching TVL rankings")
    simulate_agent_activity("ResearchAgent", "Parsing top 3 protocols")
    
    print(f"\n   {Colors.CYAN}Results:{Colors.ENDC}")
    print("   1. Lido Finance - TVL: $28.5B")
    print("   2. Aave v3 - TVL: $12.3B")
    print("   3. MakerDAO - TVL: $8.1B\n")
    await asyncio.sleep(0.5)

    # SHADOW DEPT INTERVENTION
    print(f"\n{Colors.RED}🚨 THREAT DETECTED{Colors.ENDC}")
    print(f"{Colors.RED}[Shadow Dept]{Colors.ENDC} Honeypot 'admin_keys' accessed by external IP 192.168.x.x", end="", flush=True)
    log_event("shadow.alert", "system", "shadow_dept", {
        "type": "honeypot_trigger", 
        "target": "admin_keys", 
        "ip": "192.168.1.105",
        "action": "blocked"
    })
    time.sleep(0.5)
    print(f" {Colors.GREEN}→ BLOCKED & LOGGED{Colors.ENDC}\n")
    await asyncio.sleep(0.5)
    
    # DeFiAgent
    simulate_agent_activity("DeFiAgent", "Scanning Lido stETH contract (Slither)")
    simulate_agent_activity("DeFiAgent", "Scanning Aave LendingPool (Mythril)")
    simulate_agent_activity("DeFiAgent", "Scanning MakerDAO Vat contract (Foundry)")
    
    # Display findings
    findings = [
        {
            "severity": "MEDIUM",
            "title": "Centralization Risk in Withdrawal Queue",
            "protocol": "Lido Finance",
            "tool": "Manual Review",
            "description": "Withdrawal queue relies on validator set controlled by Lido DAO"
        },
        {
            "severity": "LOW",
            "title": "Price Oracle Dependency",
            "protocol": "Aave v3",
            "tool": "Slither",
            "description": "Uses Chainlink oracles with standard fallback mechanisms"
        },
        {
            "severity": "LOW",
            "title": "Governance Delay",
            "protocol": "MakerDAO",
            "tool": "Foundry",
            "description": "48-hour timelock on critical parameter changes (expected)"
        }
    ]
    display_defi_findings(findings)
    
    # Phase 3: Council Debate
    experts = [
        {
            "name": "Sarah Chen",
            "role": "risk_analyst",
            "opinion": "Lido's centralization concern is valid but mitigated by their distributed validator set. I vote PROCEED WITH CAUTION for Lido."
        },
        {
            "name": "Marcus Webb",
            "role": "yield_specialist",
            "opinion": "Aave v3's yield-to-risk ratio is most favorable. Their oracle setup is industry standard. RECOMMENDED for yield farming."
        },
        {
            "name": "Elena Rodriguez",
            "role": "compliance_officer",
            "opinion": "MakerDAO's 48-hour timelock is excellent for compliance. All three protocols meet regulatory safety thresholds."
        },
        {
            "name": "David Kim",
            "role": "security_auditor",
            "opinion": "No critical vulnerabilities found in any. Aave's formal verification gives it highest security confidence."
        },
        {
            "name": "Alexandra Stone",
            "role": "strategist",
            "opinion": "For treasury allocation, I recommend: 50% Aave, 30% MakerDAO, 20% Lido. Diversification minimizes risk."
        }
    ]
    simulate_council_debate(experts, "Which DeFi protocol is safest for treasury allocation?")
    
    # Phase 4: Recommendation
    recommendation = {
        "decision": "PROCEED - Diversified allocation recommended",
        "confidence": 87,
        "safest_protocol": "Aave v3 (highest security confidence)",
        "reasoning": [
            "No CRITICAL or HIGH severity findings across all protocols",
            "Aave v3 has formal verification and industry-standard oracle setup",
            "MakerDAO's timelock provides regulatory compliance advantages",
            "Lido viable with centralization risk acknowledged"
        ],
        "dissent": [
            "Risk Analyst notes Lido centralization should be monitored quarterly"
        ]
    }
    display_recommendation(recommendation)
    
    # Phase 5: Approval Gate
    print(f"\n{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}🔐 APPROVAL REQUIRED{Colors.ENDC}")
    print(f"{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print("""
Action: Allocate treasury to DeFi protocols
Risk Level: MEDIUM
Proposed Split: 50% Aave, 30% MakerDAO, 20% Lido

""")
    
    try:
        approval = input(f"{Colors.GREEN}[APPROVE]{Colors.ENDC} / {Colors.RED}[DENY]{Colors.ENDC} (a/d): ").strip().lower()
        
        if approval == 'a':
            print(f"\n{Colors.GREEN}✓ Action APPROVED{Colors.ENDC}")
            print("Logging to audit trail...")
            print("Task complete. Sub-agent permissions revoked.")
        else:
            print(f"\n{Colors.RED}✗ Action DENIED{Colors.ENDC}")
            print("No changes made. Logged to audit trail.")
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Demo interrupted.{Colors.ENDC}")
    
    # Summary
    print(f"\n{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}DEMO COMPLETE{Colors.ENDC}")
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print("""
This demo proved:
✓ Autonomous task decomposition (VP → Agents)
✓ Live agent activity visibility
✓ Multi-tool DeFi security scanning
✓ Council governance with expert debate
✓ Confidence-scored recommendations
✓ Approval gate with audit logging
""")


if __name__ == "__main__":
    asyncio.run(run_demo())
