"""Base entity for a virtual RTS remote."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import RemoteConfig, SomfyRtsHub
from .rts import Button


class SomfyRtsEntity(Entity):
    """An entity belonging to one virtual remote."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: SomfyRtsHub, subentry: ConfigSubentry, suffix: str) -> None:
        self._hub = hub
        self._remote = RemoteConfig.from_subentry(subentry)
        self._attr_unique_id = f"{self._remote.key}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._remote.key)},
            name=subentry.title,
            manufacturer="Somfy",
            model="RTS virtual remote",
            serial_number=f"0x{self._remote.key}",
        )

    async def _async_press(self, button: Button) -> None:
        await self._hub.async_press(self._remote, button)
