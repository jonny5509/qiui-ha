"""Tests for the Bluetooth auto-detection helpers."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.qiui.const import (
    FAMILIES,
    KEYPOD,
    METAL_LOCK,
    PEAR_FLOWER,
    SERVICE_UUID_FAMILIES,
    families_for_service_uuids,
    family_for_service_uuids,
    normalise_uuid,
    type_id_from_family,
)

MANIFEST = (
    Path(__file__).parent.parent / "custom_components" / "qiui" / "manifest.json"
)


def test_normalise_short_uuid() -> None:
    """Short, long and mixed-case UUIDs all end up in 128 bit form."""
    assert normalise_uuid("fff0") == "0000fff0-0000-1000-8000-00805f9b34fb"
    assert normalise_uuid("0xFFF0") == "0000fff0-0000-1000-8000-00805f9b34fb"
    assert normalise_uuid("12345678") == (
        "12345678-0000-1000-8000-00805f9b34fb"
    )
    assert normalise_uuid("000036F5-0000-1000-8000-00805F9B34FB") == (
        "000036f5-0000-1000-8000-00805f9b34fb"
    )


def test_family_from_advertised_uuid() -> None:
    """Advertisements identify the hardware family."""
    assert family_for_service_uuids(["fff0"]) is KEYPOD
    assert family_for_service_uuids(["ac3a"]) is PEAR_FLOWER
    assert family_for_service_uuids(["180f", "fff0"]) is KEYPOD
    assert family_for_service_uuids(["180f"]) is None
    assert family_for_service_uuids([]) is None


def test_shared_bluetooth_profiles() -> None:
    """A UUID can be shared by more than one model."""
    assert {family.key for family in families_for_service_uuids(["fee7"])} == {
        "cellmate",
        "cellmate_4g",
    }
    assert {family.key for family in families_for_service_uuids(["fee5"])} == {
        "metal_lock",
        "metal_shake",
    }


def test_type_hint_only_for_unambiguous_family() -> None:
    """A family with a single model can fill in the type id."""
    assert type_id_from_family(METAL_LOCK) == 13
    assert type_id_from_family(KEYPOD) == 0
    assert type_id_from_family(None) == 0


def test_every_profile_is_indexed() -> None:
    """Each family with a Bluetooth profile is discoverable."""
    for family in FAMILIES:
        if family.service_uuid:
            assert normalise_uuid(family.service_uuid) in SERVICE_UUID_FAMILIES


def test_manifest_matches_the_known_profiles() -> None:
    """Home Assistant only dispatches advertisements listed in the manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    matchers = manifest["bluetooth"]
    matched = {normalise_uuid(entry["service_uuid"]) for entry in matchers}
    expected = {
        normalise_uuid(family.service_uuid)
        for family in FAMILIES
        if family.service_uuid
    }

    assert matched == expected
    assert all(entry.get("connectable") for entry in matchers)
