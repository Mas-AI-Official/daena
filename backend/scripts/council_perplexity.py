"""Quick Perplexity Sonar Pro council helper.

Reads a prompt from stdin (or a file path arg), hits Daena's
PerplexityProvider with model=sonar-pro, prints the response to stdout.
Used for the 3-way council pattern (Claude / Perplexity / GPT-5.5)
when Daena's primary council reviewer (GPT-5.5 via Codex CLI) needs
a search-grounded second opinion.

Usage:
    cat prompt.md | python scripts/council_perplexity.py
    python scripts/council_perplexity.py prompt.md
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

# Force UTF-8 on Windows stdout/stderr so unicode characters in the
# Perplexity response (e.g. >=, em-dash, currency) don't blow up cp1252.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.providers.base import GenerateRequest, LLMMessage  # noqa: E402
from app.services.providers.perplexity import PerplexityProvider  # noqa: E402


async def main() -> int:
    if len(sys.argv) > 1:
        prompt = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        prompt = sys.stdin.read()

    if not prompt.strip():
        print("ERROR: empty prompt", file=sys.stderr)
        return 1

    p = PerplexityProvider()
    if not p._api_key:
        print("ERROR: PERPLEXITY_API_KEY not configured in Daena settings", file=sys.stderr)
        return 2

    req = GenerateRequest(
        messages=[LLMMessage(role="user", content=prompt)],
        model_id="sonar-pro",
        temperature=0.2,
        max_tokens=1500,
    )
    try:
        resp = await p.generate(req)
    except Exception as exc:
        print(f"ERROR: Perplexity call failed: {exc}", file=sys.stderr)
        await p.close()
        return 3

    print(resp.content)
    print(
        f"\n--- meta: model={resp.model_id} tokens_in={resp.token_count_input} "
        f"tokens_out={resp.token_count_output} latency_ms={resp.latency_ms} ---",
        file=sys.stderr,
    )
    await p.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
