"""Test configuration.

The integration targets Home Assistant 2024.6+, where ``ConfigEntry`` is
generic.  Older installations are still useful for running the unit tests, so
make the class subscriptable there as well.
"""

from __future__ import annotations

from homeassistant import config_entries

if getattr(config_entries.ConfigEntry, "__class_getitem__", None) is None:
    config_entries.ConfigEntry.__class_getitem__ = classmethod(  # type: ignore[attr-defined]
        lambda cls, _item: cls
    )
