from __future__ import annotations


class KiwoomError(Exception):
    """Base error for Kiwoom API failures."""


class KiwoomConfigError(KiwoomError):
    """Raised when required Kiwoom settings are missing."""


class KiwoomAuthError(KiwoomError):
    """Raised when token issuance or authorization fails."""


class KiwoomApiError(KiwoomError):
    """Raised when Kiwoom returns a non-zero return_code."""


class KiwoomSchemaError(KiwoomError):
    """Raised when a response shape cannot be normalized."""
