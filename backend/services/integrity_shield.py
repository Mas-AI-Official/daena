"""
Data Integrity Shield for Daena AI VP

This is Daena's #1 competitive differentiator.
While other AI agents get manipulated by fake data, Daena verifies everything.

Three-layer verification:
1. Source Verification - Origin check, reputation tracking, cross-reference
2. Consistency Check - Compare against existing knowledge, flag conflicts
3. Manipulation Detection - Pattern detection, injection prevention

Created: 2026-01-31
Author: Daena AI System
"""

import logging
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Trust levels for data sources"""
    BLOCKED = "blocked"       # Trust score < 30
    UNTRUSTED = "untrusted"   # Trust score 30-39
    CAUTION = "caution"       # Trust score 40-59
    NEUTRAL = "neutral"       # Trust score 60-69
    TRUSTED = "trusted"       # Trust score 70-89
    VERIFIED = "verified"     # Trust score 90+


class VerificationResult(str, Enum):
    """Result of data verification"""
    PASSED = "passed"
    FLAGGED = "flagged"
    BLOCKED = "blocked"
    CONFLICT = "conflict"
    INJECTION_DETECTED = "injection_detected"


@dataclass
class SourceInfo:
    """Information about a data source"""
    source_id: str
    domain: str
    trust_score: float = 50.0  # Start neutral
    times_verified: int = 0
    times_flagged: int = 0
    times_blocked: int = 0
    first_seen: str = ""
    last_seen: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = datetime.utcnow().isoformat()
        self.last_seen = datetime.utcnow().isoformat()
    
    @property
    def trust_level(self) -> TrustLevel:
        if self.trust_score < 30:
            return TrustLevel.BLOCKED
        elif self.trust_score < 40:
            return TrustLevel.UNTRUSTED
        elif self.trust_score < 60:
            return TrustLevel.CAUTION
        elif self.trust_score < 70:
            return TrustLevel.NEUTRAL
        elif self.trust_score < 90:
            return TrustLevel.TRUSTED
        else:
            return TrustLevel.VERIFIED


@dataclass
class VerificationReport:
    """Report from data verification"""
    result: VerificationResult
    source_info: Optional[SourceInfo] = None
    trust_score: float = 50.0
    flags: List[str] = field(default_factory=list)
    manipulation_score: float = 0.0
    cross_references: int = 0
    conflicts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "source_info": asdict(self.source_info) if self.source_info else None,
            "trust_score": self.trust_score,
            "flags": self.flags,
            "manipulation_score": self.manipulation_score,
            "cross_references": self.cross_references,
            "conflicts": self.conflicts,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp
        }


class TrustLedger:
    """
    Persistent trust scoring for data sources.
    Tracks reputation over time with decay and adjustment.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.sources: Dict[str, SourceInfo] = {}
        self.storage_path = storage_path or Path(".ledger/trust_ledger.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
    
    def _load(self) -> None:
        """Load trust ledger from disk"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for source_id, info in data.get("sources", {}).items():
                        self.sources[source_id] = SourceInfo(**info)
                logger.info(f"Loaded {len(self.sources)} sources from trust ledger")
        except Exception as e:
            logger.warning(f"Could not load trust ledger: {e}")
    
    def _save(self) -> None:
        """Save trust ledger to disk"""
        try:
            data = {
                "sources": {sid: asdict(info) for sid, info in self.sources.items()},
                "last_updated": datetime.utcnow().isoformat()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save trust ledger: {e}")
    
    def get_source(self, domain: str) -> SourceInfo:
        """Get or create source info for a domain"""
        source_id = self._domain_to_id(domain)
        if source_id not in self.sources:
            self.sources[source_id] = SourceInfo(
                source_id=source_id,
                domain=domain
            )
            self._save()
        else:
            self.sources[source_id].last_seen = datetime.utcnow().isoformat()
        return self.sources[source_id]
    
    def _domain_to_id(self, domain: str) -> str:
        """Convert domain to unique ID"""
        # Normalize domain
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        elif domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        domain = domain.split("/")[0]  # Remove path
        return hashlib.md5(domain.encode()).hexdigest()[:12]
    
    def update_trust(self, domain: str, delta: float, reason: str) -> SourceInfo:
        """Update trust score for a source"""
        source = self.get_source(domain)
        old_score = source.trust_score
        source.trust_score = max(0, min(100, source.trust_score + delta))
        
        if delta > 0:
            source.times_verified += 1
        elif delta < 0:
            source.times_flagged += 1
            if source.trust_score < 30:
                source.times_blocked += 1
        
        logger.info(f"Trust update: {domain} {old_score:.1f} -> {source.trust_score:.1f} ({reason})")
        self._save()
        return source
    
    def apply_decay(self, days_inactive: int = 30, decay_rate: float = 0.1) -> int:
        """Apply trust decay to inactive sources"""
        updated = 0
        now = datetime.utcnow()
        
        for source in self.sources.values():
            try:
                last_seen = datetime.fromisoformat(source.last_seen)
                days_since = (now - last_seen).days
                
                if days_since >= days_inactive:
                    weeks = days_since // 7
                    decay = source.trust_score * decay_rate * weeks
                    if decay > 1:
                        source.trust_score = max(30, source.trust_score - decay)
                        updated += 1
            except Exception:
                pass
        
        if updated:
            self._save()
            logger.info(f"Applied trust decay to {updated} sources")
        
        return updated
    
    def get_all_sources(self) -> List[SourceInfo]:
        """Get all tracked sources"""
        return list(self.sources.values())
    
    def get_blocked_sources(self) -> List[SourceInfo]:
        """Get all blocked sources (trust < 30)"""
        return [s for s in self.sources.values() if s.trust_score < 30]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trust ledger statistics"""
        sources = list(self.sources.values())
        if not sources:
            return {"total": 0}
        
        return {
            "total": len(sources),
            "blocked": len([s for s in sources if s.trust_level == TrustLevel.BLOCKED]),
            "untrusted": len([s for s in sources if s.trust_level == TrustLevel.UNTRUSTED]),
            "caution": len([s for s in sources if s.trust_level == TrustLevel.CAUTION]),
            "neutral": len([s for s in sources if s.trust_level == TrustLevel.NEUTRAL]),
            "trusted": len([s for s in sources if s.trust_level == TrustLevel.TRUSTED]),
            "verified": len([s for s in sources if s.trust_level == TrustLevel.VERIFIED]),
            "avg_trust": sum(s.trust_score for s in sources) / len(sources),
            "total_verifications": sum(s.times_verified for s in sources),
            "total_flags": sum(s.times_flagged for s in sources)
        }


class PromptInjectionDetector:
    """
    Detects prompt injection attempts in external data.
    Catches attempts to override Daena's instructions through data.
    """
    
    # Known injection patterns
    INJECTION_PATTERNS = [
        # Role override attempts
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|guidelines?)",
        r"(?i)you\s+are\s+now\s+(?!going|about)",
        r"(?i)forget\s+(everything|all|your)\s+(you|instructions?|rules?)",
        r"(?i)disregard\s+(all|your|the)\s+(previous|prior|above)",
        r"(?i)system\s*:\s*override",
        r"(?i)\[?admin\]?\s*:\s*",
        r"(?i)\[?system\]?\s*:\s*",
        r"(?i)new\s+instructions?\s*:",
        
        # Jailbreak attempts
        r"(?i)pretend\s+(you|to\s+be)\s+(are\s+)?(?!not)",
        r"(?i)act\s+as\s+if\s+you",
        r"(?i)roleplay\s+as",
        r"(?i)developer\s+mode",
        r"(?i)jailbreak",
        r"(?i)dan\s+mode",
        
        # Hidden instruction markers
        r"(?i)<\s*/?(?:system|instruction|override|prompt)\s*>",
        r"(?i)\[\s*hidden\s*\]",
        r"(?i)<!--.*(?:instruction|override|ignore).*-->",
    ]
    
    # Urgency patterns (manipulation)
    URGENCY_PATTERNS = [
        r"(?i)urgent\s*:\s*act\s+now",
        r"(?i)critical\s*:\s*immediate\s+action",
        r"(?i)breaking\s*:\s*you\s+must",
        r"(?i)emergency\s*:\s*override",
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self.compiled_urgency = [re.compile(p) for p in self.URGENCY_PATTERNS]
        self.detection_log: List[Dict[str, Any]] = []
    
    def detect(self, content: str, source: str = "unknown") -> Tuple[bool, List[str], float]:
        """
        Detect prompt injection in content.
        
        Returns:
            Tuple of (is_injection, matched_patterns, confidence_score)
        """
        if not content:
            return False, [], 0.0
        
        matches = []
        
        # Check for injection patterns
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(content):
                matches.append(f"injection_pattern_{i}")
        
        # Check for urgency manipulation
        for i, pattern in enumerate(self.compiled_urgency):
            if pattern.search(content):
                matches.append(f"urgency_pattern_{i}")
        
        # Check for suspicious structural elements
        if self._has_role_change_structure(content):
            matches.append("role_change_structure")
        
        # Calculate confidence score
        confidence = min(1.0, len(matches) * 0.3 + (0.2 if matches else 0))
        
        is_injection = len(matches) >= 2 or confidence >= 0.6
        
        if is_injection:
            self._log_detection(content, source, matches, confidence)
        
        return is_injection, matches, confidence
    
    def _has_role_change_structure(self, content: str) -> bool:
        """Check if content has suspicious role-change structure"""
        # Look for content that switches from data to instructions
        lines = content.split('\n')
        data_lines = 0
        instruction_lines = 0
        
        for line in lines:
            line = line.strip().lower()
            if any(word in line for word in ['you should', 'you must', 'you are', 'your task']):
                instruction_lines += 1
            elif line and not line.startswith('#'):
                data_lines += 1
        
        # Suspicious if few data lines but many instruction lines
        if instruction_lines > 3 and data_lines < instruction_lines:
            return True
        
        return False
    
    def _log_detection(self, content: str, source: str, matches: List[str], confidence: float) -> None:
        """Log a detection for audit trail"""
        self.detection_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            "content_preview": content[:200] if len(content) > 200 else content,
            "matches": matches,
            "confidence": confidence
        })
        logger.warning(f"Injection detected from {source}: {matches} (confidence: {confidence:.2f})")
    
    def strip_injections(self, content: str) -> str:
        """Remove detected injection patterns from content"""
        cleaned = content
        
        for pattern in self.compiled_patterns:
            cleaned = pattern.sub("[REMOVED]", cleaned)
        
        for pattern in self.compiled_urgency:
            cleaned = pattern.sub("[REMOVED]", cleaned)
        
        return cleaned
    
    def get_detection_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent detection log entries"""
        return self.detection_log[-limit:]


class SourceVerifier:
    """
    Verifies data sources before information reaches Daena.
    Three-layer verification: Origin, Consistency, Manipulation.
    """
    
    # Trusted source allowlist (can be extended via config)
    TRUSTED_DOMAINS = {
        # Official documentation
        "docs.python.org", "developer.mozilla.org", "docs.microsoft.com",
        # Major news
        "reuters.com", "apnews.com", "bbc.com",
        # Tech sources
        "github.com", "stackoverflow.com", "arxiv.org",
        # DeFi sources
        "etherscan.io", "bscscan.com", "polygonscan.com",
        "defillama.com", "dune.com",
        # Audit firms
        "openzeppelin.com", "consensys.net", "trailofbits.com"
    }
    
    def __init__(self, trust_ledger: Optional[TrustLedger] = None):
        self.trust_ledger = trust_ledger or TrustLedger()
        self.injection_detector = PromptInjectionDetector()
        self.verification_log: List[VerificationReport] = []
    
    def verify(
        self,
        content: str,
        source_url: str,
        check_injection: bool = True,
        require_cross_reference: bool = False
    ) -> VerificationReport:
        """
        Verify data from an external source.
        
        Args:
            content: The data/content to verify
            source_url: URL or identifier of the source
            check_injection: Whether to check for prompt injection
            require_cross_reference: Whether to require cross-referencing
        
        Returns:
            VerificationReport with result and details
        """
        flags = []
        recommendations = []
        manipulation_score = 0.0
        
        # Get source info
        source_info = self.trust_ledger.get_source(source_url)
        
        # Layer 1: Origin Check
        is_trusted_origin = self._check_origin(source_url)
        if not is_trusted_origin:
            if source_info.trust_score < 50:
                flags.append("untrusted_source")
            else:
                flags.append("unverified_source")
        
        # Check if source is blocked
        if source_info.trust_level == TrustLevel.BLOCKED:
            return VerificationReport(
                result=VerificationResult.BLOCKED,
                source_info=source_info,
                trust_score=source_info.trust_score,
                flags=["blocked_source"],
                recommendations=["Source is blocked due to previous violations"]
            )
        
        # Layer 2: Injection Check
        if check_injection:
            is_injection, injection_matches, injection_confidence = self.injection_detector.detect(
                content, source_url
            )
            if is_injection:
                manipulation_score = injection_confidence * 100
                return VerificationReport(
                    result=VerificationResult.INJECTION_DETECTED,
                    source_info=source_info,
                    trust_score=source_info.trust_score,
                    flags=["injection_detected"] + injection_matches,
                    manipulation_score=manipulation_score,
                    recommendations=[
                        "Content contains prompt injection attempt",
                        "Source trust score should be reduced",
                        "Content has been stripped of malicious patterns"
                    ]
                )
            elif injection_matches:
                flags.extend(injection_matches)
                manipulation_score = injection_confidence * 50
        
        # Layer 3: Manipulation Pattern Check
        manip_score, manip_flags = self._check_manipulation_patterns(content)
        manipulation_score = max(manipulation_score, manip_score)
        flags.extend(manip_flags)
        
        # Determine result based on flags
        if manipulation_score >= 70:
            result = VerificationResult.BLOCKED
            recommendations.append("Content shows high manipulation likelihood. Blocking.")
            self.trust_ledger.update_trust(source_url, -40, "manipulation_detected")
        elif manipulation_score >= 40 or len(flags) >= 3:
            result = VerificationResult.FLAGGED
            recommendations.append("Content flagged for review. Proceed with caution.")
            if not is_trusted_origin:
                recommendations.append("Consider cross-referencing with trusted sources.")
        elif flags:
            result = VerificationResult.FLAGGED
            if is_trusted_origin:
                recommendations.append("Minor flags from trusted source. Likely safe.")
            else:
                recommendations.append("Flags detected. Recommend verification.")
        else:
            result = VerificationResult.PASSED
            if is_trusted_origin:
                self.trust_ledger.update_trust(source_url, 5, "clean_verification")
        
        report = VerificationReport(
            result=result,
            source_info=source_info,
            trust_score=source_info.trust_score,
            flags=flags,
            manipulation_score=manipulation_score,
            recommendations=recommendations
        )
        
        self.verification_log.append(report)
        return report
    
    def _check_origin(self, source_url: str) -> bool:
        """Check if source is in trusted allowlist"""
        for trusted in self.TRUSTED_DOMAINS:
            if trusted in source_url.lower():
                return True
        return False
    
    def _check_manipulation_patterns(self, content: str) -> Tuple[float, List[str]]:
        """Check for manipulation patterns in content"""
        flags = []
        score = 0.0
        
        if not content:
            return 0.0, []
        
        content_lower = content.lower()
        
        # Repetition bombing: same phrases repeated many times
        words = content_lower.split()
        if len(words) > 10:
            word_freq = {}
            for word in words:
                if len(word) > 5:  # Only count meaningful words
                    word_freq[word] = word_freq.get(word, 0) + 1
            max_freq = max(word_freq.values()) if word_freq else 0
            if max_freq > len(words) * 0.15:  # Same word more than 15% of content
                flags.append("repetition_bombing")
                score += 20
        
        # Emotional manipulation: extreme sentiment
        emotional_words = [
            "shocking", "outrage", "unbelievable", "scandal",
            "devastating", "catastrophic", "explosive", "bombshell"
        ]
        emotional_count = sum(1 for w in emotional_words if w in content_lower)
        if emotional_count >= 3:
            flags.append("emotional_manipulation")
            score += 15
        
        # Authority spoofing: fake citations
        fake_authority_patterns = [
            r"according to (?:unnamed|anonymous) sources",
            r"experts (?:say|claim|believe) that",
            r"studies (?:have )?show(?:n|s)? that",
        ]
        for pattern in fake_authority_patterns:
            if re.search(pattern, content_lower):
                # Only flag if no actual citation follows
                if not re.search(r"\[\d+\]|\(\d{4}\)|doi:|arxiv:", content_lower):
                    flags.append("unverified_authority_claim")
                    score += 10
                    break
        
        # ALL CAPS manipulation
        caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
        if caps_ratio > 0.5 and len(content) > 50:
            flags.append("excessive_caps")
            score += 10
        
        return score, flags
    
    def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics"""
        if not self.verification_log:
            return {"total": 0}
        
        results = [r.result.value for r in self.verification_log]
        
        return {
            "total": len(self.verification_log),
            "passed": results.count(VerificationResult.PASSED.value),
            "flagged": results.count(VerificationResult.FLAGGED.value),
            "blocked": results.count(VerificationResult.BLOCKED.value),
            "injection_detected": results.count(VerificationResult.INJECTION_DETECTED.value),
            "avg_manipulation_score": sum(r.manipulation_score for r in self.verification_log) / len(self.verification_log),
            "trust_ledger": self.trust_ledger.get_stats()
        }


class DataIntegrityShield:
    """
    Main interface for Daena's Data Integrity protection.
    Combines all verification layers into a single API.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.trust_ledger = TrustLedger(storage_path)
        self.source_verifier = SourceVerifier(self.trust_ledger)
        self.injection_detector = PromptInjectionDetector()
        self.active_flags: List[Dict[str, Any]] = []
        logger.info("Data Integrity Shield initialized")
    
    def verify_data(
        self,
        content: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VerificationReport:
        """
        Main entry point for data verification.
        
        Args:
            content: Data to verify
            source: Source URL or identifier
            metadata: Optional metadata about the data
        
        Returns:
            VerificationReport with verification results
        """
        report = self.source_verifier.verify(content, source)
        
        # If flagged, add to active flags
        if report.result in [VerificationResult.FLAGGED, VerificationResult.CONFLICT]:
            flag_entry = {
                "id": len(self.active_flags) + 1,
                "report": report.to_dict(),
                "content_preview": content[:500] if len(content) > 500 else content,
                "source": source,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "reviewed": False
            }
            self.active_flags.append(flag_entry)
        
        return report
    
    def strip_malicious_content(self, content: str) -> str:
        """Remove detected malicious patterns from content"""
        return self.injection_detector.strip_injections(content)
    
    def get_active_flags(self) -> List[Dict[str, Any]]:
        """Get all active (unreviewed) flags"""
        return [f for f in self.active_flags if not f.get("reviewed", False)]
    
    def review_flag(self, flag_id: int, accept: bool, reviewer: str = "founder") -> bool:
        """Review and resolve a flag"""
        for flag in self.active_flags:
            if flag.get("id") == flag_id:
                flag["reviewed"] = True
                flag["accepted"] = accept
                flag["reviewed_by"] = reviewer
                flag["reviewed_at"] = datetime.utcnow().isoformat()
                
                # Update trust score based on decision
                source = flag.get("source", "")
                if accept:
                    self.trust_ledger.update_trust(source, 10, "manual_approval")
                else:
                    self.trust_ledger.update_trust(source, -30, "manual_rejection")
                
                return True
        return False
    
    def get_blocked_sources(self) -> List[SourceInfo]:
        """Get all blocked sources"""
        return self.trust_ledger.get_blocked_sources()
    
    def unblock_source(self, domain: str, approver: str = "founder") -> bool:
        """Manually unblock a source"""
        source = self.trust_ledger.get_source(domain)
        if source.trust_score < 30:
            self.trust_ledger.update_trust(domain, 35, f"manual_unblock_by_{approver}")
            return True
        return False
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get stats for the Trust Dashboard"""
        return {
            "verification": self.source_verifier.get_verification_stats(),
            "active_flags": len(self.get_active_flags()),
            "injection_attempts": len(self.injection_detector.get_detection_log()),
            "trust_ledger": self.trust_ledger.get_stats()
        }
    
    def get_injection_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent injection attempt log"""
        return self.injection_detector.get_detection_log(limit)


# Global singleton instance
_integrity_shield: Optional[DataIntegrityShield] = None


def get_integrity_shield() -> DataIntegrityShield:
    """Get or create the global Data Integrity Shield instance"""
    global _integrity_shield
    if _integrity_shield is None:
        _integrity_shield = DataIntegrityShield()
    return _integrity_shield


def verify_external_data(content: str, source: str) -> VerificationReport:
    """Convenience function to verify external data"""
    shield = get_integrity_shield()
    return shield.verify_data(content, source)
