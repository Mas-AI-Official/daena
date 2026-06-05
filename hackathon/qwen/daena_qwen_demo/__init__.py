"""Daena on Qwen Cloud -- governed multi-agent demo (hackathon slice).

A sanitized, dependency-free slice of Daena's governed multi-agent
pipeline, ported to run on Qwen Cloud models. It demonstrates the
differentiator most multi-agent demos skip: accountability. Every agent
action passes a governance policy gate and is written to a tamper-evident,
hash-chained audit trail using the same algorithm as Daena production
(backend/app/services/audit.py).

Public OSS-safe slice: no commercial config, no secrets, stdlib only.
See README.md for run instructions (replay + live).
"""

from .audit_chain import AuditChain, AuditEntry, compute_hash
from .policy_gate import GateDecision, evaluate
from .runner import run_review

__all__ = [
    "AuditChain",
    "AuditEntry",
    "compute_hash",
    "GateDecision",
    "evaluate",
    "run_review",
]
