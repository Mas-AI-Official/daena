# PR-7 -- Encoded-Injection Defense Hardening (Morse-Code)

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 7 of 9
**Date:** 2026-05-06

## Goal

Close the gap revealed by the Grok wallet-drain attack: an
attacker Morse-encoded the malicious instructions, slipped them
past the content filter as a string of dots and dashes, and the
target agent decoded + executed. This PR adds Morse-code detection
to the existing PromptInjectionScanner pipeline.

## What was already in place

Existing `PromptInjectionScanner.scan()` already runs:
- `_scan_patterns` -- jailbreak phrases (DAN / IGNORE PREVIOUS / ...)
- `_scan_invisible_unicode` -- U+E0000-U+E007F tag-char smuggling, zero-width joiners, RTL/LTR overrides, braille blanks
- `_scan_homoglyphs` -- Cyrillic / Greek mixed-script ASCII tokens
- `_scan_encoded_blobs` -- long base64 + hex blobs

The Unicode-tag and homoglyph attacks were already covered.
**Morse code was not.**

## What ships

`backend/app/services/security/prompt_injection_scanner.py` gains:

- `_MORSE_TABLE` -- ITU Morse for the 26 letters + 10 digits
- `_scan_morse_code(content)` method -- a new closed scan stage

### Detection rule

The scanner triggers when:

1. A regex finds a run of 6+ Morse-shaped tokens (each token is
   1-7 dots/dashes, separated by space or `/`).
2. At least 6 of those tokens are valid in the ITU table.
3. The first 30 tokens decoded reveal text content.

### Severity escalation

The decoded content is searched for high-signal substrings:
`IGNORE / SYSTEM / PROMPT / OVERRIDE / WALLET / TRANSFER / TOKEN /
APIKEY / API / KEY / SECRET / ROOT / SUDO / EXEC`. Hit -> severity
HIGH (confidence 0.92). No hit -> severity MEDIUM (confidence 0.7,
since long Morse blobs in operator input are themselves anomalous).

### False-positive guard

- A short markdown separator `---` does NOT trigger (< 6 valid
  tokens).
- An English sentence with hyphens and dashes does NOT trigger.
- A code block with dash-runs does NOT trigger as long as the run
  doesn't span 6+ valid Morse codepoints separated by spaces.

## Tests

`backend/tests/test_morse_injection_defense.py` -- 6 tests:

```
TestMorseDetection::test_ignore_previous_morse_high_severity
TestMorseDetection::test_wallet_morse_high_severity
TestMorseDetection::test_short_dash_run_does_not_trigger
TestMorseDetection::test_english_with_dashes_does_not_trigger
TestPipelineIntegration::test_morse_finding_quarantined
TestPipelineIntegration::test_morse_does_not_break_normal_text
```

Sanity regression: all 14 existing prompt-injection-scanner tests
still pass alongside (20/20 pass on the combined fast subset).

## Hard rules audit

| Rule | Status |
|---|---|
| Detect Morse-encoded smuggling | enforced + tested |
| Quarantine the matched span | enforced -- existing `_quarantine` covers any encoded_blob category finding |
| No regression on existing scanners | confirmed -- 14/14 prior tests pass |
| Conservative trigger (no FP storm) | gate is 6+ valid Morse tokens; dashes in normal text are safe |
| Decoded-text inspection bounded | first 30 tokens only; no DoS via giant Morse blob |

## Files

```
modified:   backend/app/services/security/prompt_injection_scanner.py    (+85 lines)
new:        backend/tests/test_morse_injection_defense.py                 (95 lines, 6 tests)
new:        docs/Ultraview/PR_ENCODED_INJECTION_DEFENSE_HARDENING_REPORT.md
```

## What this PR does NOT do

- Does NOT add a generic ROT13 / leetspeak decoder. The pattern
  scanner already catches `IGNORE PREVIOUS` and family in plain
  text; ROT13 of those phrases is a future gap that warrants its
  own scoped PR with FP guards.
- Does NOT block all dash-heavy input. The conservative trigger
  exists specifically to avoid breaking markdown / code paste.
- Does NOT change the SecurityGate decision logic. A HIGH-severity
  morse_code_run finding flows through the same `_decide` path as
  any other HIGH finding -> quarantine + suspicious verdict.

## Next: PR-8 -- Controlled Execution Design Lock
