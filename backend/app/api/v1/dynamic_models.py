"""Dynamic model provisioning endpoints.

Allows runtime addition/removal of LLM providers without restart.
Bridges the Connections page (where users add API keys) with the
live ModelRegistry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_role
from app.services.dynamic_model_service import DynamicModelService

router = APIRouter()


def get_dynamic_model_service(request: Request) -> DynamicModelService:
    """Get DynamicModelService from app state."""
    registry = request.app.state.model_registry
    return DynamicModelService(registry)


class ProvisionRequest(BaseModel):
    """Request to add a new LLM provider at runtime."""

    provider_name: str = Field(
        ..., description="Provider name: anthropic, openai, google_gemini, groq, etc."
    )
    api_key: str = Field(..., min_length=1, description="API key for the provider")


class ProvisionResponse(BaseModel):
    """Result of provisioning attempt."""

    provider: str
    success: bool
    models_discovered: int = 0
    health: str = "UNAVAILABLE"
    error: str | None = None
    model_ids: list[str] = []


class RemoveRequest(BaseModel):
    """Request to remove a provider from the live registry."""

    provider_name: str


@router.post("/provision", response_model=ProvisionResponse)
async def provision_provider(
    body: ProvisionRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    svc: DynamicModelService = Depends(get_dynamic_model_service),
) -> ProvisionResponse:
    """Add a new LLM provider at runtime.

    Validates the API key, registers the provider, and discovers models.
    ADMIN+ role required.
    """
    result = await svc.provision_provider(
        provider_name=body.provider_name,
        api_key=body.api_key,
    )
    return ProvisionResponse(
        provider=result.provider.value,
        success=result.success,
        models_discovered=result.models_discovered,
        health=result.health,
        error=result.error,
        model_ids=result.model_ids,
    )


@router.post("/remove")
async def remove_provider(
    body: RemoveRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    svc: DynamicModelService = Depends(get_dynamic_model_service),
) -> dict:
    """Remove a dynamically added provider from the live registry.

    ADMIN+ role required.
    """
    removed = await svc.remove_provider(body.provider_name)
    return {"success": removed, "data": {"removed": removed}}


@router.get("/provisionable")
async def list_provisionable(
    user: CurrentUser = Depends(require_role("ADMIN")),
    svc: DynamicModelService = Depends(get_dynamic_model_service),
) -> dict:
    """List all providers available for dynamic provisioning."""
    providers = svc.list_provisionable()
    return {"success": True, "data": providers}


@router.post("/refresh/{provider_name}")
async def refresh_provider(
    provider_name: str,
    user: CurrentUser = Depends(require_role("ADMIN")),
    svc: DynamicModelService = Depends(get_dynamic_model_service),
) -> dict:
    """Re-check health and re-discover models for an active provider."""
    result = await svc.refresh_provider(provider_name)
    return {
        "success": result.success,
        "data": {
            "provider": result.provider.value,
            "models_discovered": result.models_discovered,
            "health": result.health,
            "error": result.error,
            "model_ids": result.model_ids,
        },
    }
