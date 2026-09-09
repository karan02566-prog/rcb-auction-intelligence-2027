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


class ProvenanceError(IngestionError):
    """Raised when data provenance manifest checks or checksum validations fail."""

    pass


class DuplicateFileError(IngestionError):
    """Raised when attempting to download or overwrite an existing raw file without permission."""

    pass


class ValidationError(RCBProjectError):
    """Raised when data contracts or schema validations fail."""

    pass


class DataQualityError(RCBProjectError):
    """Raised when data quality checks or referential integrity checks fail."""

    pass
