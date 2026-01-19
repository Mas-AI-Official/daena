from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
from datetime import datetime

from services.llm_service import LLMService
from services.auth_service import get_current_user, User
from database import get_db

router = APIRouter(prefix="/api/v1/deep-search", tags=["Deep Search"])

class DeepSearchRequest(BaseModel):
    query: str
    llm_providers: List[str] = ["openai"]  # Can select multiple LLMs
    search_depth: str = "comprehensive"  # basic, comprehensive, expert
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    max_results: int = 5
    include_conclusion: bool = True
    conclusion_method: str = "llm_aggregation"  # llm_aggregation, local_brain, hybrid

class DeepSearchResult(BaseModel):
    provider: str
    response: str
    confidence: float
    processing_time: float
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class DeepSearchResponse(BaseModel):
    query: str
    results: List[DeepSearchResult]
    aggregated_analysis: Optional[str] = None
    conclusion: Optional[str] = None
    total_processing_time: float
    llm_providers_used: List[str]
    search_depth: str
    timestamp: datetime
    session_id: Optional[str] = None

@router.get("/providers")
async def get_available_llm_providers():
    """Get list of available LLM providers for deep search"""
    return {
        "providers": [
            {"id": "openai", "name": "OpenAI GPT", "status": "available"},
            {"id": "gemini", "name": "Google Gemini", "status": "available"},
            {"id": "anthropic", "name": "Anthropic Claude", "status": "available"},
            {"id": "deepseek", "name": "DeepSeek", "status": "available"},
            {"id": "grok", "name": "Grok AI", "status": "available"},
            {"id": "mistral", "name": "Mistral AI", "status": "available"},
            {"id": "claude", "name": "Claude", "status": "available"},
            {"id": "llama", "name": "Llama", "status": "available"},
            {"id": "azure_openai", "name": "Azure OpenAI", "status": "available"},
            {"id": "cohere", "name": "Cohere", "status": "available"}
        ],
        "search_depths": ["basic", "comprehensive", "expert"],
        "conclusion_methods": ["llm_aggregation", "local_brain", "hybrid"]
    }

@router.post("/perform", response_model=DeepSearchResponse)
async def perform_deep_search(
    request: DeepSearchRequest,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Perform deep search using multiple LLM providers with intelligent result aggregation
    """
    try:
        start_time = datetime.now()
        llm_service = LLMService()
        
        # Validate LLM providers - All available LLMs
        valid_providers = [
            "openai", "gemini", "anthropic", "deepseek", "grok", 
            "mistral", "claude", "llama", "azure_openai", "cohere"
        ]
        selected_providers = [p for p in request.llm_providers if p in valid_providers]
        
        if not selected_providers:
            selected_providers = ["openai"]  # Default fallback
        
        # Prepare search context based on depth
        search_context = _prepare_search_context(request.query, request.search_depth, request.context)
        
        # Execute parallel searches across selected LLMs
        search_tasks = []
        for provider in selected_providers:
            task = _execute_llm_search(
                llm_service, 
                provider, 
                search_context, 
                request.query,
                request.search_depth
            )
            search_tasks.append(task)
        
        # Wait for all searches to complete
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Process and validate results
        valid_results = []
        for i, result in enumerate(search_results):
            if isinstance(result, Exception):
                print(f"Error with {selected_providers[i]}: {result}")
                continue
            if result:
                valid_results.append(result)
        
        if not valid_results:
            raise HTTPException(status_code=500, detail="All LLM providers failed")
        
        # Generate aggregated analysis
        aggregated_analysis = await _generate_aggregated_analysis(
            llm_service, 
            request.query, 
            valid_results, 
            request.search_depth
        )
        
        # Generate intelligent conclusion
        conclusion = None
        if request.include_conclusion:
            conclusion = await _generate_conclusion(
                llm_service,
                request.query,
                valid_results,
                aggregated_analysis,
                request.conclusion_method
            )
        
        # Calculate total processing time
        total_time = (datetime.now() - start_time).total_seconds()
        
        return DeepSearchResponse(
            query=request.query,
            results=valid_results,
            aggregated_analysis=aggregated_analysis,
            conclusion=conclusion,
            total_processing_time=total_time,
            llm_providers_used=selected_providers,
            search_depth=request.search_depth,
            timestamp=datetime.now(),
            session_id=request.session_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deep search failed: {str(e)}")

async def _execute_llm_search(
    llm_service: LLMService, 
    provider: str, 
    context: str, 
    query: str,
    depth: str
) -> Optional[DeepSearchResult]:
    """Execute search with a specific LLM provider"""
    try:
        start_time = datetime.now()
        
        # Prepare enhanced prompt based on search depth
        enhanced_prompt = _create_enhanced_prompt(query, context, depth, provider)
        
        # Execute the search
        response = await llm_service.generate_response(
            prompt=enhanced_prompt,
            provider=provider,
            max_tokens=2000 if depth == "expert" else 1000,
            temperature=0.3 if depth == "expert" else 0.1
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Calculate confidence based on response quality
        confidence = _calculate_confidence(response, depth)
        
        return DeepSearchResult(
            provider=provider,
            response=response,
            confidence=confidence,
            processing_time=processing_time,
            metadata={
                "depth": depth,
                "context_length": len(context),
                "response_length": len(response)
            }
        )
        
    except Exception as e:
        print(f"Error executing search with {provider}: {e}")
        return None

def _prepare_search_context(query: str, depth: str, context: Optional[Dict] = None) -> str:
    """Prepare enhanced search context based on depth"""
    base_context = f"Query: {query}\n"
    
    if depth == "basic":
        return base_context + "Provide a concise, factual response."
    elif depth == "comprehensive":
        return base_context + "Provide a detailed analysis with multiple perspectives and supporting evidence."
    elif depth == "expert":
        return base_context + "Provide an expert-level analysis with deep insights, critical evaluation, and actionable recommendations."
    
    return base_context

def _create_enhanced_prompt(query: str, context: str, depth: str, provider: str) -> str:
    """Create an enhanced prompt for better search results"""
    
    system_prompts = {
        "openai": "You are an expert AI analyst. Provide comprehensive, well-structured analysis.",
        "gemini": "You are a Google AI expert. Deliver thorough, research-backed insights.",
        "claude": "You are an Anthropic AI specialist. Offer nuanced, ethical analysis.",
        "grok": "You are a Grok AI expert. Provide innovative, cutting-edge insights.",
        "deepseek": "You are a DeepSeek AI specialist. Deliver deep, technical analysis."
    }
    
    system_prompt = system_prompts.get(provider, "You are an expert AI analyst.")
    
    depth_instructions = {
        "basic": "Keep your response concise and factual.",
        "comprehensive": "Provide detailed analysis with multiple perspectives.",
        "expert": "Deliver expert-level insights with critical evaluation and recommendations."
    }
    
    return f"""
{system_prompt}

{context}

Depth Level: {depth}
{depth_instructions.get(depth, "")}

Please analyze the query thoroughly and provide your insights.
"""

def _calculate_confidence(response: str, depth: str) -> float:
    """Calculate confidence score based on response quality"""
    base_score = 0.5
    
    # Length factor
    length_factor = min(len(response) / 500, 1.0)
    
    # Structure factor (check for organized response)
    structure_indicators = ["first", "second", "third", "conclusion", "summary", "analysis"]
    structure_score = sum(1 for indicator in structure_indicators if indicator.lower() in response.lower()) / len(structure_indicators)
    
    # Depth factor
    depth_multiplier = {"basic": 1.0, "comprehensive": 1.2, "expert": 1.5}.get(depth, 1.0)
    
    confidence = (base_score + length_factor * 0.3 + structure_score * 0.2) * depth_multiplier
    return min(confidence, 1.0)

async def _generate_aggregated_analysis(
    llm_service: LLMService,
    query: str,
    results: List[DeepSearchResult],
    depth: str
) -> str:
    """Generate aggregated analysis from multiple LLM results"""
    
    # Prepare results summary for aggregation
    results_summary = "\n\n".join([
        f"**{result.provider.upper()} Analysis:**\n{result.response}\n\nConfidence: {result.confidence:.2f}"
        for result in results
    ])
    
    aggregation_prompt = f"""
As an expert AI analyst, synthesize the following multiple AI analyses into a comprehensive, coherent analysis.

Original Query: {query}
Search Depth: {depth}

AI Analysis Results:
{results_summary}

Please provide:
1. A synthesized analysis that combines the best insights from all sources
2. Identification of areas of agreement and disagreement
3. Overall assessment of the query
4. Key takeaways and insights

Focus on creating a unified, well-structured analysis that leverages the strengths of each AI provider.
"""
    
    try:
        aggregated_response = await llm_service.generate_response(
            prompt=aggregation_prompt,
            provider="openai",  # Use OpenAI for aggregation
            max_tokens=1500,
            temperature=0.2
        )
        return aggregated_response
    except Exception as e:
        print(f"Error generating aggregated analysis: {e}")
        return "Unable to generate aggregated analysis due to technical issues."

async def _generate_conclusion(
    llm_service: LLMService,
    query: str,
    results: List[DeepSearchResult],
    aggregated_analysis: str,
    method: str
) -> str:
    """Generate intelligent conclusion using specified method"""
    
    if method == "llm_aggregation":
        return await _generate_llm_conclusion(llm_service, query, aggregated_analysis)
    elif method == "local_brain":
        return await _generate_local_brain_conclusion(query, results, aggregated_analysis)
    elif method == "hybrid":
        llm_conclusion = await _generate_llm_conclusion(llm_service, query, aggregated_analysis)
        local_conclusion = await _generate_local_brain_conclusion(query, results, aggregated_analysis)
        return f"**LLM Conclusion:**\n{llm_conclusion}\n\n**Local Brain Analysis:**\n{local_conclusion}"
    else:
        return await _generate_llm_conclusion(llm_service, query, aggregated_analysis)

async def _generate_llm_conclusion(
    llm_service: LLMService,
    query: str,
    aggregated_analysis: str
) -> str:
    """Generate conclusion using LLM"""
    
    conclusion_prompt = f"""
Based on the following comprehensive analysis, provide a clear, actionable conclusion.

Query: {query}

Analysis:
{aggregated_analysis}

Please provide:
1. A clear summary of key findings
2. Practical implications and recommendations
3. Next steps or actions to consider
4. Any limitations or areas for further investigation

Keep the conclusion concise but comprehensive.
"""
    
    try:
        conclusion = await llm_service.generate_response(
            prompt=conclusion_prompt,
            provider="openai",
            max_tokens=800,
            temperature=0.1
        )
        return conclusion
    except Exception as e:
        print(f"Error generating LLM conclusion: {e}")
        return "Unable to generate LLM conclusion due to technical issues."

async def _generate_local_brain_conclusion(
    query: str,
    results: List[DeepSearchResult],
    aggregated_analysis: str
) -> str:
    """Generate conclusion using local brain analysis"""
    
    # Analyze patterns in results
    provider_count = len(results)
    avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0
    
    # Identify strongest and weakest responses
    strongest_result = max(results, key=lambda x: x.confidence) if results else None
    weakest_result = min(results, key=lambda x: x.confidence) if results else None
    
    # Generate local analysis
    local_analysis = f"""
**Local Brain Analysis:**

Query Complexity Assessment: {query[:100]}...
Number of AI Providers Used: {provider_count}
Average Confidence Score: {avg_confidence:.2f}

Provider Performance:
- Strongest: {strongest_result.provider if strongest_result else 'N/A'} (Confidence: {strongest_result.confidence:.2f if strongest_result else 0})
- Weakest: {weakest_result.provider if weakest_result else 'N/A'} (Confidence: {weakest_result.confidence:.2f if weakest_result else 0})

Reliability Assessment: {'High' if avg_confidence > 0.7 else 'Medium' if avg_confidence > 0.5 else 'Low'}

Recommendations:
1. {'Consider additional sources' if avg_confidence < 0.6 else 'Results are reliable'}
2. {'Focus on insights from ' + strongest_result.provider if strongest_result else 'Consider all perspectives'}
3. {'Verify key findings independently' if avg_confidence < 0.7 else 'Proceed with confidence'}
"""
    
    return local_analysis

@router.get("/providers")
async def get_available_providers():
    """Get list of available LLM providers for deep search"""
    return {
        "providers": [
            {"id": "openai", "name": "OpenAI GPT-4", "capabilities": ["text", "analysis", "reasoning"]},
            {"id": "gemini", "name": "Google Gemini", "capabilities": ["text", "multimodal", "reasoning"]},
            {"id": "claude", "name": "Anthropic Claude", "capabilities": ["text", "ethics", "reasoning"]},
            {"id": "grok", "name": "Grok AI", "capabilities": ["text", "innovation", "analysis"]},
            {"id": "deepseek", "name": "DeepSeek", "capabilities": ["text", "technical", "analysis"]}
        ],
        "search_depths": [
            {"id": "basic", "name": "Basic", "description": "Quick factual response"},
            {"id": "comprehensive", "name": "Comprehensive", "description": "Detailed analysis with multiple perspectives"},
            {"id": "expert", "name": "Expert", "description": "Expert-level insights with recommendations"}
        ]
    } 