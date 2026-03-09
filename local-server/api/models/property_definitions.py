"""
Pydantic models for Property Definitions (new terminology).

These models replace the old "Predicate" terminology with "PropertyDefinition"
while maintaining the same database structure.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class PropertyDefinitionBase(BaseModel):
    """Base model for property definition fields."""
    title: str = Field(..., min_length=1, max_length=255)
    definition: Optional[str] = None
    mapping: Optional[dict] = None


class PropertyDefinitionCreate(PropertyDefinitionBase):
    """Model for creating a new property definition."""
    identifier: Optional[str] = None


class PropertyDefinitionUpdate(BaseModel):
    """Model for updating a property definition."""
    title: Optional[str] = None
    definition: Optional[str] = None
    mapping: Optional[dict] = None
    identifier: Optional[str] = None


class PropertyDefinitionOut(PropertyDefinitionBase):
    """Model for property definition API response."""
    id: str
    identifier: str
    date_created: str
    date_modified: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedPropertyDefinitionsResponse(BaseModel):
    """Model for paginated property definitions response."""
    data: List[PropertyDefinitionOut]
    total: int
    skip: int
    limit: int
