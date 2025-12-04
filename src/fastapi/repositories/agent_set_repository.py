"""
Agent Set Repository

Data access layer for agent set database operations.
Provides CRUD operations and queries for AgentSet model.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone

from models.agent_set import AgentSet
from core.exceptions import DatabaseException


class AgentSetRepository:
    """Repository for agent set database operations"""

    def get_all(
        self,
        session: Session,
        include_inactive: bool = False
    ) -> List[AgentSet]:
        """
        Get all agent sets.

        Args:
            session: Database session
            include_inactive: Include inactive sets

        Returns:
            List of AgentSet objects
        """
        query = session.query(AgentSet)

        if not include_inactive:
            query = query.filter(AgentSet.is_active == True)

        return query.order_by(
            AgentSet.usage_count.desc(),
            AgentSet.created_at
        ).all()

    def get_by_id(
        self,
        set_id: int,
        session: Session
    ) -> Optional[AgentSet]:
        """
        Get agent set by ID.

        Args:
            set_id: Agent set ID
            session: Database session

        Returns:
            AgentSet or None
        """
        return session.query(AgentSet).filter(
            AgentSet.id == set_id
        ).first()

    def get_by_name(
        self,
        name: str,
        session: Session
    ) -> Optional[AgentSet]:
        """
        Get agent set by name.

        Args:
            name: Set name
            session: Database session

        Returns:
            AgentSet or None
        """
        return session.query(AgentSet).filter(
            AgentSet.name == name
        ).first()

    def get_by_type(
        self,
        set_type: str,
        session: Session,
        include_inactive: bool = False
    ) -> List[AgentSet]:
        """
        Get all sets of a specific type.

        Args:
            set_type: Type of set (sequence, parallel, custom)
            session: Database session
            include_inactive: Include inactive sets

        Returns:
            List of AgentSet objects
        """
        query = session.query(AgentSet).filter(
            AgentSet.set_type == set_type
        )

        if not include_inactive:
            query = query.filter(AgentSet.is_active == True)

        return query.order_by(AgentSet.created_at).all()

    def get_default_sets(
        self,
        session: Session,
        set_type: Optional[str] = None
    ) -> List[AgentSet]:
        """
        Get system default agent sets.

        Args:
            session: Database session
            set_type: Optional filter by set type

        Returns:
            List of default AgentSet objects
        """
        query = session.query(AgentSet).filter(
            AgentSet.is_system_default == True,
            AgentSet.is_active == True
        )

        if set_type:
            query = query.filter(AgentSet.set_type == set_type)

        return query.order_by(AgentSet.usage_count.desc()).all()

    def get_user_created_sets(
        self,
        session: Session,
        set_type: Optional[str] = None
    ) -> List[AgentSet]:
        """
        Get user-created (non-default) agent sets.

        Args:
            session: Database session
            set_type: Optional filter by set type

        Returns:
            List of user-created AgentSet objects
        """
        query = session.query(AgentSet).filter(
            AgentSet.is_system_default == False,
            AgentSet.is_active == True
        )

        if set_type:
            query = query.filter(AgentSet.set_type == set_type)

        return query.order_by(AgentSet.created_at.desc()).all()

    def get_most_used_sets(
        self,
        session: Session,
        limit: int = 10
    ) -> List[AgentSet]:
        """
        Get most frequently used agent sets.

        Args:
            session: Database session
            limit: Maximum number of sets to return

        Returns:
            List of AgentSet objects ordered by usage count
        """
        return session.query(AgentSet).filter(
            AgentSet.is_active == True
        ).order_by(
            AgentSet.usage_count.desc()
        ).limit(limit).all()

    def create(
        self,
        set_data: Dict[str, Any],
        session: Session
    ) -> AgentSet:
        """
        Create a new agent set.

        Args:
            set_data: Dictionary with set data
            session: Database session

        Returns:
            Created AgentSet

        Raises:
            DatabaseException: If creation fails
        """
        try:
            # Check for duplicate name
            existing = self.get_by_name(set_data.get('name'), session)
            if existing:
                raise ValueError(f"Agent set with name '{set_data.get('name')}' already exists")

            agent_set = AgentSet(**set_data)
            session.add(agent_set)
            session.commit()
            session.refresh(agent_set)
            return agent_set

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to create agent set: {str(e)}") from e

    def update(
        self,
        set_id: int,
        set_data: Dict[str, Any],
        session: Session
    ) -> AgentSet:
        """
        Update an existing agent set.

        Args:
            set_id: Agent set ID
            set_data: Dictionary with updated data
            session: Database session

        Returns:
            Updated AgentSet

        Raises:
            DatabaseException: If update fails
        """
        try:
            agent_set = self.get_by_id(set_id, session)
            if not agent_set:
                raise ValueError(f"Agent set with ID {set_id} not found")

            # Check for name conflict if name is being changed
            if 'name' in set_data and set_data['name'] != agent_set.name:
                existing = self.get_by_name(set_data['name'], session)
                if existing:
                    raise ValueError(f"Agent set with name '{set_data['name']}' already exists")

            # Update fields
            for key, value in set_data.items():
                if hasattr(agent_set, key):
                    setattr(agent_set, key, value)

            # Explicitly update timestamp
            agent_set.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(agent_set)
            return agent_set

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to update agent set: {str(e)}") from e

    def delete(
        self,
        set_id: int,
        session: Session,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete an agent set.

        Args:
            set_id: Agent set ID
            session: Database session
            soft_delete: If True, mark as inactive; if False, permanently delete

        Returns:
            True if successful

        Raises:
            DatabaseException: If deletion fails
        """
        try:
            agent_set = self.get_by_id(set_id, session)
            if not agent_set:
                raise ValueError(f"Agent set with ID {set_id} not found")

            # Prevent deletion of system default sets (both soft and hard delete)
            if agent_set.is_system_default:
                raise ValueError("Cannot delete system default agent sets. System defaults are protected.")

            if soft_delete:
                agent_set.is_active = False
                agent_set.updated_at = datetime.now(timezone.utc)
                session.commit()
            else:
                session.delete(agent_set)
                session.commit()

            return True

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to delete agent set: {str(e)}") from e

    def activate(
        self,
        set_id: int,
        session: Session
    ) -> AgentSet:
        """
        Activate a deactivated agent set.

        Args:
            set_id: Agent set ID
            session: Database session

        Returns:
            Activated AgentSet

        Raises:
            DatabaseException: If activation fails
        """
        try:
            agent_set = self.get_by_id(set_id, session)
            if not agent_set:
                raise ValueError(f"Agent set with ID {set_id} not found")

            agent_set.is_active = True
            agent_set.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(agent_set)
            return agent_set

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to activate agent set: {str(e)}") from e

    def increment_usage_count(
        self,
        set_id: int,
        session: Session
    ) -> AgentSet:
        """
        Increment usage count for an agent set.

        Args:
            set_id: Agent set ID
            session: Database session

        Returns:
            Updated AgentSet

        Raises:
            DatabaseException: If increment fails
        """
        try:
            agent_set = self.get_by_id(set_id, session)
            if not agent_set:
                raise ValueError(f"Agent set with ID {set_id} not found")

            agent_set.usage_count += 1
            agent_set.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(agent_set)
            return agent_set

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to increment usage count: {str(e)}") from e

    def search(
        self,
        search_term: str,
        session: Session,
        set_type: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[AgentSet]:
        """
        Search agent sets by name or description.

        Args:
            search_term: Search term
            session: Database session
            set_type: Optional filter by set type
            include_inactive: Include inactive sets

        Returns:
            List of matching AgentSet objects
        """
        query = session.query(AgentSet).filter(
            or_(
                AgentSet.name.ilike(f"%{search_term}%"),
                AgentSet.description.ilike(f"%{search_term}%")
            )
        )

        if set_type:
            query = query.filter(AgentSet.set_type == set_type)

        if not include_inactive:
            query = query.filter(AgentSet.is_active == True)

        return query.order_by(AgentSet.created_at.desc()).all()

    def clone_set(
        self,
        set_id: int,
        new_name: str,
        session: Session,
        created_by: Optional[str] = None
    ) -> AgentSet:
        """
        Clone an existing agent set with a new name.

        Args:
            set_id: Source set ID
            new_name: Name for cloned set
            session: Database session
            created_by: User creating the clone

        Returns:
            Cloned AgentSet

        Raises:
            DatabaseException: If cloning fails
        """
        try:
            source_set = self.get_by_id(set_id, session)
            if not source_set:
                raise ValueError(f"Agent set with ID {set_id} not found")

            # Check for name conflict
            if self.get_by_name(new_name, session):
                raise ValueError(f"Agent set with name '{new_name}' already exists")

            # Create clone
            clone_data = {
                'name': new_name,
                'description': f"Cloned from: {source_set.name}",
                'set_type': source_set.set_type,
                'set_config': source_set.set_config,
                'is_system_default': False,  # Clones are never system defaults
                'is_active': True,
                'usage_count': 0,  # Reset usage count
                'created_by': created_by
            }

            return self.create(clone_data, session)

        except ValueError as e:
            raise DatabaseException(str(e)) from e
        except Exception as e:
            raise DatabaseException(f"Failed to clone agent set: {str(e)}") from e

    def get_sets_using_agent(
        self,
        agent_id: int,
        session: Session,
        include_inactive: bool = False
    ) -> List[AgentSet]:
        """
        Find all agent sets that use a specific agent.

        Args:
            agent_id: Agent ID to search for
            session: Database session
            include_inactive: Include inactive sets

        Returns:
            List of AgentSet objects using the specified agent
        """
        query = session.query(AgentSet)

        if not include_inactive:
            query = query.filter(AgentSet.is_active == True)

        all_sets = query.all()

        # Filter sets that contain the agent_id in their configuration
        matching_sets = []
        for agent_set in all_sets:
            if 'stages' in agent_set.set_config:
                for stage in agent_set.set_config['stages']:
                    if agent_id in stage.get('agent_ids', []):
                        matching_sets.append(agent_set)
                        break

        return matching_sets
