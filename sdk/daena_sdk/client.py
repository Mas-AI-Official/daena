"""
Daena AI VP Python SDK Client

Production-ready Python SDK for Daena AI VP System.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    DaenaAPIError,
    DaenaAuthenticationError,
    DaenaRateLimitError,
    DaenaNotFoundError,
    DaenaValidationError,
    DaenaTimeoutError
)
from .models import (
    Agent,
    Department,
    MemoryRecord,
    CouncilDecision,
    ExperienceVector,
    SystemMetrics
)


class DaenaClient:
    """
    Official Python SDK client for Daena AI VP System.
    
    Provides a clean, type-safe interface to all Daena APIs.
    
    Example:
        ```python
        from daena_sdk import DaenaClient
        
        client = DaenaClient(
            api_key="your-api-key",
            base_url="https://api.daena.ai"
        )
        
        # Get system health
        health = client.get_health()
        
        # Get all agents
        agents = client.get_agents()
        
        # Send a message to Daena
        response = client.chat("What's the status of our marketing campaigns?")
        ```
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 1.0
    ):
        """
        Initialize Daena SDK client.
        
        Args:
            api_key: Your Daena API key
            base_url: Base URL for Daena API (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum number of retries for failed requests (default: 3)
            retry_backoff: Backoff multiplier for retries (default: 1.0)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": f"Daena-Python-SDK/1.0.0"
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Daena API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path (e.g., "/api/v1/system/health")
            params: URL query parameters
            json_data: JSON request body
            **kwargs: Additional arguments passed to requests
            
        Returns:
            Response JSON data
            
        Raises:
            DaenaAPIError: For API errors
            DaenaAuthenticationError: For authentication errors
            DaenaRateLimitError: For rate limit errors
            DaenaNotFoundError: For 404 errors
            DaenaValidationError: For validation errors
            DaenaTimeoutError: For timeout errors
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
                **kwargs
            )
            
            # Handle different status codes
            if response.status_code == 401:
                raise DaenaAuthenticationError(
                    "Authentication failed. Please check your API key.",
                    status_code=401,
                    response=response.json() if response.content else None
                )
            elif response.status_code == 404:
                raise DaenaNotFoundError(
                    f"Resource not found: {endpoint}",
                    status_code=404,
                    response=response.json() if response.content else None
                )
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise DaenaRateLimitError(
                    "Rate limit exceeded. Please try again later.",
                    retry_after=retry_after,
                    status_code=429,
                    response=response.json() if response.content else None
                )
            elif response.status_code == 422:
                raise DaenaValidationError(
                    "Request validation failed.",
                    status_code=422,
                    response=response.json() if response.content else None
                )
            elif not response.ok:
                error_data = response.json() if response.content else {}
                raise DaenaAPIError(
                    error_data.get("detail", f"API request failed: {response.status_code}"),
                    status_code=response.status_code,
                    response=error_data
                )
            
            # Return JSON response
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.Timeout:
            raise DaenaTimeoutError(
                f"Request to {endpoint} timed out after {self.timeout}s",
                status_code=None
            )
        except requests.exceptions.RequestException as e:
            raise DaenaAPIError(
                f"Request failed: {str(e)}",
                status_code=None
            )
    
    # ===================================================================
    # System Endpoints
    # ===================================================================
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get system health status.
        
        Returns:
            Health status information
        """
        return self._request("GET", "/api/v1/system/health")
    
    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive system summary.
        
        Returns:
            System summary including agents, departments, memory, etc.
        """
        return self._request("GET", "/api/v1/system/summary")
    
    def get_system_metrics(self) -> SystemMetrics:
        """
        Get system metrics.
        
        Returns:
            SystemMetrics object with current system metrics
        """
        data = self._request("GET", "/api/v1/monitoring/metrics")
        return SystemMetrics(**data) if isinstance(data, dict) else SystemMetrics(
            total_agents=0,
            active_agents=0,
            departments=0,
            memory_usage={},
            api_calls_per_minute=0.0,
            average_latency_ms=0.0,
            error_rate=0.0,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    # ===================================================================
    # Agent Management
    # ===================================================================
    
    def get_agents(
        self,
        department_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Agent]:
        """
        Get list of agents.
        
        Args:
            department_id: Filter by department ID (optional)
            status: Filter by status (optional)
            limit: Maximum number of agents to return (default: 100)
            offset: Number of agents to skip (default: 0)
            
        Returns:
            List of Agent objects
        """
        params = {"limit": limit, "offset": offset}
        if department_id:
            params["department_id"] = department_id
        if status:
            params["status"] = status
        
        data = self._request("GET", "/api/v1/agents", params=params)
        agents = data.get("agents", []) if isinstance(data, dict) else []
        return [Agent(**agent) if isinstance(agent, dict) else agent for agent in agents]
    
    def get_agent(self, agent_id: str) -> Agent:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent object
            
        Raises:
            DaenaNotFoundError: If agent not found
        """
        data = self._request("GET", f"/api/v1/agents/{agent_id}")
        return Agent(**data) if isinstance(data, dict) else None
    
    def get_agent_metrics(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get agent metrics.
        
        Args:
            agent_id: Specific agent ID (optional, returns all if not specified)
            
        Returns:
            Agent metrics data
        """
        endpoint = f"/api/v1/monitoring/agent-metrics"
        if agent_id:
            endpoint += f"?agent_id={agent_id}"
        return self._request("GET", endpoint)
    
    # ===================================================================
    # Daena Chat
    # ===================================================================
    
    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to Daena chat.
        
        Args:
            message: Message text
            session_id: Chat session ID (optional, creates new if not provided)
            context: Additional context (optional)
            
        Returns:
            Chat response
        """
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        if context:
            payload["context"] = context
        
        return self._request("POST", "/api/v1/daena/chat", json_data=payload)
    
    def get_chat_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get chat session status.
        
        Args:
            session_id: Chat session ID
            
        Returns:
            Chat session status
        """
        return self._request("GET", f"/api/v1/daena/chat/{session_id}/status")
    
    # ===================================================================
    # Memory & NBMF
    # ===================================================================
    
    def store_memory(
        self,
        key: str,
        payload: Any,
        class_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ) -> MemoryRecord:
        """
        Store a memory record using NBMF.
        
        Args:
            key: Memory key
            payload: Data to store
            class_name: Record class name (default: "default")
            metadata: Additional metadata (optional)
            tenant_id: Tenant ID (optional)
            
        Returns:
            MemoryRecord object
        """
        payload_data = {
            "key": key,
            "payload": payload,
            "class_name": class_name
        }
        if metadata:
            payload_data["metadata"] = metadata
        if tenant_id:
            payload_data["tenant_id"] = tenant_id
        
        data = self._request("POST", "/api/v1/memory/store", json_data=payload_data)
        return MemoryRecord(**data) if isinstance(data, dict) else None
    
    def retrieve_memory(
        self,
        key: str,
        tenant_id: Optional[str] = None
    ) -> Optional[MemoryRecord]:
        """
        Retrieve a memory record.
        
        Args:
            key: Memory key
            tenant_id: Tenant ID (optional)
            
        Returns:
            MemoryRecord object or None if not found
        """
        params = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        
        try:
            data = self._request("GET", f"/api/v1/memory/retrieve/{key}", params=params)
            return MemoryRecord(**data) if isinstance(data, dict) else None
        except DaenaNotFoundError:
            return None
    
    def search_memory(
        self,
        query: str,
        limit: int = 10,
        tenant_id: Optional[str] = None
    ) -> List[MemoryRecord]:
        """
        Search memory records.
        
        Args:
            query: Search query
            limit: Maximum number of results (default: 10)
            tenant_id: Tenant ID (optional)
            
        Returns:
            List of MemoryRecord objects
        """
        params = {"query": query, "limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        
        data = self._request("GET", "/api/v1/memory/search", params=params)
        records = data.get("results", []) if isinstance(data, dict) else []
        return [MemoryRecord(**rec) if isinstance(rec, dict) else rec for rec in records]
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """
        Get memory system metrics.
        
        Returns:
            Memory metrics including compression, latency, storage, etc.
        """
        return self._request("GET", "/api/v1/memory/metrics")
    
    # ===================================================================
    # Council System
    # ===================================================================
    
    def run_council_debate(
        self,
        department: str,
        topic: str,
        context: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ) -> CouncilDecision:
        """
        Run a council debate on a topic.
        
        Args:
            department: Department name
            topic: Debate topic
            context: Additional context (optional)
            tenant_id: Tenant ID (optional)
            
        Returns:
            CouncilDecision object
        """
        payload = {
            "department": department,
            "topic": topic
        }
        if context:
            payload["context"] = context
        if tenant_id:
            payload["tenant_id"] = tenant_id
        
        data = self._request("POST", "/api/v1/council/debate", json_data=payload)
        return CouncilDecision(**data) if isinstance(data, dict) else None
    
    def get_council_conclusions(
        self,
        department: Optional[str] = None,
        limit: int = 10
    ) -> List[CouncilDecision]:
        """
        Get recent council conclusions.
        
        Args:
            department: Filter by department (optional)
            limit: Maximum number of conclusions (default: 10)
            
        Returns:
            List of CouncilDecision objects
        """
        params = {"limit": limit}
        if department:
            params["department"] = department
        
        data = self._request("GET", "/api/v1/council/conclusions", params=params)
        decisions = data.get("decisions", []) if isinstance(data, dict) else []
        return [CouncilDecision(**d) if isinstance(d, dict) else d for d in decisions]
    
    def get_pending_approvals(
        self,
        department: Optional[str] = None,
        impact: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get pending council approvals.
        
        Args:
            department: Filter by department (optional)
            impact: Filter by impact level (optional: low, medium, high, critical)
            limit: Maximum number of approvals (default: 50)
            
        Returns:
            List of pending approval records
        """
        params = {"limit": limit}
        if department:
            params["department"] = department
        if impact:
            params["impact"] = impact
        
        data = self._request("GET", "/api/v1/council/approvals/pending", params=params)
        return data.get("approvals", []) if isinstance(data, dict) else []
    
    def approve_decision(self, decision_id: str, approver_id: str) -> Dict[str, Any]:
        """
        Approve a council decision.
        
        Args:
            decision_id: Decision ID to approve
            approver_id: ID of the approver
            
        Returns:
            Approval result
        """
        return self._request(
            "POST",
            f"/api/v1/council/approvals/{decision_id}/approve",
            json_data={"approver_id": approver_id}
        )
    
    # ===================================================================
    # Knowledge Distillation
    # ===================================================================
    
    def distill_experience(
        self,
        data_items: List[Dict[str, Any]],
        tenant_id: Optional[str] = None
    ) -> List[ExperienceVector]:
        """
        Distill experience vectors from data items.
        
        Args:
            data_items: List of data items to analyze (minimum 2 required)
            tenant_id: Tenant ID (optional)
            
        Returns:
            List of ExperienceVector objects
        """
        payload = {"data_items": data_items}
        if tenant_id:
            payload["tenant_id"] = tenant_id
        
        data = self._request("POST", "/api/v1/knowledge/distill", json_data=payload)
        vectors = data.get("vectors", []) if isinstance(data, dict) else []
        return [ExperienceVector(**v) if isinstance(v, dict) else v for v in vectors]
    
    def search_similar_patterns(
        self,
        query_features: Dict[str, float],
        pattern_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar knowledge patterns.
        
        Args:
            query_features: Feature vector to search for
            pattern_type: Filter by pattern type (optional)
            top_k: Number of results (default: 5)
            similarity_threshold: Minimum similarity (default: 0.7)
            
        Returns:
            List of similar patterns with similarity scores
        """
        payload = {
            "query_features": query_features,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold
        }
        if pattern_type:
            payload["pattern_type"] = pattern_type
        
        data = self._request("POST", "/api/v1/knowledge/search", json_data=payload)
        return data.get("patterns", []) if isinstance(data, dict) else []
    
    def get_pattern_recommendations(
        self,
        context: Dict[str, Any],
        pattern_type: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get pattern recommendations based on context.
        
        Args:
            context: Context information
            pattern_type: Filter by pattern type (optional)
            top_k: Number of recommendations (default: 3)
            
        Returns:
            List of recommended patterns
        """
        payload = {"context": context, "top_k": top_k}
        if pattern_type:
            payload["pattern_type"] = pattern_type
        
        data = self._request("POST", "/api/v1/knowledge/recommend", json_data=payload)
        return data.get("recommendations", []) if isinstance(data, dict) else []
    
    # ===================================================================
    # OCR Comparison
    # ===================================================================
    
    def get_ocr_comparison_stats(self) -> Dict[str, Any]:
        """
        Get OCR comparison statistics.
        
        Returns:
            Comparison statistics showing NBMF advantages
        """
        return self._request("GET", "/api/v1/ocr-comparison/stats")
    
    def compare_with_ocr(self, image_path: str) -> Dict[str, Any]:
        """
        Compare NBMF encoding with OCR for a specific image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Comparison results
        """
        return self._request(
            "POST",
            "/api/v1/ocr-comparison/compare",
            json_data={"image_path": image_path}
        )
    
    def get_ocr_benchmark(self) -> Dict[str, Any]:
        """
        Get OCR benchmark results.
        
        Returns:
            Benchmark results comparing NBMF vs OCR
        """
        return self._request("GET", "/api/v1/ocr-comparison/benchmark")
    
    # ===================================================================
    # Analytics
    # ===================================================================
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get analytics summary.
        
        Returns:
            Comprehensive analytics summary
        """
        return self._request("GET", "/api/v1/analytics/summary")
    
    def get_advanced_insights(self) -> Dict[str, Any]:
        """
        Get advanced analytics insights.
        
        Returns:
            Insights including predictions, recommendations, trends
        """
        return self._request("GET", "/api/v1/analytics/insights")
    
    # ===================================================================
    # Utility Methods
    # ===================================================================
    
    def test_connection(self) -> bool:
        """
        Test connection to Daena API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.get_health()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()

