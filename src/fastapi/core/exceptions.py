"""
Custom exceptions for the application.

This module defines domain-specific exceptions for better error handling
and more meaningful error messages throughout the application.
"""

from typing import Optional, Any, Dict


class ApplicationException(Exception):
    """Base exception for all application-specific exceptions."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatabaseException(ApplicationException):
    """Exception raised for database-related errors."""
    pass


class RepositoryException(ApplicationException):
    """Exception raised for repository-level errors."""
    pass


class ServiceException(ApplicationException):
    """Exception raised for service-level errors."""
    pass


class ValidationException(ApplicationException):
    """Exception raised for validation errors."""
    pass


class NotFoundException(ApplicationException):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource: str, identifier: Any):
        message = f"{resource} not found: {identifier}"
        super().__init__(message, {"resource": resource, "identifier": identifier})


class DuplicateException(ApplicationException):
    """Exception raised when attempting to create a duplicate resource."""

    def __init__(self, resource: str, field: str, value: Any):
        message = f"{resource} already exists with {field}: {value}"
        super().__init__(message, {"resource": resource, "field": field, "value": value})


class ConfigurationException(ApplicationException):
    """Exception raised for configuration-related errors."""
    pass


class ExternalServiceException(ApplicationException):
    """Exception raised when an external service (ChromaDB, Redis, LLM) fails."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        full_message = f"{service} error: {message}"
        details = details or {}
        details["service"] = service
        super().__init__(full_message, details)


class ChromaDBException(ExternalServiceException):
    """Exception raised for ChromaDB-specific errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("ChromaDB", message, details)


class RedisException(ExternalServiceException):
    """Exception raised for Redis-specific errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("Redis", message, details)


class LLMException(ExternalServiceException):
    """Exception raised for LLM provider errors."""

    def __init__(self, message: str, provider: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__("LLM", message, details)


class AgentException(ServiceException):
    """Exception raised for agent-related errors."""
    pass


class RAGException(ServiceException):
    """Exception raised for RAG pipeline errors."""
    pass


class IngestionException(ServiceException):
    """Exception raised for document ingestion errors."""
    pass
