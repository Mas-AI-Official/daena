"""
Guardian Loop - Runtime self-healing loop for Daena

This is the core runtime component that:
1. Collects signals (exceptions, failures, timeouts)
2. Normalizes them into incidents
3. Decides action (observe/auto-fix/escalate)
4. Applies safe fixes with two-phase commit
5. Enforces rate limits and deny-lists

Integrates with existing Daena monitoring and error handling.
"""

import asyncio
import logging
import os
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import deque
import json

from . import (
    QA_GUARDIAN_ENABLED, QA_GUARDIAN_KILL_SWITCH, QA_GUARDIAN_AUTO_FIX,
    QA_GUARDIAN_RATE_LIMIT, Severity, RiskLevel, IncidentStatus, ActionType
)
from .schemas.incident import Incident, IncidentCreate, Evidence
from .decision_engine import DecisionEngine

logger = logging.getLogger("qa_guardian.loop")


class RateLimiter:
    """Simple sliding window rate limiter"""
    
    def __init__(self, max_actions: int, window_seconds: int = 3600):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self.actions: deque = deque()
    
    def can_proceed(self) -> bool:
        """Check if action is allowed within rate limit"""
        self._cleanup_old()
        return len(self.actions) < self.max_actions
    
    def record_action(self):
        """Record an action"""
        self.actions.append(time.time())
    
    def _cleanup_old(self):
        """Remove actions outside the window"""
        cutoff = time.time() - self.window_seconds
        while self.actions and self.actions[0] < cutoff:
            self.actions.popleft()
    
    def remaining(self) -> int:
        """Get remaining allowed actions"""
        self._cleanup_old()
        return max(0, self.max_actions - len(self.actions))


class IncidentStore:
    """In-memory incident store with persistence capability"""
    
    def __init__(self, persist_path: Optional[str] = None):
        self.incidents: Dict[str, Incident] = {}
        self.idempotency_keys: Dict[str, str] = {}  # key -> incident_id
        self.persist_path = persist_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "qa_incidents.json"
        )
        self._load()
    
    def _load(self):
        """Load incidents from disk"""
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, 'r') as f:
                    data = json.load(f)
                    for inc_data in data.get("incidents", []):
                        inc = Incident(**inc_data)
                        self.incidents[inc.incident_id] = inc
                        self.idempotency_keys[inc.idempotency_key] = inc.incident_id
                logger.info(f"Loaded {len(self.incidents)} incidents from disk")
        except Exception as e:
            logger.warning(f"Could not load incidents: {e}")
    
    def _save(self):
        """Persist incidents to disk"""
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            data = {
                "incidents": [inc.model_dump(mode='json') for inc in self.incidents.values()],
                "saved_at": datetime.utcnow().isoformat()
            }
            with open(self.persist_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save incidents: {e}")
    
    def add(self, incident: Incident) -> bool:
        """Add incident if not duplicate (idempotent)"""
        if incident.idempotency_key in self.idempotency_keys:
            logger.info(f"Duplicate incident detected: {incident.idempotency_key}")
            return False
        
        self.incidents[incident.incident_id] = incident
        self.idempotency_keys[incident.idempotency_key] = incident.incident_id
        self._save()
        return True
    
    def get(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)
    
    def update(self, incident: Incident):
        incident.updated_at = datetime.utcnow()
        self.incidents[incident.incident_id] = incident
        self._save()
    
    def get_open(self) -> List[Incident]:
        return [inc for inc in self.incidents.values() 
                if inc.status not in [IncidentStatus.CLOSED, IncidentStatus.COMMITTED]]
    
    def get_by_status(self, status: str) -> List[Incident]:
        return [inc for inc in self.incidents.values() if inc.status == status]
    
    def get_recent(self, hours: int = 24) -> List[Incident]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [inc for inc in self.incidents.values() if inc.created_at > cutoff]


class SignalCollector:
    """Collects runtime signals from various sources"""
    
    def __init__(self):
        self.handlers: List[Callable] = []
        self._exception_hook_installed = False
    
    def install_exception_hook(self):
        """Install global exception handler to capture unhandled exceptions"""
        if self._exception_hook_installed:
            return
        
        import sys
        original_hook = sys.excepthook
        
        def qa_exception_hook(exc_type, exc_value, exc_tb):
            # Capture for QA Guardian
            self._on_exception(exc_type, exc_value, exc_tb)
            # Call original
            original_hook(exc_type, exc_value, exc_tb)
        
        sys.excepthook = qa_exception_hook
        self._exception_hook_installed = True
        logger.info("QA Guardian exception hook installed")
    
    def _on_exception(self, exc_type, exc_value, exc_tb):
        """Handle captured exception"""
        for handler in self.handlers:
            try:
                handler({
                    "type": "exception",
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_value),
                    "stack_trace": "".join(traceback.format_tb(exc_tb)),
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                logger.error(f"Signal handler error: {e}")
    
    def add_handler(self, handler: Callable):
        """Add a signal handler"""
        self.handlers.append(handler)
    
    def emit(self, signal: Dict[str, Any]):
        """Manually emit a signal"""
        for handler in self.handlers:
            try:
                handler(signal)
            except Exception as e:
                logger.error(f"Signal handler error: {e}")


class GuardianLoop:
    """
    Main Guardian Loop - the runtime self-heal system
    
    Runs continuously collecting signals, creating incidents,
    and applying safe fixes within the boundaries defined by the Charter.
    """
    
    def __init__(self):
        self.enabled = QA_GUARDIAN_ENABLED
        self.kill_switch = QA_GUARDIAN_KILL_SWITCH
        self.auto_fix_enabled = QA_GUARDIAN_AUTO_FIX
        
        self.incident_store = IncidentStore()
        self.signal_collector = SignalCollector()
        self.decision_engine = DecisionEngine()
        self.rate_limiter = RateLimiter(max_actions=QA_GUARDIAN_RATE_LIMIT)
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._signal_queue: asyncio.Queue = asyncio.Queue()
        
        # Register signal handler
        self.signal_collector.add_handler(self._on_signal)
        
        # Audit log path
        self.audit_log_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "logs", "qa_guardian_audit.jsonl"
        )
    
    def _check_enabled(self) -> bool:
        """Check if guardian should run (respects kill switch)"""
        # Re-read environment in case it changed
        kill_switch = os.getenv("QA_GUARDIAN_KILL_SWITCH", "false").lower() == "true"
        enabled = os.getenv("QA_GUARDIAN_ENABLED", "false").lower() == "true"
        return enabled and not kill_switch
    
    def _on_signal(self, signal: Dict[str, Any]):
        """Handle incoming signal (non-blocking)"""
        try:
            self._signal_queue.put_nowait(signal)
        except asyncio.QueueFull:
            logger.warning("Signal queue full, dropping signal")
    
    async def start(self):
        """Start the guardian loop"""
        if self._running:
            return
        
        if not self._check_enabled():
            logger.info("QA Guardian is disabled, not starting loop")
            return
        
        self._running = True
        self.signal_collector.install_exception_hook()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("QA Guardian Loop started")
        self._audit_log("guardian_started", {"timestamp": datetime.utcnow().isoformat()})
    
    async def stop(self):
        """Stop the guardian loop"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("QA Guardian Loop stopped")
        self._audit_log("guardian_stopped", {"timestamp": datetime.utcnow().isoformat()})
    
    async def _run_loop(self):
        """Main loop - process signals continuously"""
        while self._running:
            try:
                # Check kill switch
                if not self._check_enabled():
                    logger.info("Kill switch activated or guardian disabled")
                    await asyncio.sleep(10)
                    continue
                
                # Wait for signal with timeout
                try:
                    signal = await asyncio.wait_for(
                        self._signal_queue.get(), 
                        timeout=5.0
                    )
                    await self._process_signal(signal)
                except asyncio.TimeoutError:
                    # No signal, check for pending work
                    await self._check_pending_incidents()
                
            except Exception as e:
                logger.error(f"Guardian loop error: {e}")
                await asyncio.sleep(1)
    
    async def _process_signal(self, signal: Dict[str, Any]):
        """Process an incoming signal"""
        try:
            # Normalize to incident
            incident = await self._normalize_signal(signal)
            if not incident:
                return
            
            # Add to store (idempotent)
            if not self.incident_store.add(incident):
                logger.debug(f"Duplicate signal, skipping: {incident.summary}")
                return
            
            self._audit_log("incident_created", {
                "incident_id": incident.incident_id,
                "severity": incident.severity,
                "category": incident.category,
                "summary": incident.summary
            })
            
            # Get decision
            decision = self.decision_engine.decide(incident)
            
            self._audit_log("decision_made", {
                "incident_id": incident.incident_id,
                "action": decision.action,
                "reasoning": decision.reasoning
            })
            
            # Execute decision
            await self._execute_decision(incident, decision)
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            self._audit_log("signal_processing_error", {
                "error": str(e),
                "signal_type": signal.get("type")
            })
    
    async def _normalize_signal(self, signal: Dict[str, Any]) -> Optional[Incident]:
        """Convert raw signal to normalized Incident"""
        signal_type = signal.get("type", "unknown")
        
        if signal_type == "exception":
            create = IncidentCreate(
                severity=self._classify_severity(signal),
                subsystem=self._extract_subsystem(signal),
                category=self._classify_category(signal),
                source="runtime",
                summary=f"{signal.get('error_type', 'Error')}: {signal.get('error_message', 'Unknown')[:100]}",
                description=signal.get('error_message', 'No description'),
                evidence=[
                    Evidence(
                        type="stack_trace",
                        content=signal.get('stack_trace', 'No stack trace'),
                        timestamp=signal.get('timestamp')
                    )
                ]
            )
            risk_level = self.decision_engine.assess_risk(create)
            return Incident.from_create(create, risk_level)
        
        elif signal_type == "task_failure":
            create = IncidentCreate(
                severity="P2",
                subsystem="task_engine",
                category="workflow",
                source="runtime",
                summary=f"Task failed: {signal.get('task_id', 'unknown')}",
                description=signal.get('error_message', 'Task execution failed'),
                affected_agent=signal.get('agent_id')
            )
            return Incident.from_create(create)
        
        elif signal_type == "timeout":
            create = IncidentCreate(
                severity="P3",
                subsystem=signal.get('subsystem', 'unknown'),
                category="config",
                source="runtime",
                summary=f"Timeout in {signal.get('operation', 'unknown operation')}",
                description=f"Operation timed out after {signal.get('timeout_seconds', '?')}s"
            )
            return Incident.from_create(create)
        
        elif signal_type == "tool_call_failure":
            create = IncidentCreate(
                severity="P3",
                subsystem="tools",
                category="bug",
                source="runtime",
                summary=f"Tool call failed: {signal.get('tool_name', 'unknown')}",
                description=signal.get('error_message', 'Tool execution failed'),
                evidence=[
                    Evidence(
                        type="tool_call",
                        content=json.dumps(signal.get('tool_input', {}), default=str),
                        timestamp=signal.get('timestamp')
                    )
                ]
            )
            return Incident.from_create(create)
        
        # Unknown signal type - log but don't create incident
        logger.debug(f"Unknown signal type: {signal_type}")
        return None
    
    def _classify_severity(self, signal: Dict[str, Any]) -> str:
        """Classify severity based on signal content"""
        error_type = signal.get('error_type', '').lower()
        error_msg = signal.get('error_message', '').lower()
        
        # P0: Critical
        if any(kw in error_msg for kw in ['database corruption', 'data loss', 'security breach']):
            return Severity.P0
        
        # P1: High
        if any(kw in error_type for kw in ['databaseerror', 'connectionerror', 'authenticationerror']):
            return Severity.P1
        
        # P2: Medium
        if any(kw in error_type for kw in ['timeout', 'httperror', 'apierror']):
            return Severity.P2
        
        # P3: Low
        if any(kw in error_type for kw in ['validationerror', 'valueerror', 'typeerror']):
            return Severity.P3
        
        # Default to P3
        return Severity.P3
    
    def _classify_category(self, signal: Dict[str, Any]) -> str:
        """Classify category based on signal content"""
        error_type = signal.get('error_type', '').lower()
        error_msg = signal.get('error_message', '').lower()
        stack = signal.get('stack_trace', '').lower()
        
        if 'security' in error_msg or 'auth' in error_type:
            return 'security'
        if 'config' in error_msg or 'environment' in error_msg or 'setting' in error_msg:
            return 'config'
        if 'import' in error_type or 'modulenotfound' in error_type or 'dependency' in error_msg:
            return 'dependency'
        if 'database' in error_msg or 'sql' in error_type:
            return 'data'
        if 'workflow' in stack or 'task' in stack:
            return 'workflow'
        if 'agent' in stack and 'conflict' in error_msg:
            return 'agent_conflict'
        
        return 'bug'
    
    def _extract_subsystem(self, signal: Dict[str, Any]) -> str:
        """Extract subsystem from stack trace"""
        stack = signal.get('stack_trace', '')
        
        # Look for known subsystems in stack
        if 'backend/routes/' in stack:
            return 'api'
        if 'backend/services/' in stack:
            return 'services'
        if 'backend/database' in stack:
            return 'database'
        if 'qa_guardian' in stack:
            return 'qa_guardian'
        if 'frontend' in stack:
            return 'frontend'
        if 'Core/' in stack:
            return 'core'
        
        return 'unknown'
    
    async def _execute_decision(self, incident: Incident, decision):
        """Execute the decision from the decision engine"""
        incident.status = IncidentStatus.TRIAGING
        self.incident_store.update(incident)
        
        if decision.action == ActionType.OBSERVE:
            # Just log and monitor
            incident.status = IncidentStatus.OPEN
            incident.proposed_actions = [{"action_type": "observe", "description": decision.reasoning}]
            self.incident_store.update(incident)
            logger.info(f"Observing incident {incident.incident_id}: {decision.reasoning}")
        
        elif decision.action == ActionType.ESCALATE:
            # Mark for escalation
            incident.status = IncidentStatus.AWAITING_APPROVAL
            incident.approval_required = True
            incident.proposed_actions = [{"action_type": "escalate", "description": decision.reasoning}]
            self.incident_store.update(incident)
            logger.warning(f"Escalating incident {incident.incident_id}: {decision.reasoning}")
            # TODO: Send notification to founder
        
        elif decision.action == ActionType.QUARANTINE:
            # Quarantine affected agent
            incident.status = IncidentStatus.PROPOSED
            incident.proposed_actions = [{"action_type": "quarantine", "description": decision.reasoning}]
            self.incident_store.update(incident)
            logger.warning(f"Quarantine recommended for {incident.affected_agent}")
            # TODO: Implement actual quarantine
        
        elif decision.action == ActionType.AUTO_FIX:
            # Check rate limit
            if not self.rate_limiter.can_proceed():
                logger.warning("Rate limit exceeded, deferring auto-fix")
                incident.status = IncidentStatus.OPEN
                self.incident_store.update(incident)
                return
            
            # Check if auto-fix is enabled
            if not self.auto_fix_enabled:
                logger.info("Auto-fix disabled, observing instead")
                incident.status = IncidentStatus.OPEN
                self.incident_store.update(incident)
                return
            
            # Generate and apply fix (placeholder - to be implemented with qa_auto_fix_agent)
            incident.status = IncidentStatus.PROPOSED
            self.rate_limiter.record_action()
            self.incident_store.update(incident)
            logger.info(f"Auto-fix proposed for {incident.incident_id}")
    
    async def _check_pending_incidents(self):
        """Check for incidents that need attention"""
        # Get incidents awaiting approval
        awaiting = self.incident_store.get_by_status(IncidentStatus.AWAITING_APPROVAL)
        if awaiting:
            logger.debug(f"{len(awaiting)} incidents awaiting approval")
        
        # Get open incidents older than 1 hour
        open_incidents = self.incident_store.get_by_status(IncidentStatus.OPEN)
        for inc in open_incidents:
            age = datetime.utcnow() - inc.created_at
            if age > timedelta(hours=1) and inc.severity in [Severity.P0, Severity.P1]:
                logger.warning(f"Critical incident {inc.incident_id} unresolved for {age}")
    
    def _audit_log(self, action: str, details: Dict[str, Any]):
        """Write to audit log"""
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "service": "qa_guardian",
                "action": action,
                **details
            }
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")
    
    # === Public API for manual signal injection ===
    
    def report_error(self, error_type: str, error_message: str, 
                     stack_trace: str = None, subsystem: str = None):
        """Manually report an error to the guardian"""
        self.signal_collector.emit({
            "type": "exception",
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace or "",
            "subsystem": subsystem,
            "timestamp": datetime.utcnow()
        })
    
    def report_task_failure(self, task_id: str, agent_id: str = None, 
                           error_message: str = None):
        """Report a task failure"""
        self.signal_collector.emit({
            "type": "task_failure",
            "task_id": task_id,
            "agent_id": agent_id,
            "error_message": error_message,
            "timestamp": datetime.utcnow()
        })
    
    def report_timeout(self, operation: str, timeout_seconds: int, 
                       subsystem: str = None):
        """Report a timeout"""
        self.signal_collector.emit({
            "type": "timeout",
            "operation": operation,
            "timeout_seconds": timeout_seconds,
            "subsystem": subsystem,
            "timestamp": datetime.utcnow()
        })
    
    def report_tool_failure(self, tool_name: str, tool_input: Dict = None,
                           error_message: str = None):
        """Report a tool call failure"""
        self.signal_collector.emit({
            "type": "tool_call_failure",
            "tool_name": tool_name,
            "tool_input": tool_input or {},
            "error_message": error_message,
            "timestamp": datetime.utcnow()
        })
    
    def get_status(self) -> Dict[str, Any]:
        """Get guardian status"""
        return {
            "enabled": self._check_enabled(),
            "running": self._running,
            "auto_fix_enabled": self.auto_fix_enabled,
            "rate_limit_remaining": self.rate_limiter.remaining(),
            "open_incidents": len(self.incident_store.get_open()),
            "total_incidents_24h": len(self.incident_store.get_recent(24))
        }


# Singleton instance
_guardian_loop: Optional[GuardianLoop] = None

def get_guardian_loop() -> GuardianLoop:
    """Get or create the singleton guardian loop"""
    global _guardian_loop
    if _guardian_loop is None:
        _guardian_loop = GuardianLoop()
    return _guardian_loop
