"""Cover entity: Up, Down and My (stop) of a virtual RTS remote."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import SomfyRtsConfigEntry
from .const import SUBENTRY_REMOTE
from .entity import SomfyRtsEntity
from .hub import SomfyRtsHub
from .rts import Button


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SomfyRtsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one cover per remote."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_REMOTE:
            async_add_entities(
                [SomfyRtsCover(entry.runtime_data, subentry)],
                config_subentry_id=subentry.subentry_id,
            )


class SomfyRtsCover(SomfyRtsEntity, CoverEntity, RestoreEntity):
    """RTS is one-way, so the state is only what we last sent."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, hub: SomfyRtsHub, subentry: ConfigSubentry) -> None:
        super().__init__(hub, subentry, "cover")
        self._attr_device_class = CoverDeviceClass(self._remote.device_class)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state == STATE_CLOSED:
                self._attr_is_closed = True
            elif last.state == STATE_OPEN:
                self._attr_is_closed = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Press Up."""
        await self._async_press(Button.UP)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Press Down."""
        await self._async_press(Button.DOWN)
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Press My, which stops a moving motor.

        On a motor at rest, My moves to the stored favourite position instead.
        """
        await self._async_press(Button.MY)
        self._attr_is_closed = False
        self.async_write_ha_state()
