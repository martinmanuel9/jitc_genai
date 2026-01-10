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
