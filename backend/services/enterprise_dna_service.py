"""
Enterprise-DNA service for managing Genome, Epigenome, Lineage, and Immune records.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from backend.models.enterprise_dna import (
    Genome, Epigenome, LineageRecord, ThreatSignal, ImmuneEvent,
    ThreatLevel, ImmuneAction
)

logger = logging.getLogger(__name__)


class EnterpriseDNAService:
    """Service for managing Enterprise-DNA records."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the service with storage path."""
        if storage_path is None:
            storage_path = Path(".dna_storage")
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories for each component
        self.genome_path = self.storage_path / "genomes"
        self.epigenome_path = self.storage_path / "epigenomes"
        self.lineage_path = self.storage_path / "lineage"
        self.immune_path = self.storage_path / "immune"
        
        for path in [self.genome_path, self.epigenome_path, self.lineage_path, self.immune_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    # ------------------------------------------------------------------
    # Genome Management
    # ------------------------------------------------------------------
    
    def get_genome(self, agent_id: str) -> Optional[Genome]:
        """Get genome for an agent."""
        genome_file = self.genome_path / f"{agent_id}.json"
        if not genome_file.exists():
            return None
        
        try:
            with open(genome_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Genome.from_dict(data)
        except Exception as e:
            logger.error(f"Error reading genome for {agent_id}: {e}")
            return None
    
    def save_genome(self, genome: Genome) -> bool:
        """Save genome for an agent."""
        try:
            genome.updated_at = datetime.utcnow()
            genome_file = self.genome_path / f"{genome.agent_id}.json"
            with open(genome_file, 'w', encoding='utf-8') as f:
                json.dump(genome.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving genome for {genome.agent_id}: {e}")
            return False
    
    def get_genomes_by_department(self, department: str) -> List[Genome]:
        """Get all genomes for a department."""
        genomes = []
        for genome_file in self.genome_path.glob("*.json"):
            try:
                with open(genome_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                genome = Genome.from_dict(data)
                if genome.department == department:
                    genomes.append(genome)
            except Exception:
                continue
        return genomes
    
    # ------------------------------------------------------------------
    # Epigenome Management
    # ------------------------------------------------------------------
    
    def get_epigenome(self, tenant_id: str) -> Optional[Epigenome]:
        """Get epigenome for a tenant."""
        epigenome_file = self.epigenome_path / f"{tenant_id}.json"
        if not epigenome_file.exists():
            return None
        
        try:
            with open(epigenome_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Epigenome.from_dict(data)
        except Exception as e:
            logger.error(f"Error reading epigenome for {tenant_id}: {e}")
            return None
    
    def save_epigenome(self, epigenome: Epigenome) -> bool:
        """Save epigenome for a tenant."""
        try:
            epigenome.updated_at = datetime.utcnow()
            epigenome_file = self.epigenome_path / f"{epigenome.tenant_id}.json"
            with open(epigenome_file, 'w', encoding='utf-8') as f:
                json.dump(epigenome.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving epigenome for {epigenome.tenant_id}: {e}")
            return False
    
    def get_effective_capabilities(self, tenant_id: str, department: Optional[str] = None) -> Dict[str, Any]:
        """
        Get effective capabilities for a tenant (combining Genome + Epigenome).
        Returns capabilities per department/agent with policy constraints applied.
        """
        epigenome = self.get_epigenome(tenant_id)
        if not epigenome:
            return {}
        
        result = {
            "tenant_id": tenant_id,
            "departments": {}
        }
        
        # Get all genomes (or filter by department)
        if department:
            genomes = self.get_genomes_by_department(department)
        else:
            genomes = []
            for genome_file in self.genome_path.glob("*.json"):
                try:
                    with open(genome_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    genomes.append(Genome.from_dict(data))
                except Exception:
                    continue
        
        # Group by department
        for genome in genomes:
            dept = genome.department
            if dept not in result["departments"]:
                result["departments"][dept] = {
                    "agents": {}
                }
            
            # Apply epigenome constraints (feature flags, ABAC rules)
            effective_capabilities = []
            for cap in genome.capabilities:
                # Check if capability is allowed by feature flags
                feature_key = f"{genome.role}_{cap.skill}"
                if feature_key in epigenome.feature_flags and not epigenome.feature_flags[feature_key]:
                    continue  # Feature disabled
                
                effective_capabilities.append({
                    "skill": cap.skill,
                    "tool": cap.tool,
                    "memory_adapter": cap.memory_adapter,
                    "allowed_actions": cap.allowed_actions,
                    "version": cap.version
                })
            
            result["departments"][dept]["agents"][genome.agent_id] = {
                "role": genome.role,
                "capabilities": effective_capabilities,
                "version": genome.version
            }
        
        return result
    
    # ------------------------------------------------------------------
    # Lineage Management
    # ------------------------------------------------------------------
    
    def record_lineage(
        self,
        object_id: str,
        tenant_id: str,
        promotion_from: str,
        promotion_to: str,
        promoted_by: str,
        nbmf_ledger_txid: str,
        merkle_parent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[LineageRecord]:
        """Record a lineage entry for a memory promotion."""
        try:
            # Compute merkle root if we have a parent
            merkle_root = None
            if merkle_parent:
                # Get parent record
                parent_file = self.lineage_path / f"{merkle_parent}.json"
                if parent_file.exists():
                    with open(parent_file, 'r', encoding='utf-8') as f:
                        parent_data = json.load(f)
                    # Build merkle chain (simplified - in production use proper Merkle tree)
                    merkle_root = parent_data.get("merkle_root") or merkle_parent
            
            lineage = LineageRecord(
                object_id=object_id,
                tenant_id=tenant_id,
                promotion_from=promotion_from,
                promotion_to=promotion_to,
                promoted_by=promoted_by,
                promoted_at=datetime.utcnow(),
                nbmf_ledger_txid=nbmf_ledger_txid,
                merkle_root=merkle_root,
                merkle_parent=merkle_parent,
                metadata=metadata or {}
            )
            
            # Save lineage record
            lineage_hash = lineage.compute_hash()
            lineage_file = self.lineage_path / f"{lineage_hash}.json"
            with open(lineage_file, 'w', encoding='utf-8') as f:
                json.dump(lineage.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Also index by object_id for quick lookup
            object_index_file = self.lineage_path / f"index_{object_id}.jsonl"
            with open(object_index_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"hash": lineage_hash, "timestamp": lineage.promoted_at.isoformat()}) + "\n")
            
            return lineage
        except Exception as e:
            logger.error(f"Error recording lineage for {object_id}: {e}")
            return None
    
    def get_lineage_chain(self, object_id: str) -> List[LineageRecord]:
        """Get full lineage chain for an object."""
        chain = []
        index_file = self.lineage_path / f"index_{object_id}.jsonl"
        
        if not index_file.exists():
            return chain
        
        try:
            # Read all lineage entries for this object
            with open(index_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    lineage_hash = entry["hash"]
                    lineage_file = self.lineage_path / f"{lineage_hash}.json"
                    if lineage_file.exists():
                        with open(lineage_file, 'r', encoding='utf-8') as lf:
                            data = json.load(lf)
                        chain.append(LineageRecord.from_dict(data))
            
            # Sort by promotion time
            chain.sort(key=lambda x: x.promoted_at)
            return chain
        except Exception as e:
            logger.error(f"Error reading lineage chain for {object_id}: {e}")
            return []
    
    def get_lineage_by_txid(self, nbmf_ledger_txid: str) -> Optional[LineageRecord]:
        """Get lineage record by NBMF ledger transaction ID."""
        # Search all lineage files (could be optimized with an index)
        for lineage_file in self.lineage_path.glob("*.json"):
            if lineage_file.name.startswith("index_"):
                continue
            try:
                with open(lineage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("nbmf_ledger_txid") == nbmf_ledger_txid:
                    return LineageRecord.from_dict(data)
            except Exception:
                continue
        return None
    
    # ------------------------------------------------------------------
    # Immune System Management
    # ------------------------------------------------------------------
    
    def record_immune_event(
        self,
        tenant_id: str,
        threat_signals: List[ThreatSignal],
        trust_score_adjustment: float = 0.0,
        quarantine_required: bool = False,
        quorum_required: bool = False,
        rollback_required: bool = False
    ) -> Optional[ImmuneEvent]:
        """Record an immune event."""
        try:
            event_id = str(uuid.uuid4())
            event = ImmuneEvent(
                event_id=event_id,
                tenant_id=tenant_id,
                threat_signals=threat_signals,
                trust_score_adjustment=trust_score_adjustment,
                quarantine_required=quarantine_required,
                quorum_required=quorum_required,
                rollback_required=rollback_required
            )
            
            # Save event
            event_file = self.immune_path / f"{event_id}.json"
            with open(event_file, 'w', encoding='utf-8') as f:
                json.dump(event.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Record Prometheus metrics
            try:
                from memory_service.dna_metrics import (
                    record_immune_event, record_quarantine, record_quorum
                )
                for signal in threat_signals:
                    record_immune_event(
                        tenant_id=tenant_id,
                        threat_type=signal.threat_type,
                        threat_level=signal.threat_level.value
                    )
                if quarantine_required:
                    record_quarantine(tenant_id=tenant_id, reason="immune_event")
                if quorum_required:
                    record_quorum(tenant_id=tenant_id)
            except ImportError:
                pass  # Metrics not available
            
            # Index by tenant
            tenant_index_file = self.immune_path / f"tenant_{tenant_id}.jsonl"
            with open(tenant_index_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"event_id": event_id, "timestamp": event.created_at.isoformat()}) + "\n")
            
            # Emit real-time event for frontend
            try:
                from backend.routes.events import emit
                emit("dna_immune_event", {
                    "tenant_id": tenant_id,
                    "event_id": event_id,
                    "quarantine_required": quarantine_required,
                    "quorum_required": quorum_required,
                    "threat_count": len(threat_signals)
                })
            except ImportError:
                pass  # Events system not available
            
            return event
        except Exception as e:
            logger.error(f"Error recording immune event: {e}")
            return None
    
    def get_immune_events(self, tenant_id: str, limit: int = 100) -> List[ImmuneEvent]:
        """Get recent immune events for a tenant."""
        events = []
        tenant_index_file = self.immune_path / f"tenant_{tenant_id}.jsonl"
        
        if not tenant_index_file.exists():
            return events
        
        try:
            # Read index
            with open(tenant_index_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Get most recent entries
            for line in lines[-limit:]:
                if not line.strip():
                    continue
                entry = json.loads(line)
                event_id = entry["event_id"]
                event_file = self.immune_path / f"{event_id}.json"
                if event_file.exists():
                    with open(event_file, 'r', encoding='utf-8') as ef:
                        data = json.load(ef)
                    events.append(ImmuneEvent.from_dict(data))
            
            # Sort by creation time (most recent first)
            events.sort(key=lambda x: x.created_at, reverse=True)
            return events
        except Exception as e:
            logger.error(f"Error reading immune events for {tenant_id}: {e}")
            return []


# Global singleton instance
_dna_service: Optional[EnterpriseDNAService] = None


def get_dna_service() -> EnterpriseDNAService:
    """Get or create the global DNA service instance."""
    global _dna_service
    if _dna_service is None:
        _dna_service = EnterpriseDNAService()
    return _dna_service

