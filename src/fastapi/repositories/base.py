"""
Base repository with generic CRUD operations.

This module provides a generic BaseRepository class that implements
common database operations (Create, Read, Update, Delete) for any SQLAlchemy model.
All domain-specific repositories should extend this base class.
"""

from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from models.base import Base
from core.exceptions import NotFoundException, DatabaseException


# Generic type bound to SQLAlchemy Base
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic base repository with CRUD operations.

    This class provides standard database operations that can be inherited
    by all domain-specific repositories.

    Type Parameters:
        ModelType: The SQLAlchemy model type this repository manages

    Example:
        class AgentRepository(BaseRepository[ComplianceAgent]):
            def __init__(self, db: Session):
                super().__init__(ComplianceAgent, db)

            def get_by_name(self, name: str) -> Optional[ComplianceAgent]:
                return self.db.query(self.model).filter(
                    self.model.name == name
                ).first()
    """

    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            db: SQLAlchemy database session
        """
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        try:
            return self.db.query(self.model).filter(self.model.id == id).first()
        except Exception as e:
            raise DatabaseException(f"Failed to get {self.model.__name__} with id {id}") from e

    def get_or_fail(self, id: int) -> ModelType:
        """
        Get a single record by ID or raise exception.

        Args:
            id: Primary key value

        Returns:
            Model instance

        Raises:
            NotFoundException: If record not found
        """
        obj = self.get(id)
        if obj is None:
            raise NotFoundException(self.model.__name__, id)
        return obj

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = True
    ) -> List[ModelType]:
        """
        Get all records with pagination and sorting.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            order_by: Field name to order by
            order_desc: Whether to order descending (default: True)

        Returns:
            List of model instances
        """
        try:
            query = self.db.query(self.model)

            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                query = query.order_by(desc(order_column) if order_desc else asc(order_column))

            return query.offset(skip).limit(limit).all()
        except Exception as e:
            raise DatabaseException(f"Failed to get all {self.model.__name__}") from e

    def get_by_filter(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = True
    ) -> List[ModelType]:
        """
        Get records matching filters.

        Args:
            filters: Dictionary of field names and values to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field name to order by
            order_desc: Whether to order descending

        Returns:
            List of model instances matching filters
        """
        try:
            query = self.db.query(self.model)

            # Apply filters
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                query = query.order_by(desc(order_column) if order_desc else asc(order_column))

            return query.offset(skip).limit(limit).all()
        except Exception as e:
            raise DatabaseException(f"Failed to filter {self.model.__name__}") from e

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records, optionally with filters.

        Args:
            filters: Optional dictionary of filters

        Returns:
            Count of matching records
        """
        try:
            query = self.db.query(self.model)

            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)

            return query.count()
        except Exception as e:
            raise DatabaseException(f"Failed to count {self.model.__name__}") from e

    def create(self, obj: ModelType) -> ModelType:
        """
        Create a new record.

        Args:
            obj: Model instance to create

        Returns:
            Created model instance with ID populated
        """
        try:
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)
            return obj
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Failed to create {self.model.__name__}") from e

    def create_from_dict(self, data: Dict[str, Any]) -> ModelType:
        """
        Create a new record from dictionary.

        Args:
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        try:
            obj = self.model(**data)
            return self.create(obj)
        except Exception as e:
            raise DatabaseException(f"Failed to create {self.model.__name__} from dict") from e

    def update(self, obj: ModelType) -> ModelType:
        """
        Update an existing record.

        Args:
            obj: Model instance with updated values

        Returns:
            Updated model instance
        """
        try:
            self.db.commit()
            self.db.refresh(obj)
            return obj
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Failed to update {self.model.__name__}") from e

    def update_by_id(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by ID with partial data.

        Args:
            id: Primary key value
            data: Dictionary of fields to update

        Returns:
            Updated model instance or None if not found
        """
        try:
            obj = self.get(id)
            if obj is None:
                return None

            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)

            return self.update(obj)
        except Exception as e:
            raise DatabaseException(f"Failed to update {self.model.__name__} by id") from e

    def delete(self, obj: ModelType) -> bool:
        """
        Delete a record.

        Args:
            obj: Model instance to delete

        Returns:
            True if successful
        """
        try:
            self.db.delete(obj)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Failed to delete {self.model.__name__}") from e

    def delete_by_id(self, id: int) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Primary key value

        Returns:
            True if deleted, False if not found
        """
        try:
            obj = self.get(id)
            if obj is None:
                return False

            return self.delete(obj)
        except Exception as e:
            raise DatabaseException(f"Failed to delete {self.model.__name__} by id") from e

    def exists(self, id: int) -> bool:
        """
        Check if a record exists.

        Args:
            id: Primary key value

        Returns:
            True if exists, False otherwise
        """
        try:
            return self.db.query(self.model).filter(self.model.id == id).count() > 0
        except Exception as e:
            raise DatabaseException(f"Failed to check existence of {self.model.__name__}") from e

    def bulk_create(self, objects: List[ModelType]) -> List[ModelType]:
        """
        Create multiple records in bulk.

        Args:
            objects: List of model instances to create

        Returns:
            List of created instances
        """
        try:
            self.db.bulk_save_objects(objects, return_defaults=True)
            self.db.commit()
            return objects
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Failed to bulk create {self.model.__name__}") from e

    def refresh(self, obj: ModelType) -> ModelType:
        """
        Refresh an object from the database.

        Args:
            obj: Model instance to refresh

        Returns:
            Refreshed model instance
        """
        try:
            self.db.refresh(obj)
            return obj
        except Exception as e:
            raise DatabaseException(f"Failed to refresh {self.model.__name__}") from e
