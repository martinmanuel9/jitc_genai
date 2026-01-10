"""
Versioning Repository

Data access layer for test plans, test cards, and document versions.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.versioning import (
    TestPlan,
    TestPlanVersion,
    TestCard,
    TestCardVersion,
    DocumentVersion,
)
from repositories.base import BaseRepository


class TestPlanRepository(BaseRepository[TestPlan]):
    """Repository for test plan records."""

    def __init__(self, db: Session):
        super().__init__(TestPlan, db)


class TestPlanVersionRepository(BaseRepository[TestPlanVersion]):
    """Repository for test plan version records."""

    def __init__(self, db: Session):
        super().__init__(TestPlanVersion, db)

    def get_next_version_number(self, plan_id: int) -> int:
        current = (
            self.db.query(func.max(TestPlanVersion.version_number))
            .filter(TestPlanVersion.plan_id == plan_id)
            .scalar()
        )
        return (current or 0) + 1


class TestCardRepository(BaseRepository[TestCard]):
    """Repository for test card records."""

    def __init__(self, db: Session):
        super().__init__(TestCard, db)


class TestCardVersionRepository(BaseRepository[TestCardVersion]):
    """Repository for test card version records."""

    def __init__(self, db: Session):
        super().__init__(TestCardVersion, db)

    def get_next_version_number(self, card_id: int) -> int:
        current = (
            self.db.query(func.max(TestCardVersion.version_number))
            .filter(TestCardVersion.card_id == card_id)
            .scalar()
        )
        return (current or 0) + 1


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """Repository for document version records."""

    def __init__(self, db: Session):
        super().__init__(DocumentVersion, db)

    def get_next_version_number(self, document_key: str) -> int:
        current = (
            self.db.query(func.max(DocumentVersion.version_number))
            .filter(DocumentVersion.document_key == document_key)
            .scalar()
        )
        return (current or 0) + 1
