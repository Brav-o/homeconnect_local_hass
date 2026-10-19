"""Tests for services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from custom_components.homeconnect_ws.const import DOMAIN
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeconnect_websocket.message import Action, Message

from . import setup_config_entry
from .const import CONFIG_ENTRIES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeconnect_websocket.testutils import MockAppliance


async def _setup(hass: HomeAssistant) -> str:
    config_entry = CONFIG_ENTRIES[0]
    assert await setup_config_entry(hass, config_entry)
    device_registry = dr.async_get(hass)
    return dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)[0].id


async def test_start_program_with_options(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """Test starting a given program with options, without a selected program."""
    device_id = await _setup(hass)

    await hass.services.async_call(
        domain=DOMAIN,
        service="start_program",
        service_data={
            "device_id": device_id,
            "program": "Test.Program.Program1",
            "options": {"Test.Option1": 200},
        },
        blocking=True,
    )

    mock_appliance.session.send_sync.assert_awaited_once_with(
        Message(
            resource="/ro/activeProgram",
            action=Action.POST,
            data={
                "program": 500,
                "options": [{"uid": 401, "value": 200}, {"uid": 402, "value": None}],
            },
        )
    )


async def test_start_selected_program_with_options(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """Test options are also applied when starting the selected program."""
    device_id = await _setup(hass)
    await mock_appliance.entities["Test.SelectedProgram"].update({"value": 500})
    await hass.async_block_till_done()

    await hass.services.async_call(
        domain=DOMAIN,
        service="start_program",
        service_data={"device_id": device_id, "options": {"Test.Option2": 5}},
        blocking=True,
    )

    mock_appliance.session.send_sync.assert_awaited_once_with(
        Message(
            resource="/ro/activeProgram",
            action=Action.POST,
            data={
                "program": 500,
                "options": [{"uid": 402, "value": 5}, {"uid": 401, "value": None}],
            },
        )
    )


@pytest.mark.parametrize(
    ("service_data", "translation_key"),
    [
        ({"program": "Test.Program.Unknown"}, "program_not_available"),
        (
            {"program": "Test.Program.Program1", "options": {"Test.Unknown": 1}},
            "option_not_available",
        ),
        ({}, "no_program_selected"),
    ],
)
async def test_start_program_errors(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
    service_data: dict,
    translation_key: str,
) -> None:
    """Test start_program validation errors."""
    device_id = await _setup(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            domain=DOMAIN,
            service="start_program",
            service_data={"device_id": device_id, **service_data},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
    mock_appliance.session.send_sync.assert_not_awaited()
