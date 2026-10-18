"""Diagnostic sensor showing a remote's next rolling code."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SomfyRtsConfigEntry
from .const import SUBENTRY_REMOTE
from .entity import SomfyRtsEntity
from .hub import SomfyRtsHub, rolling_code_signal


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SomfyRtsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a rolling code sensor per remote."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_REMOTE:
            async_add_entities(
                [RollingCodeSensor(entry.runtime_data, subentry, entry.entry_id)],
                config_subentry_id=subentry.subentry_id,
            )


class RollingCodeSensor(SomfyRtsEntity, SensorEntity):
    """The rolling code the next press will use."""

    _attr_translation_key = "rolling_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: SomfyRtsHub, subentry: ConfigSubentry, entry_id: str) -> None:
        super().__init__(hub, subentry, "rolling_code")
        self._entry_id = entry_id

    @property
    def native_value(self) -> int:
        """Return the next rolling code."""
        return self._hub.rolling_code(self._remote)

    async def async_added_to_hass(self) -> None:
        """Update whenever the remote sends."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                rolling_code_signal(self._entry_id, self._remote.key),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
