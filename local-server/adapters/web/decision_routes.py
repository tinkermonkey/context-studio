"""
HTTP routes for decision models.

Endpoints:
- GET /api/decision-models - List configured decision-model instances (no credentials)
"""

from fastapi import APIRouter, Depends

from adapters.web.dependencies import get_decision_models
from adapters.web.schemas.decision import DecisionModelListResponse, DecisionModelResponse
from domain.decision.ports import DecisionModels

router = APIRouter(prefix="/api/decision-models", tags=["decision-models"])


@router.get("", response_model=DecisionModelListResponse)
async def list_decision_models(
    decision_models: DecisionModels = Depends(get_decision_models),
) -> DecisionModelListResponse:
    """List the configured decision-model instances: name, adapter, model, configured."""
    infos = decision_models.describe()
    default = next((info.name for info in infos if info.is_default), None)
    return DecisionModelListResponse(
        default=default,
        models=[DecisionModelResponse.from_domain(info) for info in infos],
    )
