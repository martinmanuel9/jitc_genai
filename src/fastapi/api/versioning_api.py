"""
Versioning API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from repositories.versioning_repository import (
    TestPlanRepository,
    TestPlanVersionRepository,
    TestCardRepository,
    TestCardVersionRepository,
    DocumentVersionRepository,
)
from models.versioning import TestPlan, TestPlanVersion, TestCard, TestCardVersion, DocumentVersion
from schemas.versioning import (
    CreateTestPlanRequest,
    UpdateTestPlanRequest,
    TestPlanResponse,
    TestPlanCreateResponse,
    TestPlanListResponse,
    CreateTestPlanVersionRequest,
    TestPlanVersionResponse,
    TestPlanVersionListResponse,
    UpdateVersionStatusRequest,
    CompareVersionsRequest,
    CompareVersionsResponse,
    CreateTestCardRequest,
    UpdateTestCardRequest,
    TestCardResponse,
    TestCardCreateResponse,
    TestCardListResponse,
    CreateTestCardVersionRequest,
    TestCardVersionResponse,
    TestCardVersionListResponse,
    CreateDocumentVersionRequest,
    DocumentVersionResponse,
    DocumentVersionListResponse,
    DeleteTestPlanResponse,
    DeleteVersionResponse,
)


router = APIRouter(
    prefix="/versioning",
    tags=["Versioning"]
)


# ---------------------------------------------------------------------------
# Test Plans
# ---------------------------------------------------------------------------

@router.get("/test-plans", response_model=TestPlanListResponse)
async def list_test_plans(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    repo = TestPlanRepository(db)
    plans = repo.get_all(skip=skip, limit=limit, order_by="created_at", order_desc=True)
    total = repo.count()
    return TestPlanListResponse(
        plans=[TestPlanResponse.from_orm(plan) for plan in plans],
        total_count=total
    )


@router.get("/test-plans/{plan_id}", response_model=TestPlanResponse)
async def get_test_plan(plan_id: int, db: Session = Depends(get_db)):
    repo = TestPlanRepository(db)
    plan = repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test plan not found")
    return TestPlanResponse.from_orm(plan)


@router.post("/test-plans", response_model=TestPlanCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_test_plan(request: CreateTestPlanRequest, db: Session = Depends(get_db)):
    plan_repo = TestPlanRepository(db)
    version_repo = TestPlanVersionRepository(db)

    existing = db.query(TestPlan).filter(TestPlan.plan_key == request.plan_key).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test plan already exists")

    plan_data = request.dict(exclude={"document_id", "based_on_version_id"})
    plan = plan_repo.create_from_dict(plan_data)

    version = version_repo.create_from_dict({
        "plan_id": plan.id,
        "version_number": 1,
        "document_id": request.document_id,
        "based_on_version_id": request.based_on_version_id
    })

    return TestPlanCreateResponse(
        plan=TestPlanResponse.from_orm(plan),
        version=TestPlanVersionResponse.from_orm(version)
    )


@router.put("/test-plans/{plan_id}", response_model=TestPlanResponse)
async def update_test_plan(
    plan_id: int,
    request: UpdateTestPlanRequest,
    db: Session = Depends(get_db)
):
    repo = TestPlanRepository(db)
    updates = request.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    plan = repo.update_by_id(plan_id, updates)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test plan not found")
    return TestPlanResponse.from_orm(plan)


@router.get("/test-plans/{plan_id}/versions", response_model=TestPlanVersionListResponse)
async def list_test_plan_versions(plan_id: int, db: Session = Depends(get_db)):
    repo = TestPlanVersionRepository(db)
    versions = (
        db.query(TestPlanVersion)
        .filter(TestPlanVersion.plan_id == plan_id)
        .order_by(TestPlanVersion.version_number.desc())
        .all()
    )
    return TestPlanVersionListResponse(
        versions=[TestPlanVersionResponse.from_orm(v) for v in versions],
        total_count=len(versions)
    )


@router.post("/test-plans/{plan_id}/versions", response_model=TestPlanVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_test_plan_version(
    plan_id: int,
    request: CreateTestPlanVersionRequest,
    db: Session = Depends(get_db)
):
    plan_repo = TestPlanRepository(db)
    version_repo = TestPlanVersionRepository(db)

    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test plan not found")

    if request.based_on_version_id:
        base_version = db.query(TestPlanVersion).filter(
            TestPlanVersion.id == request.based_on_version_id,
            TestPlanVersion.plan_id == plan_id
        ).first()
        if not base_version:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid based_on_version_id")

    next_version = version_repo.get_next_version_number(plan_id)
    version = version_repo.create_from_dict({
        "plan_id": plan_id,
        "version_number": next_version,
        "document_id": request.document_id,
        "based_on_version_id": request.based_on_version_id
    })

    return TestPlanVersionResponse.from_orm(version)


@router.patch("/test-plans/{plan_id}/versions/{version_id}/status", response_model=TestPlanVersionResponse)
async def update_version_status(
    plan_id: int,
    version_id: int,
    request: UpdateVersionStatusRequest,
    db: Session = Depends(get_db)
):
    """
    Update the status of a test plan version

    Business rules:
    - Cannot demote published versions to draft or final
    - Draft → Final → Published workflow
    """
    from models.versioning import VersionStatus

    version_repo = TestPlanVersionRepository(db)
    version = version_repo.get(version_id)

    if not version or version.plan_id != plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    # Business rule: Cannot demote published versions
    if hasattr(version, 'status'):
        current_status = version.status.value if hasattr(version.status, 'value') else str(version.status)
        if current_status == "published" and request.status.value != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote published version to draft or final"
            )

    # Update status
    updated = version_repo.update_by_id(version_id, {"status": request.status.value})
    return TestPlanVersionResponse.from_orm(updated)


@router.post("/test-plans/{plan_id}/versions/compare", response_model=CompareVersionsResponse)
async def compare_versions(
    plan_id: int,
    request: CompareVersionsRequest,
    db: Session = Depends(get_db)
):
    """
    Compare two versions and generate Was/Is diff

    Args:
        plan_id: Test plan ID
        request: Contains version_id_was and version_id_is

    Returns:
        Comparison results with differences and HTML preview
    """
    from services.version_comparison_service import VersionComparisonService

    try:
        comparison_service = VersionComparisonService(db)
        result = comparison_service.compare_versions(
            plan_id,
            request.version_id_was,
            request.version_id_is
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {str(e)}")


@router.get("/test-plans/{plan_id}/versions/{version_id_was}/export-comparison/{version_id_is}")
async def export_comparison_docx(
    plan_id: int,
    version_id_was: int,
    version_id_is: int,
    db: Session = Depends(get_db)
):
    """
    Export Was/Is comparison as DOCX with track changes

    Args:
        plan_id: Test plan ID
        version_id_was: Previous version ID
        version_id_is: Current version ID

    Returns:
        DOCX file with track changes formatting
    """
    from services.version_comparison_service import VersionComparisonService
    from fastapi.responses import StreamingResponse
    import io

    try:
        comparison_service = VersionComparisonService(db)
        docx_bytes = comparison_service.export_comparison_docx(
            plan_id, version_id_was, version_id_is
        )

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=comparison_v{version_id_was}_to_v{version_id_is}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {str(e)}")


# ---------------------------------------------------------------------------
# Test Cards
# ---------------------------------------------------------------------------

@router.get("/test-cards", response_model=TestCardListResponse)
async def list_test_cards(
    plan_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    repo = TestCardRepository(db)
    query = db.query(TestCard)
    if plan_id is not None:
        query = query.filter(TestCard.plan_id == plan_id)
    total = query.count()
    cards = (
        query.order_by(TestCard.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return TestCardListResponse(
        cards=[TestCardResponse.from_orm(card) for card in cards],
        total_count=total
    )


@router.get("/test-cards/{card_id}", response_model=TestCardResponse)
async def get_test_card(card_id: int, db: Session = Depends(get_db)):
    repo = TestCardRepository(db)
    card = repo.get(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test card not found")
    return TestCardResponse.from_orm(card)


@router.post("/test-cards", response_model=TestCardCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_test_card(request: CreateTestCardRequest, db: Session = Depends(get_db)):
    card_repo = TestCardRepository(db)
    version_repo = TestCardVersionRepository(db)

    existing = db.query(TestCard).filter(TestCard.card_key == request.card_key).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test card already exists")

    card_data = request.dict(exclude={"document_id", "based_on_version_id", "plan_version_id"})
    card = card_repo.create_from_dict(card_data)

    version = version_repo.create_from_dict({
        "card_id": card.id,
        "version_number": 1,
        "document_id": request.document_id,
        "plan_version_id": request.plan_version_id,
        "based_on_version_id": request.based_on_version_id
    })

    return TestCardCreateResponse(
        card=TestCardResponse.from_orm(card),
        version=TestCardVersionResponse.from_orm(version)
    )


@router.put("/test-cards/{card_id}", response_model=TestCardResponse)
async def update_test_card(
    card_id: int,
    request: UpdateTestCardRequest,
    db: Session = Depends(get_db)
):
    repo = TestCardRepository(db)
    updates = request.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    card = repo.update_by_id(card_id, updates)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test card not found")
    return TestCardResponse.from_orm(card)


@router.get("/test-cards/{card_id}/versions", response_model=TestCardVersionListResponse)
async def list_test_card_versions(card_id: int, db: Session = Depends(get_db)):
    versions = (
        db.query(TestCardVersion)
        .filter(TestCardVersion.card_id == card_id)
        .order_by(TestCardVersion.version_number.desc())
        .all()
    )
    return TestCardVersionListResponse(
        versions=[TestCardVersionResponse.from_orm(v) for v in versions],
        total_count=len(versions)
    )


@router.post("/test-cards/{card_id}/versions", response_model=TestCardVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_test_card_version(
    card_id: int,
    request: CreateTestCardVersionRequest,
    db: Session = Depends(get_db)
):
    card_repo = TestCardRepository(db)
    version_repo = TestCardVersionRepository(db)

    card = card_repo.get(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test card not found")

    if request.based_on_version_id:
        base_version = db.query(TestCardVersion).filter(
            TestCardVersion.id == request.based_on_version_id,
            TestCardVersion.card_id == card_id
        ).first()
        if not base_version:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid based_on_version_id")

    next_version = version_repo.get_next_version_number(card_id)
    version = version_repo.create_from_dict({
        "card_id": card_id,
        "version_number": next_version,
        "document_id": request.document_id,
        "plan_version_id": request.plan_version_id,
        "based_on_version_id": request.based_on_version_id
    })

    return TestCardVersionResponse.from_orm(version)


# ---------------------------------------------------------------------------
# Document Versions
# ---------------------------------------------------------------------------

@router.get("/documents/{document_key}", response_model=DocumentVersionListResponse)
async def list_document_versions(document_key: str, db: Session = Depends(get_db)):
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_key == document_key)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )
    return DocumentVersionListResponse(
        versions=[DocumentVersionResponse.from_orm(v) for v in versions],
        total_count=len(versions)
    )


@router.post("/documents", response_model=DocumentVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_document_version(request: CreateDocumentVersionRequest, db: Session = Depends(get_db)):
    repo = DocumentVersionRepository(db)

    if request.based_on_version_id:
        base_version = db.query(DocumentVersion).filter(
            DocumentVersion.id == request.based_on_version_id,
            DocumentVersion.document_key == request.document_key
        ).first()
        if not base_version:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid based_on_version_id")

    next_version = repo.get_next_version_number(request.document_key)
    version = repo.create_from_dict({
        "document_key": request.document_key,
        "document_id": request.document_id,
        "collection_name": request.collection_name,
        "document_name": request.document_name,
        "version_number": next_version,
        "based_on_version_id": request.based_on_version_id
    })

    return DocumentVersionResponse.from_orm(version)


# ---------------------------------------------------------------------------
# Delete Operations
# ---------------------------------------------------------------------------

@router.delete("/test-plans/{plan_id}", response_model=DeleteTestPlanResponse)
async def delete_test_plan(plan_id: int, db: Session = Depends(get_db)):
    """
    Delete a test plan and all its versions.

    This will:
    1. Delete all test plan versions from PostgreSQL
    2. Delete all associated ChromaDB documents
    3. Delete the test plan record

    Args:
        plan_id: ID of the test plan to delete

    Returns:
        DeleteTestPlanResponse with deletion statistics
    """
    from integrations.chromadb_client import get_chroma_client

    plan_repo = TestPlanRepository(db)
    version_repo = TestPlanVersionRepository(db)

    # Get the plan
    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test plan {plan_id} not found")

    # Get all versions for this plan
    versions = db.query(TestPlanVersion).filter(TestPlanVersion.plan_id == plan_id).all()
    collection_name = plan.collection_name or "test_plan_drafts"

    # Delete ChromaDB documents for all versions
    chromadb_deleted = 0
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(collection_name)

        for version in versions:
            # Find all documents for this version
            result = collection.get(where={"version_id": str(version.id)})
            if result and result.get("ids"):
                collection.delete(ids=result["ids"])
                chromadb_deleted += len(result["ids"])

    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Failed to delete some ChromaDB documents: {e}")

    # Delete all versions from PostgreSQL (cascade will handle this, but being explicit)
    versions_count = len(versions)
    for version in versions:
        version_repo.delete(version)

    # Delete the test plan (cascade delete will also remove versions)
    plan_repo.delete(plan)

    return DeleteTestPlanResponse(
        success=True,
        message=f"Test plan '{plan.title}' deleted successfully",
        plan_id=plan_id,
        versions_deleted=versions_count,
        chromadb_documents_deleted=chromadb_deleted
    )


@router.delete("/test-plans/{plan_id}/versions/{version_id}", response_model=DeleteVersionResponse)
async def delete_test_plan_version(plan_id: int, version_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific test plan version.

    This will:
    1. Delete the version from PostgreSQL
    2. Delete associated ChromaDB documents

    Args:
        plan_id: ID of the test plan
        version_id: ID of the version to delete

    Returns:
        DeleteVersionResponse with deletion statistics
    """
    from integrations.chromadb_client import get_chroma_client

    plan_repo = TestPlanRepository(db)
    version_repo = TestPlanVersionRepository(db)

    # Get the plan
    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test plan {plan_id} not found")

    # Get the version
    version = version_repo.get(version_id)
    if not version or version.plan_id != plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {version_id} not found for plan {plan_id}")

    collection_name = plan.collection_name or "test_plan_drafts"

    # Delete ChromaDB documents for this version
    chromadb_deleted = 0
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(collection_name)

        # Find all documents for this version
        result = collection.get(where={"version_id": str(version_id)})
        if result and result.get("ids"):
            collection.delete(ids=result["ids"])
            chromadb_deleted = len(result["ids"])

    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Failed to delete some ChromaDB documents: {e}")

    # Delete the version from PostgreSQL
    version_repo.delete(version)

    return DeleteVersionResponse(
        success=True,
        message=f"Version {version.version_number} deleted successfully",
        version_id=version_id,
        chromadb_documents_deleted=chromadb_deleted
    )
