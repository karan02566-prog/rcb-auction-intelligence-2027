"""Custom exception hierarchy for the RCB Auction Intelligence Engine."""


class RCBProjectError(Exception):
    """Base exception class for all RCB Auction Intelligence Engine errors."""

    pass


class ConfigurationError(RCBProjectError):
    """Raised when configuration files are missing, unparseable, or invalid."""

    pass


class IngestionError(RCBProjectError):
    """Raised when data ingestion from external sources fails."""

    pass


class ValidationError(RCBProjectError):
    """Raised when data contracts or schema validations fail."""

    pass


class DataQualityError(RCBProjectError):
    """Raised when data quality checks or referential integrity checks fail."""

    pass
