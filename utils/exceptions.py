"""Custom exception hierarchy for the Technical Service Assistant."""

from typing import Optional, Any, Dict


class TechnicalServiceError(Exception):
    """Base exception for Technical Service Assistant.
    
    All custom exceptions in the application should inherit from this base class.
    Provides structured error handling with optional context and error codes.
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for categorization
            context: Additional context information for debugging
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context
        }


class PDFProcessingError(TechnicalServiceError):
    """Raised when PDF processing fails.
    
    This includes errors in PDF parsing, text extraction, 
    table extraction, or image extraction.
    """
    pass


class EmbeddingGenerationError(TechnicalServiceError):
    """Raised when embedding generation fails.
    
    This includes errors communicating with Ollama services
    or processing embedding responses.
    """
    pass


class DatabaseError(TechnicalServiceError):
    """Raised when database operations fail.
    
    This includes connection errors, query failures,
    and data integrity issues.
    """
    pass


class SearchError(TechnicalServiceError):
    """Raised when search operations fail.
    
    This includes vector search failures, hybrid search issues,
    and result processing errors.
    """
    pass


class ConfigurationError(TechnicalServiceError):
    """Raised when configuration is invalid or missing.
    
    This includes missing environment variables,
    invalid configuration values, and setup issues.
    """
    pass


class ExternalServiceError(TechnicalServiceError):
    """Raised when external service calls fail.
    
    This includes Ollama API failures, SearXNG issues,
    and other external dependency problems.
    """
    pass


class ValidationError(TechnicalServiceError):
    """Raised when input validation fails.
    
    This includes invalid request data, malformed files,
    and constraint violations.
    """
    pass


class AuthenticationError(TechnicalServiceError):
    """Raised when authentication fails.
    
    This includes invalid API keys, expired tokens,
    and permission denied scenarios.
    """
    pass


class AuthorizationError(TechnicalServiceError):
    """Raised when authorization/permission checks fail.
    
    This includes missing permissions, role restrictions,
    and forbidden resource access attempts.
    """
    pass


class AccountLockedError(TechnicalServiceError):
    """Raised when an account is temporarily locked due to security policies.
    
    Typically triggered by repeated failed login attempts or
    administrative suspension actions.
    """
    pass


class RateLimitError(TechnicalServiceError):
    """Raised when rate limits are exceeded.
    
    This includes API rate limiting and resource
    usage threshold violations.
    """
    pass


class TimeoutError(TechnicalServiceError):
    """Raised when operations timeout.
    
    This includes long-running queries, external
    service timeouts, and processing delays.
    """
    pass