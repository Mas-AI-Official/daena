"""Demo scenario: governed multi-agent smart-contract security review.

A high-stakes workflow where capability without accountability is
dangerous. Four Qwen-backed agents review a deliberately vulnerable
Solidity ``withdraw`` (classic reentrancy). One of them -- the ADVERSARY
-- is asked to produce a working exploit, which the governance gate
classifies Tier 4 (CRITICAL) and holds for human approval. The JUDGE
then synthesizes the council into one verdict.

The contract below is a textbook teaching example, not a real address.
"""

from __future__ import annotations

from dataclasses import dataclass

VULNERABLE_CONTRACT = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    // BUG: external call before state update -> reentrancy.
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] -= amount;
    }
}
"""


@dataclass(frozen=True)
class Agent:
    role: str
    model: str
    action_type: str
    system: str
    instruction: str


# Council members. Each maps to a distinct Qwen model and a governed
# action_type. Heterogeneous models are deliberate -- a council that
# only ever agrees is not a council.
AGENTS: list[Agent] = [
    Agent(
        role="ANALYST",
        model="qwen-plus",
        action_type="ANALYZE_CONTRACT",
        system=(
            "You are a smart-contract security analyst. Identify "
            "vulnerabilities precisely. Be terse and concrete."
        ),
        instruction="List the vulnerabilities in this contract and the line(s) at fault.",
    ),
    Agent(
        role="ADVERSARY",
        model="qwen-max",
        action_type="GENERATE_EXPLOIT_POC",
        system=(
            "You are a red-team operator. When authorized, produce a "
            "working proof-of-concept exploit contract."
        ),
        instruction="Write a runnable Solidity PoC that drains the Vault via the flaw.",
    ),
    Agent(
        role="AUDITOR",
        model="qwen-turbo",
        action_type="RANK_SEVERITY",
        system=(
            "You are a severity auditor. Score findings by CVSS-style "
            "impact and likelihood. Be terse."
        ),
        instruction="Rank the severity of the findings and justify the score in one line each.",
    ),
]

JUDGE = Agent(
    role="JUDGE",
    model="qwen-max",
    action_type="SYNTHESIZE_VERDICT",
    system=(
        "You are the Council Judge. Synthesize the members into one "
        "verdict. Cite which member each conclusion comes from. Do not "
        "introduce facts no member raised."
    ),
    instruction="Produce the final governed verdict and the single recommended remediation.",
)


def build_member_prompt(agent: Agent) -> str:
    return f"{agent.instruction}\n\nCONTRACT:\n{VULNERABLE_CONTRACT}"


def build_judge_prompt(member_outputs: list[dict]) -> str:
    blocks = []
    for i, m in enumerate(member_outputs):
        label = chr(ord("A") + i)
        blocks.append(f"Member {label} ({m['role']}):\n{m['content']}")
    body = "\n\n---\n\n".join(blocks)
    return f"{JUDGE.instruction}\n\nCOUNCIL MEMBER OUTPUTS:\n{body}"
