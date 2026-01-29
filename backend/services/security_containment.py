"""
Security containment playbooks for Guardian / Incident response.

- Block IPs (in-memory; from deception hits or manual).
- On deception hit: count per IP; auto-block and optionally lockdown after N hits.
- Playbook actions: lockdown, block_ip, unblock_ip.
"""

import logging
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# Config
DECEPTION_HITS_BEFORE_BLOCK = int(os.getenv("DECEPTION_HITS_BEFORE_BLOCK", "3"))
DECEPTION_HITS_WINDOW_SEC = int(os.getenv("DECEPTION_HITS_WINDOW_SEC", "300"))
AUTO_LOCKDOWN_ON_BLOCK = os.getenv("AUTO_LOCKDOWN_ON_BLOCK", "false").lower() in ("1", "true", "yes")

_blocked_ips: Set[str] = set()
_hits_per_ip: Dict[str, List[float]] = defaultdict(list)
_playbook_log: List[Dict[str, Any]] = []
_MAX_LOG = 100


def _client_ip_from_hit(hit: Dict[str, Any]) -> str:
    """Extract client IP from deception hit (x_forwarded_for or client_host)."""
    forwarded = hit.get("x_forwarded_for") or hit.get("client_host") or ""
    if "," in forwarded:
        return forwarded.split(",")[0].strip()
    return forwarded.strip() or "unknown"


def _clean_old_hits(ip: str) -> None:
    cutoff = time.time() - DECEPTION_HITS_WINDOW_SEC
    _hits_per_ip[ip] = [t for t in _hits_per_ip[ip] if t > cutoff]


def on_deception_hit(hit: Dict[str, Any]) -> None:
    """
    Called when a decoy route is hit. Counts hits per IP; auto-blocks and
    optionally triggers lockdown after DECEPTION_HITS_BEFORE_BLOCK in window.
    """
    ip = _client_ip_from_hit(hit)
    if ip == "unknown":
        return
    _clean_old_hits(ip)
    _hits_per_ip[ip].append(time.time())
    count = len(_hits_per_ip[ip])
    if count >= DECEPTION_HITS_BEFORE_BLOCK:
        if ip not in _blocked_ips:
            _blocked_ips.add(ip)
            _log_playbook("auto_block_ip", {"ip": ip, "reason": "deception_hits", "count": count})
            logger.warning("[CONTAINMENT] Auto-blocked IP %s after %d deception hits", ip, count)
        if AUTO_LOCKDOWN_ON_BLOCK:
            try:
                from backend.config.security_state import set_lockdown
                set_lockdown(True)
                _log_playbook("auto_lockdown", {"reason": "deception_auto_block", "ip": ip})
                logger.warning("[CONTAINMENT] Auto lockdown after deception auto-block (IP %s)", ip)
            except Exception as e:
                logger.warning("Could not set lockdown: %s", e)


def _log_playbook(action: str, payload: Dict[str, Any]) -> None:
    _playbook_log.append({
        "action": action,
        "payload": payload,
        "ts": time.time(),
    })
    if len(_playbook_log) > _MAX_LOG:
        _playbook_log.pop(0)


def block_ip(ip: str, reason: str = "manual") -> None:
    if ip:
        _blocked_ips.add(ip.strip())
        _log_playbook("block_ip", {"ip": ip, "reason": reason})


def unblock_ip(ip: str) -> None:
    if ip:
        _blocked_ips.discard(ip.strip())
        _log_playbook("unblock_ip", {"ip": ip})


def get_blocked_ips() -> Set[str]:
    return set(_blocked_ips)


def is_blocked(ip: str) -> bool:
    if not ip:
        return False
    return ip.strip() in _blocked_ips


def run_playbook(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a containment action: lockdown, block_ip, unblock_ip.
    Returns result dict for API response.
    """
    if action == "lockdown":
        try:
            from backend.config.security_state import set_lockdown
            set_lockdown(True)
            _log_playbook("lockdown", payload)
            return {"ok": True, "action": "lockdown", "message": "Lockdown set"}
        except Exception as e:
            return {"ok": False, "action": "lockdown", "error": str(e)}
    if action == "block_ip":
        ip = (payload or {}).get("ip") or ""
        if not ip:
            return {"ok": False, "action": "block_ip", "error": "Missing ip"}
        block_ip(ip, reason=payload.get("reason", "playbook"))
        return {"ok": True, "action": "block_ip", "ip": ip}
    if action == "unblock_ip":
        ip = (payload or {}).get("ip") or ""
        if not ip:
            return {"ok": False, "action": "unblock_ip", "error": "Missing ip"}
        unblock_ip(ip)
        return {"ok": True, "action": "unblock_ip", "ip": ip}
    return {"ok": False, "action": action, "error": "Unknown action"}


def get_status() -> Dict[str, Any]:
    return {
        "blocked_ips": list(get_blocked_ips()),
        "blocked_count": len(_blocked_ips),
        "recent_playbook": _playbook_log[-20:],
        "config": {
            "deception_hits_before_block": DECEPTION_HITS_BEFORE_BLOCK,
            "auto_lockdown_on_block": AUTO_LOCKDOWN_ON_BLOCK,
        },
    }
