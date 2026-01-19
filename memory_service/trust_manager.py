"""
Advanced trust & divergence scoring utilities for NBMF promotion decisions.
Includes deterministic trust graph for inter-record/agent trust relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from collections import defaultdict

from .simhash_neardup import near_duplicate


@dataclass
class TrustAssessment:
    cls: str
    score: float
    divergence: float
    consensus: float
    safety: float
    issues: List[str]
    details: Dict[str, Any]
    promote: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cls": self.cls,
            "score": self.score,
            "divergence": self.divergence,
            "consensus": self.consensus,
            "safety": self.safety,
            "issues": self.issues,
            "details": self.details,
            "promote": self.promote,
        }


def _sequence_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _dict_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, List[str]]:
    if not a and not b:
        return 1.0, []
    keys_a = set(a.keys())
    keys_b = set(b.keys())
    shared = keys_a & keys_b
    total = keys_a | keys_b
    key_overlap = len(shared) / len(total) if total else 1.0
    issues: List[str] = []
    if keys_a - keys_b:
        issues.append(f"missing_keys_in_candidate:{sorted(keys_a - keys_b)}")
    if keys_b - keys_a:
        issues.append(f"new_keys_in_candidate:{sorted(keys_b - keys_a)}")
    value_scores: List[float] = []
    for key in shared:
        if a[key] == b[key]:
            value_scores.append(1.0)
            continue
        diff = _sequence_similarity(str(a[key]), str(b[key]))
        value_scores.append(diff)
        if diff < 0.8:
            issues.append(f"value_shift:{key}")
    value_similarity = sum(value_scores) / len(value_scores) if value_scores else 1.0
    similarity = (key_overlap + value_similarity) / 2
    return similarity, issues


def _list_similarity(a: List[Any], b: List[Any]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    set_a = set(map(str, a))
    set_b = set(map(str, b))
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 1.0


class TrustManager:
    def __init__(
        self,
        *,
        min_consensus: int = 2,
        max_halluc_score: float = 0.35,
        promote_threshold: float = 0.35,
        divergence_threshold: float = 0.3,
        critical_abort_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self.min_consensus = min_consensus
        self.max_halluc_score = max_halluc_score
        self.promote_threshold = promote_threshold
        self.divergence_threshold = divergence_threshold
        self.critical_abort_thresholds = critical_abort_thresholds or {
            "legal": 0.2,
            "finance": 0.25,
            "pii": 0.2,
        }

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------
    def compute_trust(
        self,
        candidate_texts: Iterable[str],
        hallucination_scores: Iterable[float],
    ) -> float:
        texts: List[str] = [t for t in candidate_texts if t]
        scores: List[float] = [max(0.0, min(1.0, s)) for s in hallucination_scores]
        if not texts:
            return 0.0

        agree = 0
        total = 0
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                total += 1
                if near_duplicate(texts[i], texts[j]):
                    agree += 1
        consensus = agree / total if total else 1.0
        safety = 1.0 - min(1.0, sum(scores) / max(1, len(scores)))
        return max(0.0, min(1.0, 0.6 * consensus + 0.4 * safety))

    def assess(
        self,
        cls: str,
        candidate: Any,
        reference: Optional[Any] = None,
        *,
        hallucination_scores: Optional[Iterable[float]] = None,
        related_texts: Optional[Iterable[str]] = None,
    ) -> TrustAssessment:
        scores = [max(0.0, min(1.0, s)) for s in (hallucination_scores or [])]
        safety = 1.0 - min(1.0, sum(scores) / max(1, len(scores))) if scores else 1.0

        consensus_texts: List[str] = []
        if related_texts:
            consensus_texts.extend(str(t) for t in related_texts if t)
        if reference is not None:
            consensus_texts.append(str(reference))
        consensus_texts.append(str(candidate))
        consensus = self.compute_trust(consensus_texts, [0.0] * len(consensus_texts)) if consensus_texts else 1.0

        divergence, issues = self._divergence(cls, candidate, reference)
        blended = max(0.0, min(1.0, 0.5 * (1.0 - divergence) + 0.3 * consensus + 0.2 * safety))
        promote = blended >= self.promote_threshold and divergence <= self.divergence_threshold
        return TrustAssessment(
            cls=cls,
            score=blended,
            divergence=divergence,
            consensus=consensus,
            safety=safety,
            issues=issues,
            details={"has_reference": reference is not None},
            promote=promote,
        )

    def _divergence(self, cls: str, candidate: Any, reference: Optional[Any]) -> Tuple[float, List[str]]:
        if reference is None:
            return 0.0, []
        issues: List[str]
        similarity: float
        if isinstance(candidate, dict) and isinstance(reference, dict):
            similarity, issues = _dict_similarity(candidate, reference)
        elif isinstance(candidate, list) and isinstance(reference, list):
            similarity = _list_similarity(candidate, reference)
            issues = [] if similarity >= 0.8 else ["list_delta"]
        else:
            similarity = _sequence_similarity(str(candidate), str(reference))
            issues = [] if similarity >= 0.8 else ["text_delta"]
        divergence = max(0.0, min(1.0, 1.0 - similarity))
        if divergence < 0.05:
            issues = []
        return divergence, issues

    # ------------------------------------------------------------------
    # Policy helpers
    # ------------------------------------------------------------------
    def should_promote(self, value: Union[TrustAssessment, float]) -> bool:
        if isinstance(value, TrustAssessment):
            return value.promote
        return value >= self.promote_threshold

    def requires_abort(self, cls: str, divergence: float) -> bool:
        threshold = self.critical_abort_thresholds.get(cls)
        return threshold is not None and divergence >= threshold


class TrustGraph:
    """
    Deterministic trust graph for inter-record/agent trust relationships.
    
    Nodes represent records or agents, edges represent trust relationships.
    Trust scores propagate through the graph with decay.
    """
    
    def __init__(self, decay_factor: float = 0.8):
        """
        Initialize trust graph.
        
        Args:
            decay_factor: Trust decay per hop (0.8 = 80% trust after 1 hop)
        """
        self.decay_factor = decay_factor
        self.nodes: Dict[str, Dict[str, Any]] = {}  # node_id -> {type, metadata}
        self.edges: Dict[str, Dict[str, float]] = defaultdict(dict)  # node_id -> {target_id: trust_score}
        self.reverse_edges: Dict[str, Dict[str, float]] = defaultdict(dict)  # target_id -> {node_id: trust_score}
    
    def add_node(self, node_id: str, node_type: str = "record", metadata: Optional[Dict[str, Any]] = None):
        """Add a node to the trust graph."""
        self.nodes[node_id] = {
            "type": node_type,
            "metadata": metadata or {}
        }
    
    def add_edge(self, source_id: str, target_id: str, trust_score: float):
        """
        Add a trust edge from source to target.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            trust_score: Trust score (0.0 to 1.0)
        """
        if source_id not in self.nodes:
            self.add_node(source_id)
        if target_id not in self.nodes:
            self.add_node(target_id)
        
        trust_score = max(0.0, min(1.0, trust_score))
        self.edges[source_id][target_id] = trust_score
        self.reverse_edges[target_id][source_id] = trust_score
    
    def get_trust(self, source_id: str, target_id: str, max_hops: int = 3) -> float:
        """
        Get trust score from source to target, with propagation.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            max_hops: Maximum number of hops for trust propagation
        
        Returns:
            Trust score (0.0 to 1.0)
        """
        if source_id == target_id:
            return 1.0
        
        # Direct trust
        if target_id in self.edges.get(source_id, {}):
            return self.edges[source_id][target_id]
        
        # Propagated trust (BFS with decay)
        if max_hops <= 0:
            return 0.0
        
        visited = {source_id}
        queue = [(source_id, 1.0, 0)]  # (node_id, current_trust, hops)
        
        while queue:
            current_id, current_trust, hops = queue.pop(0)
            
            if hops >= max_hops:
                continue
            
            for neighbor_id, edge_trust in self.edges.get(current_id, {}).items():
                if neighbor_id in visited:
                    continue
                
                visited.add(neighbor_id)
                propagated_trust = current_trust * edge_trust * (self.decay_factor ** hops)
                
                if neighbor_id == target_id:
                    return propagated_trust
                
                queue.append((neighbor_id, propagated_trust, hops + 1))
        
        return 0.0
    
    def get_trusted_neighbors(self, node_id: str, min_trust: float = 0.5) -> List[Tuple[str, float]]:
        """
        Get all neighbors with trust score >= min_trust.
        
        Returns:
            List of (neighbor_id, trust_score) tuples
        """
        neighbors = self.edges.get(node_id, {})
        return [(nid, score) for nid, score in neighbors.items() if score >= min_trust]
    
    def propagate_trust(self, source_id: str, initial_trust: float, max_hops: int = 2) -> Dict[str, float]:
        """
        Propagate trust from a source node to all reachable nodes.
        
        Returns:
            Dict of {node_id: propagated_trust_score}
        """
        propagated: Dict[str, float] = {}
        visited = {source_id}
        queue = [(source_id, initial_trust, 0)]
        
        while queue:
            current_id, current_trust, hops = queue.pop(0)
            
            if hops > max_hops:
                continue
            
            propagated[current_id] = max(propagated.get(current_id, 0.0), current_trust)
            
            for neighbor_id, edge_trust in self.edges.get(current_id, {}).items():
                if neighbor_id in visited:
                    continue
                
                visited.add(neighbor_id)
                propagated_trust = current_trust * edge_trust * (self.decay_factor ** hops)
                queue.append((neighbor_id, propagated_trust, hops + 1))
        
        return propagated
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize trust graph to dictionary."""
        return {
            "nodes": self.nodes,
            "edges": dict(self.edges),
            "decay_factor": self.decay_factor
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrustGraph":
        """Deserialize trust graph from dictionary."""
        graph = cls(decay_factor=data.get("decay_factor", 0.8))
        graph.nodes = data.get("nodes", {})
        graph.edges = defaultdict(dict, data.get("edges", {}))
        
        # Rebuild reverse edges
        for source_id, targets in graph.edges.items():
            for target_id, trust_score in targets.items():
                graph.reverse_edges[target_id][source_id] = trust_score
        
        return graph


# Global trust graph instance (optional, can be per-router)
_global_trust_graph: Optional[TrustGraph] = None


def get_trust_graph() -> TrustGraph:
    """Get or create global trust graph instance."""
    global _global_trust_graph
    if _global_trust_graph is None:
        _global_trust_graph = TrustGraph()
    return _global_trust_graph


