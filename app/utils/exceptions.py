"""AMZ_Designy - Domain-specific exceptions for trends integration."""

from __future__ import annotations


class TrendsError(Exception):
    """Base exception for trends-related errors."""
    pass


class TrendsEmptyResultError(TrendsError):
    """Raised when trends API returns empty results."""
    pass


class TrendsRateLimitError(TrendsError):
    """Raised when rate limited by trends API."""
    pass


class TrendsAPIError(TrendsError):
    """Raised when trends API returns an error response."""
    pass


class TrendsGeoNotSupportedError(TrendsError):
    """Raised when the requested geo is not supported."""
    pass
