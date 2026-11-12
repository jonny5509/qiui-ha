"""Exceptions for the QIUI integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class QiuiError(HomeAssistantError):
    """Base class for all QIUI errors."""


class QiuiConnectionError(QiuiError):
    """Raised when the QIUI cloud API cannot be reached."""


class QiuiAuthError(QiuiError):
    """Raised when the platform API token is missing, invalid or expired."""


class QiuiApiError(QiuiError):
    """Raised when the QIUI cloud API returns an error code.

    The numeric ``code`` is kept so callers can react to individual error
    codes from the platform (see ``ERROR_CODES`` in ``const.py``).
    """

    def __init__(self, message: str, code: int | str | None = None) -> None:
        """Initialise the error."""
        super().__init__(message)
        self.code = code


class QiuiBleError(QiuiError):
    """Raised when the Bluetooth link to a device fails."""


class QiuiDeviceUnavailable(QiuiBleError):
    """Raised when the device cannot be found by any Bluetooth source."""
