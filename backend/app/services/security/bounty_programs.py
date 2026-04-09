"""Bug Bounty Program Configuration.

Defines authorized bug bounty programs with their scope rules.
The VulnScannerAgent checks targets against these scopes before
scanning. This is a hard safety check -- even AGI mode respects it.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field


@dataclass
class BountyProgram:
    """A registered bug bounty program."""
    name: str
    platform: str  # "bughunters.google.com", "hackerone", "bugcrowd"
    scope: list[str]  # Wildcard patterns: ["*.google.com", "*.googleapis.com"]
    out_of_scope: list[str] = field(default_factory=list)
    url: str = ""
    registered: bool = True
    notes: str = ""


PROGRAMS: dict[str, BountyProgram] = {
    "google_vrp": BountyProgram(
        name="Google Vulnerability Reward Program",
        platform="bughunters.google.com",
        scope=[
            "*.google.com",
            "*.googleapis.com",
            "*.cloud.google.com",
            "*.googleusercontent.com",
            "*.withgoogle.com",
            "*.google.co.*",
        ],
        out_of_scope=[
            "accounts.google.com/login",
            "mail.google.com",
            "drive.google.com",
        ],
        url="https://bughunters.google.com/about/rules/6625378258649088/google-and-alphabet-vulnerability-reward-program-vrp-rules",
        notes="Masoud registered: bughunters.google.com/profile/5b0db196-b87e-4b13-b7c5-0353d339f362",
    ),
    "xai_bug_bounty": BountyProgram(
        name="xAI Bug Bounty",
        platform="hackerone",
        scope=[
            "*.x.ai",
            "api.x.ai",
            "grok.x.ai",
            "console.x.ai",
        ],
        url="https://hackerone.com/xai",
    ),
    "bugcrowd_general": BountyProgram(
        name="Bugcrowd Programs",
        platform="bugcrowd",
        scope=[],  # Set per-program
        url="https://bugcrowd.com",
        notes="Masoud identity verified on Bugcrowd",
    ),
}


def is_target_authorized(target: str) -> tuple[bool, str]:
    """Check if a target is within any registered bounty program scope.

    Returns:
        (authorized, program_name) -- True + program name if authorized,
        False + reason if not.
    """
    target_lower = target.lower().strip()

    for prog_id, prog in PROGRAMS.items():
        if not prog.registered:
            continue

        # Check out-of-scope first
        for pattern in prog.out_of_scope:
            if fnmatch.fnmatch(target_lower, pattern.lower()):
                return False, f"Target '{target}' is explicitly OUT OF SCOPE for {prog.name}"

        # Check in-scope
        for pattern in prog.scope:
            if fnmatch.fnmatch(target_lower, pattern.lower()):
                return True, prog.name

    return False, (
        f"Target '{target}' is not in any registered bug bounty program scope. "
        f"Register the program first or add the target to an existing program."
    )


def get_program(program_id: str) -> BountyProgram | None:
    """Get a bounty program by ID."""
    return PROGRAMS.get(program_id)


def list_programs() -> list[dict]:
    """List all registered programs."""
    return [
        {
            "id": pid,
            "name": p.name,
            "platform": p.platform,
            "scope_count": len(p.scope),
            "registered": p.registered,
            "url": p.url,
        }
        for pid, p in PROGRAMS.items()
    ]
