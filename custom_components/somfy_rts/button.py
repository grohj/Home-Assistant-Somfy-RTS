"""My and Prog buttons of a virtual RTS remote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    """Add My and Prog buttons per remote."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_REMOTE:
            hub = entry.runtime_data
            async_add_entities(
                [
                    SomfyRtsButton(hub, subentry, Button.MY, "my"),
                    SomfyRtsButton(hub, subentry, Button.PROG, "prog"),
                ],
                config_subentry_id=subentry.subentry_id,
            )


class SomfyRtsButton(SomfyRtsEntity, ButtonEntity):
    """Sends a single RTS button press."""

    def __init__(
        self, hub: SomfyRtsHub, subentry: ConfigSubentry, button: Button, key: str
    ) -> None:
        super().__init__(hub, subentry, key)
        self._button = button
        self._attr_translation_key = key
        if button is Button.PROG:
            # Only needed while pairing; keep it out of the main controls.
            self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Send the button press."""
        await self._async_press(self._button)
