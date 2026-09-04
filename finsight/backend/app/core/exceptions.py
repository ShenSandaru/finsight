"""Standardized application and service exception hierarchy for FinSight."""

from typing import Any


class FinSightError(Exception):
    """Base exception for all FinSight domain and service errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(FinSightError):
    """Raised when incoming client/domain data fails validation rules."""
    pass


class FileValidationError(ValidationError):
    """Raised when an uploaded file violates type, extension, or size constraints."""
    pass


class NotFoundError(FinSightError):
    """Raised when a requested resource is not found."""
    pass


class DocumentNotFoundError(NotFoundError):
    """Raised when a specific document ID is not found."""
    pass


class ChunkNotFoundError(NotFoundError):
    """Raised when a specific chunk ID is not found."""
    pass


class ServiceError(FinSightError):
    """Raised when an internal business logic or service operation fails."""
    pass


class ProcessingError(ServiceError):
    """Raised when a background task or document processing fails."""
    pass


class ExternalServiceError(FinSightError):
    """Raised when an external third-party integration (e.g. LLM API, Redis) fails."""
    pass
