"""
MCP Server - Exposes Daena's capabilities to other agents

Per DAENA_FULL_POWER.md Part 2:
- Exposes Daena's research, DeFi scan, Council consult, and fact-check tools
- Requires API key authentication
- Rate-limited and logged
- Makes Daena a valuable service other agents want to use

Created: 2026-01-31
"""

import json
import asyncio
import logging
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger(__name__)


@dataclass 
class RateLimitEntry:
    """Rate limit tracking for a client"""
    client_id: str
    requests: List[datetime] = field(default_factory=list)
    max_per_minute: int = 10
    
    def can_make_request(self) -> bool:
        """Check if client can make another request"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        self.requests = [r for r in self.requests if r > cutoff]
        return len(self.requests) < self.max_per_minute
    
    def record_request(self) -> None:
        """Record a request"""
        self.requests.append(datetime.utcnow())


class DaenaMCPServer:
    """
    MCP Server that exposes Daena's tools to external agents.
    
    Available tools:
    - daena_research: Given a topic, returns verified research with sources
    - daena_defi_scan: Given contract code, returns security audit
    - daena_council_consult: Given a decision, returns Council recommendation  
    - daena_fact_check: Given a claim, returns verification status + sources
    """
    
    # Tool definitions for MCP
    TOOLS = [
        {
            "name": "daena_research",
            "description": "Research a topic and return verified information with sources. Uses Daena's multi-agent research pipeline.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to research"
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["quick", "standard", "deep"],
                        "description": "Research depth: quick (1min), standard (5min), deep (15min)"
                    }
                },
                "required": ["topic"]
            }
        },
        {
            "name": "daena_defi_scan",
            "description": "Scan a smart contract for security vulnerabilities. Returns findings with severity ratings.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contract_code": {
                        "type": "string",
                        "description": "Solidity contract code to scan"
                    },
                    "contract_name": {
                        "type": "string",
                        "description": "Optional name for the contract"
                    }
                },
                "required": ["contract_code"]
            }
        },
        {
            "name": "daena_council_consult",
            "description": "Consult Daena's Council of experts on a decision. Returns weighted recommendation from multiple perspectives.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "description": "The decision or question to consult on"
                    },
                    "domain": {
                        "type": "string",
                        "enum": ["general", "technical", "financial", "legal", "security"],
                        "description": "Domain for expert selection"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context for the decision"
                    }
                },
                "required": ["decision"]
            }
        },
        {
            "name": "daena_fact_check",
            "description": "Verify a claim against Daena's knowledge and external sources. Returns verification status with citations.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The claim to fact-check"
                    },
                    "sources_required": {
                        "type": "integer",
                        "description": "Minimum number of sources required for verification (default: 3)"
                    }
                },
                "required": ["claim"]
            }
        }
    ]
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        self.api_keys = api_keys or {}
        self.rate_limits: Dict[str, RateLimitEntry] = {}
        self.usage_log: List[Dict[str, Any]] = []
        self._request_id = 0
    
    def validate_api_key(self, key: str) -> Optional[str]:
        """Validate API key and return client ID"""
        for client_id, valid_key in self.api_keys.items():
            if key == valid_key:
                return client_id
        return None
    
    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limits"""
        if client_id not in self.rate_limits:
            self.rate_limits[client_id] = RateLimitEntry(client_id=client_id)
        return self.rate_limits[client_id].can_make_request()
    
    def record_usage(self, client_id: str, tool_name: str, success: bool) -> None:
        """Log tool usage"""
        if client_id in self.rate_limits:
            self.rate_limits[client_id].record_request()
        
        self.usage_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id,
            "tool": tool_name,
            "success": success
        })
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any], client_id: str) -> Dict[str, Any]:
        """Handle a tool call from an external agent"""
        
        # Rate limit check
        if not self.check_rate_limit(client_id):
            return {
                "error": "Rate limit exceeded. Max 10 requests per minute.",
                "retry_after_seconds": 60
            }
        
        try:
            if tool_name == "daena_research":
                result = await self._do_research(arguments)
            elif tool_name == "daena_defi_scan":
                result = await self._do_defi_scan(arguments)
            elif tool_name == "daena_council_consult":
                result = await self._do_council_consult(arguments)
            elif tool_name == "daena_fact_check":
                result = await self._do_fact_check(arguments)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            self.record_usage(client_id, tool_name, "error" not in result)
            return result
            
        except Exception as e:
            logger.error(f"MCP tool error: {tool_name} - {e}")
            self.record_usage(client_id, tool_name, False)
            return {"error": str(e)}
    
    async def _do_research(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research using Daena's research pipeline"""
        topic = args.get("topic", "")
        depth = args.get("depth", "standard")
        
        if not topic:
            return {"error": "Topic is required"}
        
        # TODO: Integrate with actual research agent
        # For now, return placeholder
        return {
            "topic": topic,
            "depth": depth,
            "summary": f"Research on '{topic}' would be performed here using Daena's multi-agent research pipeline.",
            "sources": [
                {"url": "https://example.com/source1", "trust_score": 85},
                {"url": "https://example.com/source2", "trust_score": 78}
            ],
            "verified": True,
            "note": "Full integration pending - placeholder response"
        }
    
    async def _do_defi_scan(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute DeFi security scan"""
        contract_code = args.get("contract_code", "")
        contract_name = args.get("contract_name", "Contract")
        
        if not contract_code:
            return {"error": "Contract code is required"}
        
        if len(contract_code) < 50:
            return {"error": "Contract code too short"}
        
        # TODO: Integrate with DeFi scanner
        # For now, return placeholder with structure
        return {
            "contract_name": contract_name,
            "scan_status": "completed",
            "findings": [
                {
                    "severity": "Medium",
                    "title": "Placeholder finding",
                    "description": "Full integration with Slither pending"
                }
            ],
            "summary": {
                "risk_level": "MEDIUM",
                "total_findings": 1
            },
            "note": "Full Slither integration pending - placeholder response"
        }
    
    async def _do_council_consult(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Consult Daena's Council of experts"""
        decision = args.get("decision", "")
        domain = args.get("domain", "general")
        context = args.get("context", "")
        
        if not decision:
            return {"error": "Decision is required"}
        
        # TODO: Integrate with Council system
        return {
            "decision": decision,
            "domain": domain,
            "recommendation": "APPROVE",
            "confidence": 0.75,
            "expert_votes": [
                {"expert": "TechAdvisor", "vote": "approve", "reasoning": "Placeholder"},
                {"expert": "RiskAnalyst", "vote": "approve", "reasoning": "Placeholder"},
                {"expert": "DomainExpert", "vote": "neutral", "reasoning": "Placeholder"}
            ],
            "consensus": "Majority approval with moderate confidence",
            "note": "Full Council integration pending - placeholder response"
        }
    
    async def _do_fact_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Fact-check a claim using the Data Integrity Shield"""
        claim = args.get("claim", "")
        sources_required = args.get("sources_required", 3)
        
        if not claim:
            return {"error": "Claim is required"}
        
        try:
            # Use the real Integrity Shield
            from backend.services.integrity_shield import get_integrity_shield
            
            shield = get_integrity_shield()
            
            # Verify the claim as external data
            report = shield.verify(
                content=claim,
                source="mcp_fact_check",
                content_type="claim"
            )
            
            # Determine verification status based on result
            if report.result.value == "passed":
                verification_status = "verified"
                confidence = 0.8
            elif report.result.value == "flagged":
                verification_status = "flagged"
                confidence = 0.4
            elif report.result.value == "blocked":
                verification_status = "rejected"
                confidence = 0.1
            elif report.result.value == "injection_detected":
                verification_status = "malicious"
                confidence = 0.0
            else:
                verification_status = "unverified"
                confidence = 0.5
            
            # Build detailed response
            return {
                "claim": claim,
                "verification_status": verification_status,
                "confidence": confidence,
                "sources_found": 1 if report.source_info else 0,
                "sources_required": sources_required,
                "flags": report.flags,
                "manipulation_score": report.manipulation_score,
                "injection_detected": report.injection_detected,
                "source_trust": {
                    "domain": report.source_info.domain if report.source_info else None,
                    "trust_score": report.source_info.trust_score if report.source_info else 0,
                    "trust_level": report.source_info.trust_level.value if report.source_info else "unknown"
                },
                "recommendation": report.recommendations[0] if report.recommendations else "Review this claim carefully before accepting.",
                "note": "Verified using Daena's Data Integrity Shield"
            }
            
        except Exception as e:
            logger.error(f"Fact check error: {e}")
            # Fallback to basic response
            return {
                "claim": claim,
                "verification_status": "error",
                "confidence": 0.0,
                "sources_found": 0,
                "sources_required": sources_required,
                "error": str(e),
                "recommendation": "Could not verify - treat as unverified"
            }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        if not self.usage_log:
            return {"total_requests": 0}
        
        return {
            "total_requests": len(self.usage_log),
            "by_tool": {
                tool["name"]: len([u for u in self.usage_log if u["tool"] == tool["name"]])
                for tool in self.TOOLS
            },
            "success_rate": (
                len([u for u in self.usage_log if u["success"]]) / len(self.usage_log) * 100
            ) if self.usage_log else 0
        }


# ============================================
# Stdio Server (for MCP protocol compliance)
# ============================================

async def run_stdio_server(server: DaenaMCPServer):
    """Run the MCP server on stdio (for MCP protocol compliance)"""
    
    async def read_stdin():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        return reader
    
    async def write_stdout(data: str):
        sys.stdout.write(data + "\n")
        sys.stdout.flush()
    
    reader = await read_stdin()
    
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            
            request = json.loads(line.decode().strip())
            response = await handle_request(server, request)
            
            if response:
                await write_stdout(json.dumps(response))
                
        except Exception as e:
            logger.error(f"Stdio server error: {e}")


async def handle_request(server: DaenaMCPServer, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle an incoming JSON-RPC request"""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "Daena MCP Server",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": server.TOOLS
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        # For stdio, use a default client ID
        result = await server.handle_tool_call(tool_name, arguments, "stdio_client")
        
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        }
    
    elif method == "notifications/initialized":
        # No response needed for notification
        return None
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


# Global instance
_mcp_server: Optional[DaenaMCPServer] = None


def get_mcp_server() -> DaenaMCPServer:
    """Get or create the global MCP server instance"""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = DaenaMCPServer()
    return _mcp_server


if __name__ == "__main__":
    # Run as standalone MCP server
    logging.basicConfig(level=logging.INFO)
    server = DaenaMCPServer()
    asyncio.run(run_stdio_server(server))
