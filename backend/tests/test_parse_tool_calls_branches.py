"""Branch coverage for parse_tool_calls' lower-precedence extraction paths.

The existing ``TestParseToolCalls`` (test_tool_use_loop.py) covers the canonical
```tool_call``` fence (Pattern 1), a malformed fence, the ``arguments`` alias,
and a bare *whole-response* object. It does NOT exercise three real, regressable
branches of the same parser in ``app.services.tool_schema_builder``:

  * Pattern 2 -- a ```json``` fenced block, which fires only when no
    ```tool_call``` fence was found.
  * Pattern 3 -- the hand-rolled brace-depth matcher that lifts a
    ``{"tool": ...}`` object out of *surrounding prose*. Its only reason to
    exist over ``json.loads(whole_response)`` (Pattern 4) is (a) prose on both
    sides and (b) a NESTED params object: a naive ``\\{.*?\\}`` matcher would
    stop at the first inner ``}`` and yield invalid JSON. The existing
    ``test_parse_bare_json`` passes the object as the ENTIRE string, which
    Pattern 4 would satisfy too -- so it does not actually prove the walker is
    needed. This is the parser's crown-jewel contract and the only one that
    guards against a "simplify to one regex" regression.
  * the precedence gate -- a ```tool_call``` fence must SUPPRESS a stray
    ``{"tool": ...}`` object elsewhere in the same message (the ``if not calls:``
    guards), so the parsed count stays 1, not 2.

Plus the third ``_extract`` alias (``parameters``), completing the
params/arguments/parameters trio.

Each assertion fails for a concrete, named regression (see per-test comments),
so none of these is a tautology.
"""

from __future__ import annotations

from app.services.tool_schema_builder import parse_tool_calls


class TestParseToolCallsBranches:
    def test_pattern2_json_fence(self):
        # No ```tool_call``` fence, so Pattern 1 yields nothing and the
        # ```json``` fence (Pattern 2) must take over. RED if Pattern 2 is
        # removed: a ```json```-only response would parse to zero calls.
        response = (
            "Sure, here is the call:\n"
            "```json\n"
            '{"tool": "gmail_search", "params": {"query": "is:unread"}}\n'
            "```\n"
        )
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["tool"] == "gmail_search"
        assert calls[0]["params"]["query"] == "is:unread"

    def test_pattern3_prose_embedded_with_nested_params(self):
        # The object is embedded in prose (so Pattern 4's whole-string
        # json.loads cannot fire) AND its params nest another object (so a
        # naive non-greedy brace match would truncate at the first inner '}').
        # Only the depth-counting walker recovers the full object. RED if the
        # brace walker is swapped for a naive regex OR if Pattern 3 is removed.
        response = (
            "I'll run this now: "
            '{"tool": "run_workflow", "params": {"workflow_id": "ops.x", '
            '"opts": {"deep": true}}} '
            "and report back."
        )
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["tool"] == "run_workflow"
        # The nested object survived the brace walk intact (a truncating
        # matcher would have produced invalid JSON and dropped the call).
        assert calls[0]["params"]["opts"] == {"deep": True}

    def test_tool_call_fence_suppresses_stray_object(self):
        # Pattern 1 finds the fenced call; the ``if not calls:`` gates must
        # stop Pattern 3 from ALSO lifting the stray {"tool": ...} in prose.
        # RED if the precedence gate is dropped: count would become 2.
        response = (
            "```tool_call\n"
            '{"tool": "read_file", "params": {"path": "/a"}}\n'
            "```\n"
            'Ignore this dangling object: {"tool": "delete_file", '
            '"params": {"path": "/b"}}'
        )
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["tool"] == "read_file"

    def test_parameters_key_alias(self):
        # _extract aliases params -> arguments -> parameters; only the first
        # two were covered. A call carrying ONLY "parameters" must resolve.
        # RED if the ``parameters`` fallback is dropped from _extract.
        response = (
            "```tool_call\n"
            '{"tool": "web_search", "parameters": {"query": "daena"}}\n'
            "```"
        )
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["params"] == {"query": "daena"}
