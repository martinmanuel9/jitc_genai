"""
Agent Repository

This module provides data access layer for ComplianceAgent operations,
including CRUD operations and cascade deletion of related entities.

This repository extends BaseRepository to provide standard CRUD operations
plus agent-specific methods.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from models.agent import ComplianceAgent
from models.session import DebateSession
from models.response import ComplianceResult
from repositories.base import BaseRepository
from core.exceptions import NotFoundException, DuplicateException

logger = logging.getLogger("AGENT_REPOSITORY")


class AgentRepository(BaseRepository[ComplianceAgent]):
    """
    Repository for managing ComplianceAgent database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations (get, create, update, delete)
    - Agent-specific methods (get_by_name, exists_by_name, etc.)
    - Cascade deletion handling
    - Performance metrics updates
    """

    def __init__(self, db: Session):
        """
        Initialize the agent repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(ComplianceAgent, db)

    def get_by_name(self, name: str) -> Optional[ComplianceAgent]:
        """
        Retrieve an agent by name.

        Args:
            name: Name of the agent to retrieve

        Returns:
            ComplianceAgent if found, None otherwise
        """
        try:
            return self.db.query(ComplianceAgent).filter(ComplianceAgent.name == name).first()
        except Exception as e:
            logger.error(f"Error retrieving agent by name '{name}': {e}")
            return None

    def exists_by_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if an agent with the given name exists.

        Args:
            name: Agent name to check
            exclude_id: Optional agent ID to exclude from check (useful for updates)

        Returns:
            True if agent with name exists, False otherwise
        """
        try:
            query = self.db.query(ComplianceAgent).filter(ComplianceAgent.name == name)
            if exclude_id is not None:
                query = query.filter(ComplianceAgent.id != exclude_id)
            return query.first() is not None
        except Exception as e:
            logger.error(f"Error checking agent existence by name '{name}': {e}")
            return False

    def get_active_agents(self) -> List[ComplianceAgent]:
        """
        Get all active agents.

        Returns:
            List of active ComplianceAgent objects
        """
        return self.get_by_filter({"is_active": True})

    def get_all_with_filter(self, include_inactive: bool = True) -> List[ComplianceAgent]:
        """
        Retrieve all agents with optional filtering.

        Args:
            include_inactive: If False, only return active agents

        Returns:
            List of ComplianceAgent objects
        """
        try:
            if include_inactive:
                return self.get_all()
            else:
                return self.get_active_agents()
        except Exception as e:
            logger.error(f"Error retrieving agents with filter: {e}")
            return []

    def create_agent(self, agent_data: Dict[str, Any]) -> ComplianceAgent:
        """
        Create a new agent with duplicate name checking.

        Args:
            agent_data: Dictionary containing agent attributes

        Returns:
            Created ComplianceAgent

        Raises:
            DuplicateException: If agent name already exists
            Exception: For other database errors
        """
        try:
            # Check for duplicate name
            if self.exists_by_name(agent_data.get("name")):
                raise DuplicateException("ComplianceAgent", "name", agent_data.get("name"))

            new_agent = self.create_from_dict(agent_data)
            logger.info(f"Agent created successfully: ID={new_agent.id}, Name={new_agent.name}")
            return new_agent
        except DuplicateException:
            raise
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating agent: {e}")
            raise DuplicateException("ComplianceAgent", "name", agent_data.get("name"))
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating agent: {e}")
            raise

    def update_agent(self, agent_id: int, update_data: Dict[str, Any]) -> Optional[ComplianceAgent]:
        """
        Update an existing agent with automatic timestamp update.

        Args:
            agent_id: ID of agent to update
            update_data: Dictionary of fields to update

        Returns:
            Updated ComplianceAgent if found, None otherwise

        Raises:
            Exception: For database errors
        """
        try:
            # Add updated_at timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            agent = self.update_by_id(agent_id, update_data)
            if agent:
                logger.info(f"Agent updated successfully: ID={agent.id}, Name={agent.name}")
            return agent
        except Exception as e:
            logger.error(f"Error updating agent {agent_id}: {e}")
            raise

    def delete_cascade(self, agent_id: int) -> Dict[str, Any]:
        """
        Delete an agent and all related entities (cascade deletion).

        This method handles foreign key relationships by deleting:
        1. All DebateSession records referencing this agent
        2. All ComplianceResult records referencing this agent
        3. The agent itself

        Args:
            agent_id: ID of agent to delete

        Returns:
            Dictionary containing deletion statistics

        Raises:
            NotFoundException: If agent not found
            Exception: For database errors
        """
        try:
            # Check if agent exists
            agent = self.get(agent_id)
            if not agent:
                raise NotFoundException("ComplianceAgent", agent_id)

            agent_name = agent.name

            # Delete related DebateSession records
            debate_sessions_deleted = self.db.query(DebateSession).filter(
                DebateSession.compliance_agent_id == agent_id
            ).delete(synchronize_session=False)

            # Delete related ComplianceResult records
            compliance_results_deleted = self.db.query(ComplianceResult).filter(
                ComplianceResult.agent_id == agent_id
            ).delete(synchronize_session=False)

            logger.info(
                f"Cascade deletion for agent {agent_id}: "
                f"Removed {debate_sessions_deleted} debate sessions and "
                f"{compliance_results_deleted} compliance results"
            )

            # Delete the agent
            self.delete(agent)

            deleted_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"Agent deleted successfully: ID={agent_id}, Name={agent_name}")

            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "deleted_at": deleted_at,
                "cleanup_info": {
                    "debate_sessions_deleted": debate_sessions_deleted,
                    "compliance_results_deleted": compliance_results_deleted
                }
            }

        except NotFoundException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during cascade deletion of agent {agent_id}: {e}")
            raise

    def toggle_status(self, agent_id: int) -> Optional[ComplianceAgent]:
        """
        Toggle agent active/inactive status.

        Args:
            agent_id: ID of agent to toggle

        Returns:
            Updated ComplianceAgent if found, None otherwise

        Raises:
            Exception: For database errors
        """
        try:
            agent = self.get(agent_id)
            if not agent:
                return None

            agent.is_active = not agent.is_active
            agent.updated_at = datetime.now(timezone.utc)

            updated_agent = self.update(agent)

            status = "activated" if updated_agent.is_active else "deactivated"
            logger.info(f"Agent {status}: ID={updated_agent.id}, Name={updated_agent.name}")

            return updated_agent
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error toggling agent status for {agent_id}: {e}")
            raise

    def update_performance_metrics(
        self,
        agent_id: int,
        response_time_ms: int,
        success: bool = True
    ) -> Optional[ComplianceAgent]:
        """
        Update agent performance metrics (queries, avg response time, success rate).

        Args:
            agent_id: Agent identifier
            response_time_ms: Response time in milliseconds
            success: Whether the operation was successful

        Returns:
            Updated agent or None if not found
        """
        try:
            agent = self.get(agent_id)
            if not agent:
                return None

            agent.total_queries = (agent.total_queries or 0) + 1

            # Update average response time
            if agent.avg_response_time_ms is None:
                agent.avg_response_time_ms = response_time_ms
            else:
                total_time = agent.avg_response_time_ms * (agent.total_queries - 1) + response_time_ms
                agent.avg_response_time_ms = total_time / agent.total_queries

            # Update success rate
            if agent.success_rate is None:
                agent.success_rate = 1.0 if success else 0.0
            else:
                total_successes = agent.success_rate * (agent.total_queries - 1) + (1 if success else 0)
                agent.success_rate = total_successes / agent.total_queries

            updated_agent = self.update(agent)
            logger.info(
                f"Updated performance for agent {agent_id}: "
                f"queries={agent.total_queries}, "
                f"avg_time={agent.avg_response_time_ms:.1f}ms"
            )
            return updated_agent
        except Exception as e:
            logger.error(f"Error updating performance for agent {agent_id}: {e}")
            return None

    def to_dict(self, agent: ComplianceAgent) -> Dict[str, Any]:
        """
        Convert ComplianceAgent to dictionary representation.

        Args:
            agent: ComplianceAgent instance

        Returns:
            Dictionary with agent data
        """
        return {
            "id": agent.id,
            "name": agent.name,
            "model_name": agent.model_name,
            "system_prompt": agent.system_prompt,
            "user_prompt_template": agent.user_prompt_template,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "created_by": agent.created_by,
            "is_active": agent.is_active,
            "total_queries": agent.total_queries,
            "avg_response_time_ms": agent.avg_response_time_ms,
            "success_rate": agent.success_rate,
            "chain_type": agent.chain_type,
            "memory_enabled": agent.memory_enabled,
            "tools_enabled": agent.tools_enabled
        }
