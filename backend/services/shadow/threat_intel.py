"""
Threat Intelligence — TTP Logging and Attacker Profiling

Collects and analyzes threat data to build internal threat database.
Learns attack patterns to improve early detection.

Per DAENA_NEW_BLUEPRINT.html: "Daena builds an internal threat database"
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class TTP:
    """Tactics, Techniques, and Procedures observed."""
    ttp_id: str
    tactic: str           # reconnaissance, initial_access, execution, etc.
    technique: str        # specific technique used
    description: str
    first_seen: str
    last_seen: str
    occurrence_count: int = 1
    associated_ips: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)


@dataclass
class AttackerProfile:
    """Profile of an observed attacker."""
    profile_id: str
    source_ip: str
    first_seen: str
    last_seen: str
    hit_count: int = 1
    user_agents: List[str] = field(default_factory=list)
    targeted_paths: List[str] = field(default_factory=list)
    ttps_used: List[str] = field(default_factory=list)
    threat_level: str = "unknown"  # unknown, low, medium, high, severe
    notes: str = ""


class ThreatIntel:
    """
    Threat Intelligence Database.
    
    Collects and correlates threat data to:
    1. Profile attackers by IP/behavior
    2. Catalog TTPs (Tactics, Techniques, Procedures)
    3. Improve detection over time
    4. Generate threat reports
    
    Uses MITRE ATT&CK framework concepts.
    """
    
    def __init__(self):
        self._storage_path = Path(__file__).parent.parent.parent.parent / ".ledger" / "threat_intel.json"
        
        self._profiles: Dict[str, AttackerProfile] = {}
        self._ttps: Dict[str, TTP] = {}
        self._raw_events: List[Dict[str, Any]] = []
        
        self._load_state()
    
    def _load_state(self):
        """Load persistent state."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                self._profiles = {k: AttackerProfile(**v) for k, v in data.get("profiles", {}).items()}
                self._ttps = {k: TTP(**v) for k, v in data.get("ttps", {}).items()}
                self._raw_events = data.get("events", [])[-1000:]
            except Exception as e:
                logger.error(f"ThreatIntel: Failed to load state: {e}")
    
    def _save_state(self):
        """Save persistent state."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                json.dump({
                    "profiles": {k: v.__dict__ for k, v in self._profiles.items()},
                    "ttps": {k: v.__dict__ for k, v in self._ttps.items()},
                    "events": self._raw_events[-1000:],
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"ThreatIntel: Failed to save state: {e}")
    
    def process_alert(self, alert) -> Optional[AttackerProfile]:
        """
        Process an alert from Shadow agent.
        
        Updates attacker profiles and TTPs.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Store raw event
        self._raw_events.append({
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type,
            "source_ip": alert.source_ip,
            "timestamp": alert.detected_at,
            "details": alert.details
        })
        
        # Update or create attacker profile
        profile = None
        if alert.source_ip:
            profile = self._update_profile(alert, now)
        
        # Extract and log TTPs
        self._extract_ttps(alert, now)
        
        self._save_state()
        return profile
    
    def _update_profile(self, alert, now: str) -> AttackerProfile:
        """Update or create attacker profile."""
        ip = alert.source_ip
        profile_id = f"atk_{hashlib.md5(ip.encode()).hexdigest()[:16]}"
        
        if profile_id in self._profiles:
            profile = self._profiles[profile_id]
            profile.last_seen = now
            profile.hit_count += 1
            
            # Add user agent if new
            ua = alert.user_agent
            if ua and ua not in profile.user_agents:
                profile.user_agents.append(ua)
            
            # Add targeted path
            path = alert.details.get("path", "")
            if path and path not in profile.targeted_paths:
                profile.targeted_paths.append(path)
            
            # Update threat level based on activity
            profile.threat_level = self._calculate_threat_level(profile)
            
        else:
            profile = AttackerProfile(
                profile_id=profile_id,
                source_ip=ip,
                first_seen=now,
                last_seen=now,
                user_agents=[alert.user_agent] if alert.user_agent else [],
                targeted_paths=[alert.details.get("path", "")] if alert.details.get("path") else [],
                threat_level="medium"
            )
            self._profiles[profile_id] = profile
        
        return profile
    
    def _calculate_threat_level(self, profile: AttackerProfile) -> str:
        """Calculate threat level based on activity."""
        score = 0
        
        # Hit count factor
        if profile.hit_count > 100:
            score += 3
        elif profile.hit_count > 20:
            score += 2
        elif profile.hit_count > 5:
            score += 1
        
        # Target diversity factor
        if len(profile.targeted_paths) > 10:
            score += 2
        elif len(profile.targeted_paths) > 3:
            score += 1
        
        # TTP sophistication factor
        if len(profile.ttps_used) > 5:
            score += 2
        elif len(profile.ttps_used) > 2:
            score += 1
        
        # Map score to level
        if score >= 6:
            return "severe"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"
    
    def _extract_ttps(self, alert, now: str):
        """Extract TTPs from alert."""
        alert_type = alert.alert_type
        
        # Map alert types to TTPs
        ttp_mapping = {
            "injection": ("execution", "command_line_interface", "Attempted prompt/command injection"),
            "credential_probe": ("credential_access", "credential_dumping", "Attempted to access credentials"),
            "path_traversal": ("discovery", "file_directory_discovery", "Path traversal attempt"),
            "command_injection": ("execution", "shell_command", "Command injection attempt"),
            "honeypot_hit": ("reconnaissance", "active_scanning", "Probing honeypot endpoints"),
            "canary_triggered": ("credential_access", "valid_accounts", "Used stolen canary credentials"),
        }
        
        if alert_type in ttp_mapping:
            tactic, technique, description = ttp_mapping[alert_type]
            self._log_ttp(tactic, technique, description, alert.source_ip, now)
    
    def _log_ttp(self, tactic: str, technique: str, description: str, source_ip: Optional[str], now: str):
        """Log a TTP observation."""
        ttp_id = f"ttp_{tactic}_{technique}"
        
        if ttp_id in self._ttps:
            ttp = self._ttps[ttp_id]
            ttp.last_seen = now
            ttp.occurrence_count += 1
            if source_ip and source_ip not in ttp.associated_ips:
                ttp.associated_ips.append(source_ip)
        else:
            ttp = TTP(
                ttp_id=ttp_id,
                tactic=tactic,
                technique=technique,
                description=description,
                first_seen=now,
                last_seen=now,
                associated_ips=[source_ip] if source_ip else []
            )
            self._ttps[ttp_id] = ttp
    
    def get_profile(self, ip: str) -> Optional[AttackerProfile]:
        """Get attacker profile by IP."""
        profile_id = f"atk_{hashlib.md5(ip.encode()).hexdigest()[:16]}"
        return self._profiles.get(profile_id)
    
    def get_high_threat_ips(self) -> List[str]:
        """Get list of high/severe threat IPs."""
        return [
            p.source_ip for p in self._profiles.values()
            if p.threat_level in ("high", "severe")
        ]
    
    def is_known_attacker(self, ip: str) -> bool:
        """Check if IP is a known attacker."""
        profile = self.get_profile(ip)
        return profile is not None and profile.threat_level in ("medium", "high", "severe")
    
    def get_trending_ttps(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get trending TTPs in last N days."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        trending = []
        for ttp in self._ttps.values():
            if ttp.last_seen >= cutoff:
                trending.append({
                    "ttp_id": ttp.ttp_id,
                    "tactic": ttp.tactic,
                    "technique": ttp.technique,
                    "description": ttp.description,
                    "occurrences": ttp.occurrence_count,
                    "unique_attackers": len(ttp.associated_ips)
                })
        
        trending.sort(key=lambda x: x["occurrences"], reverse=True)
        return trending[:10]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get threat intelligence statistics."""
        return {
            "total_profiles": len(self._profiles),
            "severe_threats": sum(1 for p in self._profiles.values() if p.threat_level == "severe"),
            "high_threats": sum(1 for p in self._profiles.values() if p.threat_level == "high"),
            "ttps_cataloged": len(self._ttps),
            "events_processed": len(self._raw_events),
            "unique_ips": len(set(e.get("source_ip") for e in self._raw_events if e.get("source_ip")))
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate threat intelligence report."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_stats(),
            "trending_ttps": self.get_trending_ttps(),
            "high_threat_actors": [
                {
                    "ip": p.source_ip,
                    "threat_level": p.threat_level,
                    "hits": p.hit_count,
                    "first_seen": p.first_seen,
                    "last_seen": p.last_seen
                }
                for p in self._profiles.values()
                if p.threat_level in ("high", "severe")
            ][:20],
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on data."""
        recs = []
        
        # Check for high activity
        high_threat_count = sum(1 for p in self._profiles.values() if p.threat_level in ("high", "severe"))
        if high_threat_count > 5:
            recs.append("Consider implementing IP rate limiting - multiple high-threat actors detected")
        
        # Check for credential probing
        cred_ttp = self._ttps.get("ttp_credential_access_credential_dumping")
        if cred_ttp and cred_ttp.occurrence_count > 10:
            recs.append("Credential probing detected - rotate sensitive API keys and secrets")
        
        # Check for canary triggers
        canary_ttp = self._ttps.get("ttp_credential_access_valid_accounts")
        if canary_ttp:
            recs.append("Canary credentials were used - possible data leak, investigate immediately")
        
        if not recs:
            recs.append("No critical recommendations - continue monitoring")
        
        return recs


# Singleton
_intel: Optional[ThreatIntel] = None


def get_threat_intel() -> ThreatIntel:
    """Get the global threat intelligence instance."""
    global _intel
    if _intel is None:
        _intel = ThreatIntel()
    return _intel
