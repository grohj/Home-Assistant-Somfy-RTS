"""Rolling code bookkeeping and command sending."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DEVICE_CLASS,
    CONF_REMOTE_ID,
    CONF_REPETITIONS,
    CONF_ROLLING_CODE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_REPETITIONS,
    DOMAIN,
    STORAGE_VERSION,
    SUBENTRY_REMOTE,
)
from .rts import MAX_ROLLING_CODE, Button, build_frame, build_pulses
from .transmitter import PigpioTransmitter, TransmitterError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteConfig:
    """One virtual RTS remote, stored as a config subentry."""

    remote_id: int
    initial_rolling_code: int
    repetitions: int
    device_class: str

    @property
    def key(self) -> str:
        """Stable key for storage and unique ids."""
        return f"{self.remote_id:06X}"

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> RemoteConfig:
        """Build from a remote subentry."""
        data = subentry.data
        return cls(
            remote_id=data[CONF_REMOTE_ID],
            initial_rolling_code=data[CONF_ROLLING_CODE],
            repetitions=data.get(CONF_REPETITIONS, DEFAULT_REPETITIONS),
            device_class=data.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
        )


def rolling_code_signal(entry_id: str, key: str) -> str:
    """Dispatcher signal sent when a remote's rolling code changes."""
    return f"{DOMAIN}_{entry_id}_{key}_rolling_code"


class SomfyRtsHub:
    """Owns the transmitter and the rolling code of every remote."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, transmitter: PigpioTransmitter
    ) -> None:
        self.hass = hass
        self.transmitter = transmitter
        self._entry_id = entry.entry_id
        self._store: Store[dict[str, int]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._codes: dict[str, int] = {}
        # One transmitter, so only one frame on air at a time.
        self._lock = asyncio.Lock()

    async def async_load(self, entry: ConfigEntry) -> None:
        """Load stored rolling codes, never going below a remote's initial code."""
        self._codes = dict(await self._store.async_load() or {})
        for subentry in entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_REMOTE:
                continue
            remote = RemoteConfig.from_subentry(subentry)
            stored = self._codes.get(remote.key, remote.initial_rolling_code)
            self._codes[remote.key] = max(stored, remote.initial_rolling_code)
        await self._store.async_save(self._codes)

    def rolling_code(self, remote: RemoteConfig) -> int:
        """Return the code the next press of this remote will use."""
        return self._codes.get(remote.key, remote.initial_rolling_code)

    async def async_press(self, remote: RemoteConfig, button: Button) -> None:
        """Send one button press for a remote."""
        async with self._lock:
            code = self.rolling_code(remote)
            # Persist the next code before sending, so a crash mid-transmission
            # can never make us reuse a code the motor has already seen.
            self._codes[remote.key] = (code + 1) & MAX_ROLLING_CODE
            await self._store.async_save(self._codes)

            pulses = build_pulses(
                build_frame(button, code, remote.remote_id), remote.repetitions
            )
            _LOGGER.debug(
                "Remote %s: sending %s with rolling code %d",
                remote.key,
                button.name,
                code,
            )
            try:
                await self.hass.async_add_executor_job(self.transmitter.send, pulses)
            except TransmitterError as err:
                raise HomeAssistantError(
                    f"Sending Somfy RTS command failed: {err}"
                ) from err
            finally:
                async_dispatcher_send(
                    self.hass, rolling_code_signal(self._entry_id, remote.key)
                )
