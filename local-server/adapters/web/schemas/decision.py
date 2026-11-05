"""
Pydantic schemas for the decision-model routes.
"""

from typing import Optional

from pydantic import BaseModel, Field

from domain.decision.value_objects import DecisionModelInfo


class DecisionModelResponse(BaseModel):
    """A configured decision-model instance. Credentials are never included."""

    name: str = Field(description="Instance name from config.json")
    adapter: str = Field(description="Adapter serving the instance, e.g. 'workers_ai' or 'llm'")
    model: str = Field(description="Model id the adapter calls")
    configured: bool = Field(description="Whether the instance has what it needs to make a call")
    is_default: bool = Field(description="Whether callers get this instance when naming none")
    fallback: Optional[str] = Field(
        default=None, description="Instance used when this one is unconfigured or fails"
    )
    price_per_mtok_in: Optional[float] = Field(
        default=None, description="USD per million input tokens, when configured"
    )

    @classmethod
    def from_domain(cls, info: DecisionModelInfo) -> "DecisionModelResponse":
        return cls(
            name=info.name,
            adapter=info.adapter,
            model=info.model,
            configured=info.configured,
            is_default=info.is_default,
            fallback=info.fallback,
            price_per_mtok_in=info.price_per_mtok_in,
        )


class DecisionModelListResponse(BaseModel):
    """Every configured decision-model instance and the default's name."""

    default: Optional[str] = Field(default=None, description="Default instance name")
    models: list[DecisionModelResponse]
