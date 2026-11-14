"""
WEDJAT-X Phase 7 — Application Exceptions Hierarchy
Offline-First Astronaut Health-Monitoring Decision-Support Backend.

Defines custom exception classes for validation, routing, execution,
and integration errors.
"""

from typing import Optional, List, Dict, Any


class WedjatXError(Exception):
    """Base exception for all WEDJAT-X backend errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(WedjatXError):
    """Raised when input data fails schema or integrity validation."""

    def __init__(
        self,
        message: str,
        missing_fields: Optional[List[str]] = None,
        invalid_fields: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.missing_fields = missing_fields or []
        self.invalid_fields = invalid_fields or {}

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["missing_fields"] = self.missing_fields
        d["invalid_fields"] = self.invalid_fields
        return d


class SchemaMismatchError(ValidationError):
    """Raised when data structure does not match the expected dataset schema."""
    pass


class DataRoutingError(WedjatXError):
    """Raised when data cannot be routed or is routed to an incompatible pipeline."""
    pass


class UnsupportedSourceError(DataRoutingError):
    """Raised when an unknown or unsupported source_type is specified."""
    pass


class ProvenanceViolationError(DataRoutingError):
    """Raised when synthetic and NASA laboratory data are merged or mislabeled."""
    pass


class EngineExecutionError(WedjatXError):
    """Raised when an analytical engine encounters an unrecoverable runtime error."""

    def __init__(
        self,
        engine_name: str,
        message: str,
        underlying_exception: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        full_msg = f"Engine '{engine_name}' execution failed: {message}"
        super().__init__(full_msg, details)
        self.engine_name = engine_name
        self.underlying_exception = underlying_exception

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["engine_name"] = self.engine_name
        if self.underlying_exception:
            d["underlying_error"] = str(self.underlying_exception)
        return d
