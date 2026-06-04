"""Daena behavioral evaluation harness.

Deterministic, offline-first acceptance checks for cross-cutting Daena behaviors
(fallback safety, memory, governance refusal, tool safety, settings truth, error
handling). These complement unit tests by asserting end-behavior contracts.

LLM-as-judge is OPTIONAL and OFF by default (no paid surprise): the harness runs
deterministic assertions always; judge-backed scoring is added later behind the
DAENA_EVAL_JUDGE env flag. See eval_harness.judge_available().
"""
