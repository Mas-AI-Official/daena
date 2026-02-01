"""
Shadow Agent — Invisible Monitoring and Deception Coordination

Runs silently in the background, monitoring data streams for
manipulation attempts and coordinating the honeypot/canary system.

Other agents don't know Shadow exists unless it finds something.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import asyncio
import re

logger = logging.getLogger(__name__)


@dataclass
class ThreatAlert:
    """A threat detected by Shadow"""
    alert_id: str
    alert_type: str  # honeypot_hit, canary_triggered, injection_attempt, anomaly
    severity: str    # info, low, medium, high, critical
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = ""
    reported: bool = False
    
    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


class ShadowAgent:
    """
    The invisible eye of Daena.
    
    Responsibilities:
    1. Monitor all incoming data for manipulation attempts
    2. Coordinate honeypots and canary tokens
    3. Report threats to the Council silently
    4. Build threat intelligence from attack patterns
    
    Shadow never announces itself. Other agents don't know it's running.
    Only the Founder sees its dashboard.
    """
    
    def __init__(self):
        self._storage_path = Path(__file__).parent.parent.parent.parent / ".ledger" / "shadow.json"
        self._alerts: List[ThreatAlert] = []
        self._monitoring = False
        self._patterns = self._load_patterns()
        
        # Stats
        self._stats = {
            "alerts_total": 0,
            "honeypot_hits": 0,
            "canary_triggers": 0,
            "injections_blocked": 0,
            "anomalies_detected": 0
        }
        
        self._load_state()
    
    def _load_patterns(self) -> Dict[str, List[str]]:
        """Load detection patterns."""
        return {
            # Prompt injection patterns
            "injection": [
                r"ignore previous instructions",
                r"forget everything",
                r"you are now",
                r"pretend to be",
                r"system prompt",
                r"developer mode",
                r"jailbreak",
                r"DAN mode",
                r"\[INST\]",
                r"<\|im_start\|>",
            ],
            # Credential probing patterns
            "credential_probe": [
                r"api[_-]?key",
                r"secret[_-]?key",
                r"password",
                r"access[_-]?token",
                r"private[_-]?key",
                r"\.env",
                r"credentials",
            ],
            # Path traversal patterns
            "path_traversal": [
                r"\.\./",
                r"\.\.\\",
                r"/etc/passwd",
                r"/etc/shadow",
                r"win\.ini",
            ],
            # Command injection patterns
            "command_injection": [
                r";\s*(?:cat|ls|rm|wget|curl)",
                r"\|\s*(?:bash|sh|cmd)",
                r"\$\(.*\)",
                r"`.*`",
            ]
        }
    
    def _load_state(self):
        """Load persistent state."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                self._alerts = [ThreatAlert(**a) for a in data.get("alerts", [])[-1000:]]
                self._stats = data.get("stats", self._stats)
            except Exception as e:
                logger.error(f"Shadow: Failed to load state: {e}")
    
    def _save_state(self):
        """Save persistent state."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                json.dump({
                    "alerts": [a.__dict__ for a in self._alerts[-1000:]],
                    "stats": self._stats,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Shadow: Failed to save state: {e}")
    
    def scan_input(self, content: str, source: str = "unknown", metadata: Optional[Dict] = None) -> List[ThreatAlert]:
        """
        Scan incoming content for threats.
        
        Called for every user input, API request, and data ingestion.
        Returns list of detected threats (empty if clean).
        """
        alerts = []
        meta = metadata or {}
        
        # Check each pattern category
        for category, patterns in self._patterns.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, content, re.IGNORECASE):
                        alert = ThreatAlert(
                            alert_id=f"shd_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}",
                            alert_type=category,
                            severity=self._get_severity(category),
                            source_ip=meta.get("ip"),
                            user_agent=meta.get("user_agent"),
                            details={
                                "pattern": pattern,
                                "source": source,
                                "content_preview": content[:200],
                                "metadata": meta
                            }
                        )
                        alerts.append(alert)
                except re.error:
                    continue
        
        # Log and store alerts
        for alert in alerts:
            self._log_alert(alert)
        
        return alerts
    
    def _get_severity(self, category: str) -> str:
        """Map category to severity level."""
        severity_map = {
            "injection": "high",
            "credential_probe": "medium",
            "path_traversal": "high",
            "command_injection": "critical"
        }
        return severity_map.get(category, "medium")
    
    def _log_alert(self, alert: ThreatAlert):
        """Log an alert silently."""
        self._alerts.append(alert)
        self._stats["alerts_total"] += 1
        
        # Update category stats
        if "injection" in alert.alert_type:
            self._stats["injections_blocked"] += 1
        elif alert.alert_type == "honeypot_hit":
            self._stats["honeypot_hits"] += 1
        elif alert.alert_type == "canary_triggered":
            self._stats["canary_triggers"] += 1
        else:
            self._stats["anomalies_detected"] += 1
        
        self._save_state()
        
        # Silent logging - no external notification unless critical
        if alert.severity == "critical":
            logger.warning(f"Shadow: Critical alert - {alert.alert_type}")
    
    def report_honeypot_hit(self, honeypot_id: str, request_data: Dict[str, Any]):
        """
        Report when a honeypot is triggered.
        
        Called by the honeypot routes when accessed.
        """
        alert = ThreatAlert(
            alert_id=f"hp_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}",
            alert_type="honeypot_hit",
            severity="high",
            source_ip=request_data.get("ip"),
            user_agent=request_data.get("user_agent"),
            details={
                "honeypot_id": honeypot_id,
                "path": request_data.get("path"),
                "method": request_data.get("method"),
                "headers": request_data.get("headers", {}),
                "body": request_data.get("body", "")[:500]
            }
        )
        self._log_alert(alert)
        
        # Report to threat intel
        self._report_to_intel(alert)
        
        return alert
    
    def report_canary_trigger(self, canary_id: str, trigger_data: Dict[str, Any]):
        """
        Report when a canary token is triggered.
        
        Called when a fake credential is used somewhere.
        """
        alert = ThreatAlert(
            alert_id=f"can_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}",
            alert_type="canary_triggered",
            severity="critical",
            source_ip=trigger_data.get("ip"),
            user_agent=trigger_data.get("user_agent"),
            details={
                "canary_id": canary_id,
                "canary_type": trigger_data.get("type"),
                "usage_context": trigger_data.get("context"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        self._log_alert(alert)
        self._report_to_intel(alert)
        
        return alert
    
    def _report_to_intel(self, alert: ThreatAlert):
        """Report alert to threat intelligence for profiling."""
        try:
            from .threat_intel import get_threat_intel
            intel = get_threat_intel()
            intel.process_alert(alert)
        except Exception as e:
            logger.error(f"Shadow: Failed to report to intel: {e}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[ThreatAlert]:
        """Get alerts from the last N hours."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        return [a for a in self._alerts if a.detected_at >= cutoff_str]
    
    def get_alerts_by_severity(self, severity: str) -> List[ThreatAlert]:
        """Get all alerts of a specific severity."""
        return [a for a in self._alerts if a.severity == severity]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Shadow department statistics."""
        recent = self.get_recent_alerts(24)
        
        return {
            **self._stats,
            "alerts_24h": len(recent),
            "critical_24h": sum(1 for a in recent if a.severity == "critical"),
            "high_24h": sum(1 for a in recent if a.severity == "high"),
            "monitoring_active": self._monitoring,
            "patterns_loaded": sum(len(p) for p in self._patterns.values())
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for the Shadow dashboard (founder only)."""
        recent = self.get_recent_alerts(24)
        
        # Group by type
        by_type = {}
        for alert in recent:
            by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1
        
        # Get unique IPs
        unique_ips = set(a.source_ip for a in recent if a.source_ip)
        
        return {
            "stats": self.get_stats(),
            "alerts_24h": [a.__dict__ for a in recent[-50:]],  # Last 50
            "by_type": by_type,
            "unique_attackers": len(unique_ips),
            "last_critical": next(
                (a.__dict__ for a in reversed(self._alerts) if a.severity == "critical"),
                None
            )
        }


# Singleton
_shadow: Optional[ShadowAgent] = None


def get_shadow_agent() -> ShadowAgent:
    """Get the global Shadow agent instance."""
    global _shadow
    if _shadow is None:
        _shadow = ShadowAgent()
    return _shadow
