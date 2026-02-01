"""
Research Agent — Multi-Source Knowledge Gathering with Trust Scoring

Implements MoltBot's research capability for:
- Web search with trust verification
- Local knowledge base queries
- Multi-source deduplication
- Findings stored in NBMF memory

Integrates with:
- IntegrityShield for trust scoring
- NBMF Memory for persistence
- Learning Loop for outcome tracking
"""

import logging
import hashlib
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Types of knowledge sources."""
    WEB = "web"
    LOCAL_KB = "local_kb"
    DOCUMENT = "document"
    MCP_TOOL = "mcp_tool"
    AGENT_MEMORY = "agent_memory"


@dataclass
class ResearchFinding:
    """A single research finding with source and trust info."""
    finding_id: str
    query: str
    content: str
    source_type: SourceType
    source_url: Optional[str] = None
    source_name: str = ""
    trust_score: float = 0.0
    relevance_score: float = 0.0
    verified: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "query": self.query,
            "content": self.content,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "trust_score": self.trust_score,
            "relevance_score": self.relevance_score,
            "verified": self.verified,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ResearchResult:
    """Aggregated research result from multiple sources."""
    query: str
    findings: List[ResearchFinding] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    sources_searched: int = 0
    total_findings: int = 0
    deduplicated_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "summary": self.summary,
            "confidence": self.confidence,
            "sources_searched": self.sources_searched,
            "total_findings": self.total_findings,
            "deduplicated_count": self.deduplicated_count,
            "findings": [f.to_dict() for f in self.findings],
            "timestamp": self.timestamp.isoformat()
        }


class ResearchAgent:
    """
    Research agent for multi-source knowledge gathering.
    
    Implements:
    - Web search via configured search provider
    - Local knowledge base queries
    - Trust scoring via IntegrityShield
    - Deduplication of findings
    - Storage in NBMF memory
    """
    
    def __init__(self):
        self.search_provider = "web"  # Can be "web", "local", "hybrid"
        self.max_results_per_source = 10
        self.min_trust_threshold = 0.3
        self._finding_hashes: set = set()  # For deduplication
        self._search_history: List[Dict] = []
        logger.info("🔬 Research Agent initialized")
    
    async def research(
        self,
        query: str,
        sources: Optional[List[SourceType]] = None,
        max_results: int = 10,
        verify_facts: bool = True
    ) -> ResearchResult:
        """
        Execute a research query across multiple sources.
        
        Args:
            query: The research query
            sources: List of source types to search (default: all)
            max_results: Maximum total findings to return
            verify_facts: Whether to verify findings via IntegrityShield
            
        Returns:
            ResearchResult with aggregated findings
        """
        if sources is None:
            sources = [SourceType.WEB, SourceType.LOCAL_KB, SourceType.AGENT_MEMORY]
        
        logger.info(f"🔍 Research query: {query[:100]}... | Sources: {[s.value for s in sources]}")
        
        result = ResearchResult(query=query, sources_searched=len(sources))
        all_findings: List[ResearchFinding] = []
        
        # Search each source
        for source_type in sources:
            try:
                findings = await self._search_source(query, source_type)
                all_findings.extend(findings)
                result.total_findings += len(findings)
            except Exception as e:
                logger.warning(f"Source {source_type.value} search failed: {e}")
        
        # Deduplicate findings
        unique_findings = self._deduplicate_findings(all_findings)
        result.deduplicated_count = result.total_findings - len(unique_findings)
        
        # Verify facts if requested
        if verify_facts:
            unique_findings = await self._verify_findings(unique_findings)
        
        # Sort by combined score and take top results
        unique_findings.sort(
            key=lambda f: (f.trust_score * 0.6 + f.relevance_score * 0.4),
            reverse=True
        )
        result.findings = unique_findings[:max_results]
        
        # Generate summary
        result.summary = self._generate_summary(query, result.findings)
        
        # Calculate confidence
        if result.findings:
            avg_trust = sum(f.trust_score for f in result.findings) / len(result.findings)
            avg_relevance = sum(f.relevance_score for f in result.findings) / len(result.findings)
            result.confidence = (avg_trust * 0.6 + avg_relevance * 0.4)
        
        # Store in memory
        await self._store_in_memory(result)
        
        # Track in learning loop
        self._track_outcome(result)
        
        logger.info(f"✅ Research complete: {len(result.findings)} findings, {result.confidence:.2f} confidence")
        
        return result
    
    async def _search_source(
        self,
        query: str,
        source_type: SourceType
    ) -> List[ResearchFinding]:
        """Search a specific source type."""
        findings = []
        
        if source_type == SourceType.WEB:
            findings = await self._search_web(query)
        elif source_type == SourceType.LOCAL_KB:
            findings = await self._search_local_kb(query)
        elif source_type == SourceType.AGENT_MEMORY:
            findings = await self._search_agent_memory(query)
        elif source_type == SourceType.MCP_TOOL:
            findings = await self._search_mcp_tools(query)
        elif source_type == SourceType.DOCUMENT:
            findings = await self._search_documents(query)
        
        return findings
    
    async def _search_web(self, query: str) -> List[ResearchFinding]:
        """Search the web for relevant information."""
        findings = []
        
        try:
            # Try to use deep_search service if available
            from backend.services.deep_search_service import DeepSearchService
            search = DeepSearchService()
            
            results = await search.search_web(query, max_results=self.max_results_per_source)
            
            for r in results:
                finding = ResearchFinding(
                    finding_id=self._generate_finding_id(r.get("content", "")),
                    query=query,
                    content=r.get("content", r.get("snippet", "")),
                    source_type=SourceType.WEB,
                    source_url=r.get("url", ""),
                    source_name=r.get("title", "Web Result"),
                    trust_score=r.get("trust_score", 0.5),
                    relevance_score=r.get("relevance", 0.5)
                )
                findings.append(finding)
                
        except ImportError:
            # Fallback: simulate web search
            logger.warning("DeepSearchService not available, using simulation")
            finding = ResearchFinding(
                finding_id=self._generate_finding_id(query),
                query=query,
                content=f"[Simulated web result for: {query}]",
                source_type=SourceType.WEB,
                source_name="Web Search Simulation",
                trust_score=0.3,
                relevance_score=0.5
            )
            findings.append(finding)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
        
        return findings
    
    async def _search_local_kb(self, query: str) -> List[ResearchFinding]:
        """Search local knowledge base (NBMF memory)."""
        findings = []
        
        try:
            from backend.services.memory.hot_memory import HotMemory
            hot = HotMemory()
            
            results = hot.search(query, top_k=self.max_results_per_source)
            
            for r in results:
                finding = ResearchFinding(
                    finding_id=r.get("item_id", self._generate_finding_id(r.get("content", ""))),
                    query=query,
                    content=r.get("content", ""),
                    source_type=SourceType.LOCAL_KB,
                    source_name="NBMF Hot Memory",
                    trust_score=0.9,  # Local memory is trusted
                    relevance_score=r.get("score", 0.5)
                )
                findings.append(finding)
                
        except Exception as e:
            logger.debug(f"Local KB search failed: {e}")
        
        return findings
    
    async def _search_agent_memory(self, query: str) -> List[ResearchFinding]:
        """Search agent unified memory."""
        findings = []
        
        try:
            from backend.services.unified_memory import UnifiedMemory
            memory = UnifiedMemory()
            
            # Search for relevant memories
            results = memory.search_similar(query, top_k=self.max_results_per_source)
            
            for r in results:
                finding = ResearchFinding(
                    finding_id=r.get("memory_id", self._generate_finding_id(r.get("content", ""))),
                    query=query,
                    content=r.get("content", ""),
                    source_type=SourceType.AGENT_MEMORY,
                    source_name="Unified Agent Memory",
                    trust_score=0.95,  # Agent memory is highly trusted
                    relevance_score=r.get("similarity", 0.5)
                )
                findings.append(finding)
                
        except Exception as e:
            logger.debug(f"Agent memory search failed: {e}")
        
        return findings
    
    async def _search_mcp_tools(self, query: str) -> List[ResearchFinding]:
        """Use MCP tools to gather information."""
        findings = []
        
        try:
            from backend.services.mcp.mcp_server import get_mcp_server
            mcp = get_mcp_server()
            
            # Use daena_research tool
            result = await mcp.call_tool("daena_research", {"query": query})
            
            if result and "findings" in result:
                for item in result["findings"]:
                    finding = ResearchFinding(
                        finding_id=self._generate_finding_id(item.get("content", "")),
                        query=query,
                        content=item.get("content", str(item)),
                        source_type=SourceType.MCP_TOOL,
                        source_name=item.get("source", "MCP Tool"),
                        trust_score=item.get("confidence", 0.5),
                        relevance_score=0.7
                    )
                    findings.append(finding)
                    
        except Exception as e:
            logger.debug(f"MCP tools search failed: {e}")
        
        return findings
    
    async def _search_documents(self, query: str) -> List[ResearchFinding]:
        """Search uploaded documents."""
        findings = []
        # TODO: Implement document search when document service is available
        return findings
    
    def _deduplicate_findings(self, findings: List[ResearchFinding]) -> List[ResearchFinding]:
        """Remove duplicate findings based on content hash."""
        unique = []
        seen_hashes = set()
        
        for finding in findings:
            content_hash = hashlib.sha256(finding.content.encode()).hexdigest()[:16]
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique.append(finding)
        
        return unique
    
    async def _verify_findings(self, findings: List[ResearchFinding]) -> List[ResearchFinding]:
        """Verify findings using IntegrityShield."""
        try:
            from backend.services.integrity_shield import get_integrity_shield
            shield = get_integrity_shield()
            
            for finding in findings:
                # Run fact check
                result = await shield.fact_check(
                    content=finding.content,
                    source=finding.source_url or finding.source_name
                )
                
                finding.verified = result.verified
                if result.trust_score is not None:
                    finding.trust_score = result.trust_score
                    
        except Exception as e:
            logger.warning(f"Finding verification failed: {e}")
        
        return findings
    
    def _generate_summary(self, query: str, findings: List[ResearchFinding]) -> str:
        """Generate a summary of research findings."""
        if not findings:
            return f"No findings for query: {query}"
        
        high_trust = [f for f in findings if f.trust_score >= 0.7]
        
        if high_trust:
            summary = f"Found {len(findings)} results for '{query}'. "
            summary += f"{len(high_trust)} are high-trust sources. "
            summary += f"Top finding: {findings[0].content[:200]}..."
        else:
            summary = f"Found {len(findings)} results for '{query}', but none with high trust. "
            summary += "Consider verifying from authoritative sources."
        
        return summary
    
    async def _store_in_memory(self, result: ResearchResult):
        """Store research result in NBMF memory."""
        try:
            from backend.services.memory.memory_router import get_memory_router
            router = get_memory_router()
            
            # Store as research_note class
            content = {
                "query": result.query,
                "summary": result.summary,
                "findings_count": len(result.findings),
                "confidence": result.confidence,
                "top_findings": [f.to_dict() for f in result.findings[:3]]
            }
            
            router.route(
                content=str(content),
                data_class="research_note",
                metadata={
                    "type": "research_result",
                    "query": result.query,
                    "source_types": list(set(f.source_type.value for f in result.findings))
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to store research in memory: {e}")
    
    def _track_outcome(self, result: ResearchResult):
        """Track research outcome in learning loop."""
        try:
            from backend.services.outcome_tracker import get_outcome_tracker
            tracker = get_outcome_tracker()
            
            # Record the action
            action_id = tracker.record_action(
                agent_id="research_agent",
                action_type="research_query",
                description=f"Research: {result.query}",
                parameters={
                    "sources_searched": result.sources_searched,
                    "findings_count": len(result.findings)
                }
            )
            
            # Log outcome
            tracker.log_outcome(
                action_id=action_id,
                success=len(result.findings) > 0,
                result_summary=result.summary,
                confidence=result.confidence
            )
            
        except Exception as e:
            logger.debug(f"Outcome tracking failed: {e}")
    
    def _generate_finding_id(self, content: str) -> str:
        """Generate unique ID for a finding based on content."""
        return f"find_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def get_search_history(self, limit: int = 20) -> List[Dict]:
        """Get recent search history."""
        return self._search_history[-limit:]


# Singleton instance
_research_agent: Optional[ResearchAgent] = None


def get_research_agent() -> ResearchAgent:
    """Get the singleton ResearchAgent instance."""
    global _research_agent
    if _research_agent is None:
        _research_agent = ResearchAgent()
    return _research_agent
