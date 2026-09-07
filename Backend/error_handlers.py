"""
Centralized error handling utilities for the RAG application.
Provides standardized error responses and exception handling.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import psycopg2
from google.auth.exceptions import GoogleAuthError
import google.api_core.exceptions

# Configure logging
logger = logging.getLogger(__name__)

class AppError(Exception):
    """Base application error class."""
    def __init__(self, message: str, status_code: int = 500, error_code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        super().__init__(self.message)

class AuthenticationError(AppError):
    """Authentication-related errors."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401, "AUTH_ERROR")

class AuthorizationError(AppError):
    """Authorization-related errors."""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403, "FORBIDDEN")

class ValidationError(AppError):
    """Validation-related errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, 400, "VALIDATION_ERROR")
        self.field = field

class ResourceNotFoundError(AppError):
    """Resource not found errors."""
    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(message, 404, "NOT_FOUND")

class DatabaseError(AppError):
    """Database-related errors."""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, 500, "DATABASE_ERROR")

class ExternalServiceError(AppError):
    """External service errors (Gemini, Google Auth, etc.)."""
    def __init__(self, service_name: str, message: str):
        super().__init__(f"{service_name} error: {message}", 503, "SERVICE_UNAVAILABLE")

class ServerError(AppError):
    """General server errors."""
    def __init__(self, message: str = "Internal server error"):
        super().__init__(message, 500, "SERVER_ERROR")

def error_response(error: AppError) -> Dict[str, Any]:
    """Convert AppError to JSON response format."""
    return {
        "error": error.error_code,
        "message": error.message,
        "status_code": error.status_code
    }

def handle_database_error(error: Exception) -> DatabaseError:
    """Convert database errors to AppError."""
    error_msg = str(error)
    
    if isinstance(error, psycopg2.OperationalError):
        return DatabaseError("Database connection failed. Please try again later.")
    elif isinstance(error, psycopg2.IntegrityError):
        return DatabaseError("Database constraint violated. Please check your input.")
    elif isinstance(error, psycopg2.ProgrammingError):
        return DatabaseError("Database query error. Please contact support.")
    elif "connection" in error_msg.lower():
        return DatabaseError("Unable to connect to database. Please try again later.")
    elif "timeout" in error_msg.lower():
        return DatabaseError("Database operation timed out. Please try again.")
    else:
        return DatabaseError("Database error occurred. Please try again.")

def handle_google_auth_error(error: Exception) -> ExternalServiceError:
    """Convert Google Auth errors to AppError."""
    error_msg = str(error)
    
    if isinstance(error, GoogleAuthError):
        return ExternalServiceError("Google Auth", "Authentication service unavailable")
    elif "invalid_token" in error_msg.lower():
        return ExternalServiceError("Google Auth", "Invalid or expired token")
    elif "network" in error_msg.lower() or "connection" in error_msg.lower():
        return ExternalServiceError("Google Auth", "Network error. Please try again.")
    else:
        return ExternalServiceError("Google Auth", error_msg)

def handle_gemini_error(error: Exception) -> ExternalServiceError:
    """Convert Gemini API errors to AppError."""
    error_msg = str(error)
    
    if isinstance(error, google.api_core.exceptions.GoogleAPICallError):
        if isinstance(error, google.api_core.exceptions.ResourceExhausted):
            return ExternalServiceError("Gemini", "Rate limit exceeded. Please try again later.")
        elif isinstance(error, google.api_core.exceptions.DeadlineExceeded):
            return ExternalServiceError("Gemini", "Request timeout. Please try again.")
        elif isinstance(error, google.api_core.exceptions.Unavailable):
            return ExternalServiceError("Gemini", "Service temporarily unavailable. Please try again later.")
        elif isinstance(error, google.api_core.exceptions.PermissionDenied):
            return ExternalServiceError("Gemini", "API key error. Please check your configuration.")
        elif isinstance(error, google.api_core.exceptions.InvalidArgument):
            return ExternalServiceError("Gemini", "Invalid request format.")
    elif "401" in error_msg or "api_key" in error_msg.lower():
        return ExternalServiceError("Gemini", "Invalid API key. Please check your configuration.")
    elif "429" in error_msg:
        return ExternalServiceError("Gemini", "Rate limit exceeded. Please try again later.")
    elif "503" in error_msg or "unavailable" in error_msg.lower():
        return ExternalServiceError("Gemini", "Service unavailable. Please try again later.")
    elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
        return ExternalServiceError("Gemini", "Request timeout. Please try again.")
    elif "connection" in error_msg.lower():
        return ExternalServiceError("Gemini", "Network error. Please check your connection.")
    else:
        return ExternalServiceError("Gemini", error_msg)

def handle_file_error(error: Exception) -> AppError:
    """Convert file operation errors to AppError."""
    error_msg = str(error)
    
    if "not found" in error_msg.lower():
        return AppError("File not found", 404, "FILE_NOT_FOUND")
    elif "permission" in error_msg.lower():
        return AppError("Permission denied", 403, "PERMISSION_DENIED")
    elif "disk" in error_msg.lower() or "space" in error_msg.lower():
        return AppError("Insufficient disk space", 500, "DISK_ERROR")
    elif "timeout" in error_msg.lower():
        return AppError("File operation timed out", 504, "TIMEOUT")
    else:
        return AppError("File operation failed", 500, "FILE_ERROR")

async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for all unhandled exceptions."""
    error_msg = str(exc)
    logger.error(f"Unhandled exception: {type(exc).__name__}: {error_msg}")
    
    # Handle known error types
    if isinstance(exc, AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc)
        )
    elif isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )
    elif isinstance(exc, psycopg2.Error):
        app_error = handle_database_error(exc)
        return JSONResponse(
            status_code=app_error.status_code,
            content=error_response(app_error)
        )
    elif isinstance(exc, google.api_core.exceptions.GoogleAPICallError):
        app_error = handle_gemini_error(exc)
        return JSONResponse(
            status_code=app_error.status_code,
            content=error_response(app_error)
        )
    elif isinstance(exc, GoogleAuthError):
        app_error = handle_google_auth_error(exc)
        return JSONResponse(
            status_code=app_error.status_code,
            content=error_response(app_error)
        )
    else:
        # Generic error response for unknown exceptions
        return JSONResponse(
            status_code=500,
            content=error_response(ServerError("An unexpected error occurred. Please try again."))
        )

def log_error(error: Exception, context: str = ""):
    """Log error with context information."""
    error_msg = f"Error in {context}: {type(error).__name__}: {str(error)}"
    if isinstance(error, AppError):
        logger.warning(error_msg)
    else:
        logger.error(error_msg)
