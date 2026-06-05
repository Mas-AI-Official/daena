"""Qwen Cloud chat clients (live + replay).

Two interchangeable backends behind one ``complete`` interface:

* ``LiveQwenClient`` -- OpenAI-compatible POST to the DashScope
  compatible-mode endpoint. Requires ``QWEN_CLOUD_API_KEY``. Real network,
  real spend: founder-gated. Mirrors the request shape of
  backend/app/services/providers/qwen_cloud.py but is dependency-light
  (stdlib ``urllib``) so this public slice carries no commercial config.

* ``ReplayQwenClient`` -- returns recorded responses from a fixtures
  file, keyed by agent role. Deterministic, offline, no secret. This is
  the default the demo and tests use so the run is reproducible and the
  audit-trail hashes are stable.

Both return a ``Completion``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Indicative international-region USD list prices per 1M tokens, 2026-06.
# Best-effort cost tracking only; confirm in the Model Studio console.
_PRICES: dict[str, tuple[float, float]] = {
    "qwen-max": (1.60, 6.40),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.05, 0.20),
    "qwen3-coder-plus": (1.00, 5.00),
}


@dataclass(frozen=True)
class Completion:
    role: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def _cost(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = _PRICES.get(model, (0.40, 1.20))
    return round((in_tok / 1_000_000) * pin + (out_tok / 1_000_000) * pout, 6)


class ReplayQwenClient:
    """Deterministic client backed by a recorded fixtures file."""

    def __init__(self, fixtures: dict[str, dict]) -> None:
        self._fixtures = fixtures

    @classmethod
    def from_file(cls, path: str) -> "ReplayQwenClient":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def complete(
        self, role: str, model: str, system: str, user: str
    ) -> Completion:
        rec = self._fixtures.get(role)
        if rec is None:
            raise KeyError(f"no replay fixture for role {role!r}")
        in_tok = int(rec.get("input_tokens", 0))
        out_tok = int(rec.get("output_tokens", 0))
        return Completion(
            role=role,
            model=model,
            content=rec["content"],
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=_cost(model, in_tok, out_tok),
            latency_ms=int(rec.get("latency_ms", 0)),
        )


class LiveQwenClient:
    """OpenAI-compatible client for Qwen Cloud (founder-gated, real spend)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("QWEN_CLOUD_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "QWEN_CLOUD_API_KEY is not set -- live mode is founder-gated. "
                "Use the default replay mode for an offline run."
            )
        base = base_url or os.environ.get("QWEN_CLOUD_BASE_URL", _DEFAULT_BASE_URL)
        self._chat_url = f"{base.rstrip('/')}/chat/completions"
        self._timeout = timeout

    def complete(
        self, role: str, model: str, system: str, user: str
    ) -> Completion:
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self._chat_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency_ms = int((time.monotonic() - start) * 1000)

        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage", {})
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))
        return Completion(
            role=role,
            model=model,
            content=choice.get("message", {}).get("content", ""),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=_cost(model, in_tok, out_tok),
            latency_ms=latency_ms,
        )
