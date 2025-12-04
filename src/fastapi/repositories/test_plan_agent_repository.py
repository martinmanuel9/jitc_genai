"""
Test Plan Agent Repository

Data access layer for test plan agent database operations.
Provides CRUD operations and queries for test plan agents using the unified ComplianceAgent model.

Note: This repository now uses the ComplianceAgent table (unified architecture).
The old TestPlanAgent model and test_plan_agents table are deprecated.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone

from models.agent import ComplianceAgent
from core.exceptions import DatabaseException

# Type alias for backward compatibility
TestPlanAgent = ComplianceAgent


class TestPlanAgentRepository:
    """Repository for test plan agent database operations"""

    def get_all(
        self,
        session: Session,
        include_inactive: bool = False
    ) -> List[ComplianceAgent]:
        """
        Get all test plan agents.

        Args:
            session: Database session
            include_inactive: Include inactive agents

        Returns:
            List of ComplianceAgent objects
        """
        query = session.query(ComplianceAgent)

        if not include_inactive:
            query = query.filter(ComplianceAgent.is_active == True)

        return query.order_by(
            ComplianceAgent.agent_type,
            ComplianceAgent.created_at
        ).all()

    def get_by_id(
        self,
        agent_id: int,
        session: Session
    ) -> Optional[ComplianceAgent]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent ID
            session: Database session

        Returns:
            ComplianceAgent or None
        """
        return session.query(ComplianceAgent).filter(
            ComplianceAgent.id == agent_id
        ).first()

    def get_by_name(
        self,
        name: str,
        session: Session
    ) -> Optional[ComplianceAgent]:
        """
        Get agent by name.

        Args:
            name: Agent name
            session: Database session

        Returns:
            ComplianceAgent or None
        """
        return session.query(ComplianceAgent).filter(
            ComplianceAgent.name == name
        ).first()

    def get_by_type(
        self,
        agent_type: str,
        session: Session,
        include_inactive: bool = False
    ) -> List[ComplianceAgent]:
        """
        Get all agents of a specific type.

        Args:
            agent_type: Type of agent (actor, critic, contradiction, gap_analysis)
            session: Database session
            include_inactive: Include inactive agents

        Returns:
            List of ComplianceAgent objects
        """
        query = session.query(ComplianceAgent).filter(
            ComplianceAgent.agent_type == agent_type
        )

        if not include_inactive:
            query = query.filter(ComplianceAgent.is_active == True)

        return query.order_by(ComplianceAgent.created_at).all()

    def get_default_agents(
        self,
        session: Session,
        agent_type: Optional[str] = None
    ) -> List[ComplianceAgent]:
        """
        Get system default agents.

        Args:
            session: Database session
            agent_type: Optional filter by agent type

        Returns:
            List of default ComplianceAgent objects
        """
        query = session.query(ComplianceAgent).filter(
            ComplianceAgent.is_system_default == True,
            ComplianceAgent.is_active == True
        )

        if agent_type:
            query = query.filter(ComplianceAgent.agent_type == agent_type)

        return query.order_by(ComplianceAgent.agent_type).all()

    def get_user_created_agents(
        self,
        session: Session,
        agent_type: Optional[str] = None
    ) -> List[ComplianceAgent]:
        """
        Get user-created (non-default) agents.

        Args:
            session: Database session
            agent_type: Optional filter by agent type

        Returns:
            List of user-created ComplianceAgent objects
        """
        query = session.query(ComplianceAgent).filter(
            ComplianceAgent.is_system_default == False,
            ComplianceAgent.is_active == True
        )

        if agent_type:
            query = query.filter(ComplianceAgent.agent_type == agent_type)

        return query.order_by(ComplianceAgent.created_at.desc()).all()

    def create(
        self,
        agent_data: Dict[str, Any],
        session: Session
    ) -> ComplianceAgent:
        """
        Create a new test plan agent.

        Args:
            agent_data: Dictionary with agent data
            session: Database session

        Returns:
            Created ComplianceAgent

        Raises:
            DatabaseException: If creation fails
        """
        try:
            # Check for duplicate name
            existing = self.get_by_name(agent_data.get('name'), session)
            if existing:
                raise ValueError(f"Agent with name '{agent_data.get('name')}' already exists")

            agent = ComplianceAgent(**agent_data)
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return agent

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to create agent: {str(e)}") from e

    def update(
        self,
        agent_id: int,
        agent_data: Dict[str, Any],
        session: Session
    ) -> ComplianceAgent:
        """
        Update an existing test plan agent.

        Args:
            agent_id: Agent ID
            agent_data: Dictionary with updated data
            session: Database session

        Returns:
            Updated ComplianceAgent

        Raises:
            DatabaseException: If update fails
        """
        try:
            agent = self.get_by_id(agent_id, session)
            if not agent:
                raise ValueError(f"Agent with ID {agent_id} not found")

            # Check for name conflict if name is being changed
            if 'name' in agent_data and agent_data['name'] != agent.name:
                existing = self.get_by_name(agent_data['name'], session)
                if existing:
                    raise ValueError(f"Agent with name '{agent_data['name']}' already exists")

            # Update fields
            for key, value in agent_data.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)

            # Explicitly update timestamp
            agent.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(agent)
            return agent

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to update agent: {str(e)}") from e

    def delete(
        self,
        agent_id: int,
        session: Session,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete a test plan agent.

        Args:
            agent_id: Agent ID
            session: Database session
            soft_delete: If True, mark as inactive; if False, permanently delete

        Returns:
            True if successful

        Raises:
            DatabaseException: If deletion fails
        """
        try:
            agent = self.get_by_id(agent_id, session)
            if not agent:
                raise ValueError(f"Agent with ID {agent_id} not found")

            # Prevent deletion of system default agents (both soft and hard delete)
            if agent.is_system_default:
                raise ValueError("Cannot delete system default agents. System defaults are protected.")

            if soft_delete:
                agent.is_active = False
                agent.updated_at = datetime.now(timezone.utc)
                session.commit()
            else:
                session.delete(agent)
                session.commit()

            return True

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to delete agent: {str(e)}") from e

    def activate(
        self,
        agent_id: int,
        session: Session
    ) -> ComplianceAgent:
        """
        Activate a deactivated agent.

        Args:
            agent_id: Agent ID
            session: Database session

        Returns:
            Activated ComplianceAgent

        Raises:
            DatabaseException: If activation fails
        """
        try:
            agent = self.get_by_id(agent_id, session)
            if not agent:
                raise ValueError(f"Agent with ID {agent_id} not found")

            agent.is_active = True
            agent.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(agent)
            return agent

        except ValueError as e:
            session.rollback()
            raise DatabaseException(str(e)) from e
        except Exception as e:
            session.rollback()
            raise DatabaseException(f"Failed to activate agent: {str(e)}") from e

    def search(
        self,
        search_term: str,
        session: Session,
        agent_type: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[ComplianceAgent]:
        """
        Search agents by name or description.

        Args:
            search_term: Search term
            session: Database session
            agent_type: Optional filter by agent type
            include_inactive: Include inactive agents

        Returns:
            List of matching ComplianceAgent objects
        """
        query = session.query(ComplianceAgent).filter(
            or_(
                ComplianceAgent.name.ilike(f"%{search_term}%"),
                ComplianceAgent.description.ilike(f"%{search_term}%")
            )
        )

        if agent_type:
            query = query.filter(ComplianceAgent.agent_type == agent_type)

        if not include_inactive:
            query = query.filter(ComplianceAgent.is_active == True)

        return query.order_by(ComplianceAgent.created_at.desc()).all()

    def clone_agent(
        self,
        agent_id: int,
        new_name: str,
        session: Session,
        created_by: Optional[str] = None
    ) -> ComplianceAgent:
        """
        Clone an existing agent with a new name.

        Args:
            agent_id: Source agent ID
            new_name: Name for cloned agent
            session: Database session
            created_by: User creating the clone

        Returns:
            Cloned ComplianceAgent

        Raises:
            DatabaseException: If cloning fails
        """
        try:
            source_agent = self.get_by_id(agent_id, session)
            if not source_agent:
                raise ValueError(f"Agent with ID {agent_id} not found")

            # Check for name conflict
            if self.get_by_name(new_name, session):
                raise ValueError(f"Agent with name '{new_name}' already exists")

            # Create clone
            clone_data = {
                'name': new_name,
                'agent_type': source_agent.agent_type,
                'workflow_type': source_agent.workflow_type or 'general',  # Ensure workflow_type is never None
                'model_name': source_agent.model_name,
                'system_prompt': source_agent.system_prompt,
                'user_prompt_template': source_agent.user_prompt_template,
                'temperature': source_agent.temperature,
                'max_tokens': source_agent.max_tokens,
                'is_system_default': False,  # Clones are never system defaults
                'is_active': True,
                'created_by': created_by,
                'description': f"Cloned from: {source_agent.name}",
                'agent_metadata': source_agent.agent_metadata  # Use correct attribute name
            }

            return self.create(clone_data, session)

        except ValueError as e:
            raise DatabaseException(str(e)) from e
        except Exception as e:
            raise DatabaseException(f"Failed to clone agent: {str(e)}") from e
