"""Diagnostics: a one-click export of every remote's id and rolling code."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import SomfyRtsConfigEntry
from .const import CONF_GPIO, SUBENTRY_REMOTE
from .hub import RemoteConfig


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SomfyRtsConfigEntry
) -> dict[str, Any]:
    """Return the transmitter settings and the state of every remote.

    This doubles as a rolling code backup: the ids and next codes are all
    that is needed to restore the remotes elsewhere without re-pairing.
    """
    hub = entry.runtime_data
    remotes = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_REMOTE:
            continue
        remote = RemoteConfig.from_subentry(subentry)
        remotes.append(
            {
                "name": subentry.title,
                "remote_id": f"0x{remote.key}",
                "remote_id_decimal": remote.remote_id,
                "next_rolling_code": hub.rolling_code(remote),
                "repetitions": remote.repetitions,
                "device_class": remote.device_class,
            }
        )
    return {
        "transmitter": {
            "host": entry.data[CONF_HOST],
            "port": entry.data[CONF_PORT],
            "gpio": entry.data[CONF_GPIO],
        },
        "remotes": remotes,
    }
