"""
Versioning Pydantic Schemas
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class VersionStatusEnum(str, Enum):
    """Version status enumeration"""
    DRAFT = "draft"
    FINAL = "final"
    PUBLISHED = "published"


# ---------------------------------------------------------------------------
# Test Plan Schemas
# ---------------------------------------------------------------------------

class TestPlanBase(BaseModel):
    plan_key: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    collection_name: Optional[str] = Field(None, max_length=255)
    percent_complete: float = Field(0, ge=0, le=100)


class CreateTestPlanRequest(TestPlanBase):
    document_id: str = Field(..., min_length=1, max_length=255)
    based_on_version_id: Optional[int] = None


class UpdateTestPlanRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    collection_name: Optional[str] = Field(None, max_length=255)
    percent_complete: Optional[float] = Field(None, ge=0, le=100)


class TestPlanResponse(TestPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CreateTestPlanVersionRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=255)
    based_on_version_id: Optional[int] = None


class TestPlanVersionResponse(BaseModel):
    id: int
    plan_id: int
    version_number: int
    document_id: str
    based_on_version_id: Optional[int]
    created_at: datetime
    status: str = "draft"
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TestPlanCreateResponse(BaseModel):
    plan: TestPlanResponse
    version: TestPlanVersionResponse


class TestPlanListResponse(BaseModel):
    plans: List[TestPlanResponse]
    total_count: int


class TestPlanVersionListResponse(BaseModel):
    versions: List[TestPlanVersionResponse]
    total_count: int


class UpdateVersionStatusRequest(BaseModel):
    """Request to update version status"""
    status: VersionStatusEnum


class CompareVersionsRequest(BaseModel):
    """Request to compare two versions"""
    version_id_was: int = Field(..., description="Previous version ID (base)")
    version_id_is: int = Field(..., description="Current version ID (comparison)")


class VersionDiff(BaseModel):
    """Represents a single change between versions"""
    section_id: str
    section_title: str
    field: str = Field(..., description="Field name (e.g., 'synthesized_rules', 'test_procedures')")
    change_type: str = Field(..., description="Change type: 'added', 'deleted', 'modified'")
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class CompareVersionsResponse(BaseModel):
    """Response with version comparison results"""
    was_version: Dict[str, Any] = Field(..., description="Previous version metadata")
    is_version: Dict[str, Any] = Field(..., description="Current version metadata")
    differences: List[VersionDiff] = Field(..., description="List of differences")
    total_changes: int = Field(..., description="Total number of changes")
    html_preview: str = Field(..., description="HTML preview with track changes styling")


# ---------------------------------------------------------------------------
# Test Card Schemas
# ---------------------------------------------------------------------------

class TestCardBase(BaseModel):
    card_key: str = Field(..., min_length=1, max_length=255)
    plan_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    requirement_id: Optional[str] = Field(None, max_length=255)
    percent_complete: float = Field(0, ge=0, le=100)


class CreateTestCardRequest(TestCardBase):
    document_id: str = Field(..., min_length=1, max_length=255)
    based_on_version_id: Optional[int] = None
    plan_version_id: Optional[int] = None


class UpdateTestCardRequest(BaseModel):
    plan_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    requirement_id: Optional[str] = Field(None, max_length=255)
    percent_complete: Optional[float] = Field(None, ge=0, le=100)


class TestCardResponse(TestCardBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CreateTestCardVersionRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=255)
    based_on_version_id: Optional[int] = None
    plan_version_id: Optional[int] = None


class TestCardVersionResponse(BaseModel):
    id: int
    card_id: int
    version_number: int
    document_id: str
    plan_version_id: Optional[int]
    based_on_version_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TestCardCreateResponse(BaseModel):
    card: TestCardResponse
    version: TestCardVersionResponse


class TestCardListResponse(BaseModel):
    cards: List[TestCardResponse]
    total_count: int


class TestCardVersionListResponse(BaseModel):
    versions: List[TestCardVersionResponse]
    total_count: int


# ---------------------------------------------------------------------------
# Document Version Schemas
# ---------------------------------------------------------------------------

class CreateDocumentVersionRequest(BaseModel):
    document_key: str = Field(..., min_length=1, max_length=255)
    document_id: str = Field(..., min_length=1, max_length=255)
    collection_name: str = Field(..., min_length=1, max_length=255)
    document_name: Optional[str] = Field(None, max_length=255)
    based_on_version_id: Optional[int] = None


class DocumentVersionResponse(BaseModel):
    id: int
    document_key: str
    document_id: str
    collection_name: str
    document_name: Optional[str]
    version_number: int
    based_on_version_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentVersionListResponse(BaseModel):
    versions: List[DocumentVersionResponse]
    total_count: int


# ---------------------------------------------------------------------------
# Delete Responses
# ---------------------------------------------------------------------------

class DeleteTestPlanResponse(BaseModel):
    """Response for test plan deletion"""
    success: bool
    message: str
    plan_id: int
    versions_deleted: int
    chromadb_documents_deleted: int


class DeleteVersionResponse(BaseModel):
    """Response for version deletion"""
    success: bool
    message: str
    version_id: int
    chromadb_documents_deleted: int
