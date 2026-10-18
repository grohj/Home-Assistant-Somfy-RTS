"""Somfy RTS shutters through a 433.42 MHz transmitter driven by pigpiod."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_GPIO
from .hub import SomfyRtsHub
from .transmitter import PigpioTransmitter, TransmitterError

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SENSOR]

type SomfyRtsConfigEntry = ConfigEntry[SomfyRtsHub]


async def async_setup_entry(hass: HomeAssistant, entry: SomfyRtsConfigEntry) -> bool:
    """Connect to pigpiod and set up one device per remote."""
    transmitter = PigpioTransmitter(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_GPIO]
    )
    try:
        await hass.async_add_executor_job(transmitter.connect)
    except TransmitterError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hub = SomfyRtsHub(hass, entry, transmitter)
    await hub.async_load(entry)
    entry.runtime_data = hub

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SomfyRtsConfigEntry) -> bool:
    """Unload platforms and disconnect from pigpiod."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.transmitter.close)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: SomfyRtsConfigEntry) -> None:
    """Reload when remotes are added, changed or removed."""
    await hass.config_entries.async_reload(entry.entry_id)
