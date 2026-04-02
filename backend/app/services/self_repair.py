"""SelfRepair: Daena fixes her own errors automatically.

When a tool call, runtime execution, or test fails, the self-repair
loop kicks in:
    1. Parse the error (traceback, exit code, error message)
    2. Identify the broken file and line number
    3. Read the broken code
    4. Generate a fix using the LLM
    5. Apply the fix
    6. Re-run the failing operation
    7. If still broken, try again (max 3 attempts)

This is what makes Daena self-healing. Instead of stopping at an error
and telling the user "try again later", she diagnoses and fixes.

BACKGROUND PATH ONLY -- uses LLM calls for diagnosis
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_REPAIR_ATTEMPTS = 3


@dataclass
class RepairResult:
    """Result of a self-repair attempt."""
    success: bool
    attempts: int
    error_type: str = ""
    file_fixed: str = ""
    description: str = ""
    original_error: str = ""


def extract_error_location(error_text: str) -> dict[str, Any]:
    """Parse a Python traceback to find the broken file and line.

    Returns:
        Dict with file_path, line_number, function_name, error_type, error_message
    """
    result: dict[str, Any] = {
        "file_path": "",
        "line_number": 0,
        "function_name": "",
        "error_type": "",
        "error_message": "",
    }

    # Extract the last file reference from traceback
    file_matches = re.findall(
        r'File "([^"]+)", line (\d+), in (.+)',
        error_text,
    )
    if file_matches:
        last = file_matches[-1]
        result["file_path"] = last[0]
        result["line_number"] = int(last[1])
        result["function_name"] = last[2]

    # Extract error type and message
    error_match = re.search(r'(\w+Error|\w+Exception): (.+?)$', error_text, re.MULTILINE)
    if error_match:
        result["error_type"] = error_match.group(1)
        result["error_message"] = error_match.group(2).strip()
    else:
        # Try simpler patterns
        for pattern in [
            r'Error: (.+?)$',
            r'error: (.+?)$',
            r'FAILED (.+?)$',
        ]:
            m = re.search(pattern, error_text, re.MULTILINE)
            if m:
                result["error_message"] = m.group(1).strip()
                break

    return result


async def attempt_self_repair(
    error_text: str,
    context: str = "",
    *,
    dry_run: bool = False,
) -> RepairResult:
    """Attempt to automatically fix an error.

    Args:
        error_text: The full error output (traceback, logs, etc.)
        context: Additional context about what was being done
        dry_run: If True, diagnose but don't apply fix

    Returns:
        RepairResult with success status and details
    """
    location = extract_error_location(error_text)

    if not location["file_path"]:
        return RepairResult(
            success=False,
            attempts=0,
            error_type="unknown",
            description="Could not extract error location from output",
            original_error=error_text[:500],
        )

    logger.info(
        "self_repair.attempting",
        file=location["file_path"],
        line=location["line_number"],
        error_type=location["error_type"],
    )

    from app.services.agent_core.system_access import SystemAccess
    sys_access = SystemAccess(agi_mode=True)

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        try:
            # Step 1: Read the broken file
            try:
                file_content = await sys_access.read_file(location["file_path"])
            except Exception:
                return RepairResult(
                    success=False,
                    attempts=attempt,
                    error_type=location["error_type"],
                    description=f"Cannot read file: {location['file_path']}",
                    original_error=error_text[:500],
                )

            # Step 2: Extract the broken section (10 lines around the error)
            lines = file_content.split("\n")
            start = max(0, location["line_number"] - 5)
            end = min(len(lines), location["line_number"] + 5)
            broken_section = "\n".join(
                f"{i+1}: {line}" for i, line in enumerate(lines[start:end], start=start)
            )

            # Step 3: Use Ollama to diagnose and generate fix
            import httpx
            prompt = f"""You are a Python debugging expert. Fix this error.

ERROR:
{error_text[:1000]}

BROKEN CODE (from {location['file_path']}):
{broken_section}

{f"CONTEXT: {context}" if context else ""}

Respond with ONLY the fixed code section (no explanation). Include the same line range ({start+1} to {end}).
Do NOT include line numbers in your response -- just the fixed code."""

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "llama3.1:8b",
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                    if resp.status_code == 200:
                        fix = resp.json().get("response", "").strip()
                    else:
                        fix = ""
            except Exception as llm_exc:
                logger.warning("self_repair.llm_failed", error=str(llm_exc))
                return RepairResult(
                    success=False,
                    attempts=attempt,
                    error_type=location["error_type"],
                    description=f"LLM diagnosis failed: {llm_exc}",
                    original_error=error_text[:500],
                )

            if not fix or dry_run:
                return RepairResult(
                    success=False,
                    attempts=attempt,
                    error_type=location["error_type"],
                    file_fixed=location["file_path"],
                    description=f"Diagnosed: {location['error_type']} at line {location['line_number']}. {'Dry run.' if dry_run else 'No fix generated.'}",
                    original_error=error_text[:500],
                )

            # Step 4: Apply the fix
            fix_lines = fix.split("\n")
            # Remove any code block markers
            if fix_lines and fix_lines[0].startswith("```"):
                fix_lines = fix_lines[1:]
            if fix_lines and fix_lines[-1].startswith("```"):
                fix_lines = fix_lines[:-1]

            # Replace the broken section
            new_lines = lines[:start] + fix_lines + lines[end:]
            new_content = "\n".join(new_lines)

            await sys_access.write_file(location["file_path"], new_content)

            logger.info(
                "self_repair.fix_applied",
                file=location["file_path"],
                attempt=attempt,
                lines_changed=f"{start+1}-{end}",
            )

            # Step 5: Verify by running tests
            test_result = await sys_access.run_command(
                f"cd {location['file_path'].rsplit('/', 1)[0]} && python -m pytest --tb=short -x -q 2>&1 | tail -3",
                timeout=60,
            )
            test_output = test_result.get("stdout", "")

            if "passed" in test_output and "failed" not in test_output:
                return RepairResult(
                    success=True,
                    attempts=attempt,
                    error_type=location["error_type"],
                    file_fixed=location["file_path"],
                    description=f"Fixed {location['error_type']} at {location['file_path']}:{location['line_number']} on attempt {attempt}",
                    original_error=error_text[:500],
                )

            # Fix didn't work -- try again
            logger.info(
                "self_repair.fix_failed_retrying",
                attempt=attempt,
                test_output=test_output[:200],
            )

        except Exception as exc:
            logger.error("self_repair.attempt_failed", attempt=attempt, error=str(exc))

    return RepairResult(
        success=False,
        attempts=MAX_REPAIR_ATTEMPTS,
        error_type=location["error_type"],
        file_fixed=location["file_path"],
        description=f"Failed after {MAX_REPAIR_ATTEMPTS} attempts",
        original_error=error_text[:500],
    )
