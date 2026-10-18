"""Config flow: one entry per transmitter, one subentry per virtual remote."""

from __future__ import annotations

import random
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_CLASS,
    CONF_GPIO,
    CONF_REMOTE_ID,
    CONF_REPETITIONS,
    CONF_ROLLING_CODE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_GPIO,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_REPETITIONS,
    DEFAULT_ROLLING_CODE,
    DOMAIN,
    MAX_REPETITIONS,
    SUBENTRY_REMOTE,
)
from .hub import RemoteConfig
from .rts import MAX_REMOTE_ID, MAX_ROLLING_CODE, parse_remote_id
from .transmitter import PigpioTransmitter, TransmitterError

TRANSMITTER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_GPIO, default=DEFAULT_GPIO): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=53)
        ),
    }
)

DEVICE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            CoverDeviceClass.SHUTTER,
            CoverDeviceClass.BLIND,
            CoverDeviceClass.AWNING,
            CoverDeviceClass.CURTAIN,
            CoverDeviceClass.SHADE,
            CoverDeviceClass.WINDOW,
            CoverDeviceClass.GARAGE,
            CoverDeviceClass.GATE,
        ],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_DEVICE_CLASS,
    )
)

REPETITIONS_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_REPETITIONS))


class SomfyRtsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a pigpiod-driven transmitter."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Remotes are added as subentries."""
        return {SUBENTRY_REMOTE: RemoteSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the pigpiod address and the transmitter pin."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_GPIO: user_input[CONF_GPIO],
                }
            )
            transmitter = PigpioTransmitter(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_GPIO]
            )
            try:
                await self.hass.async_add_executor_job(transmitter.connect)
            except TransmitterError:
                errors["base"] = "cannot_connect"
            else:
                await self.hass.async_add_executor_job(transmitter.close)
                return self.async_create_entry(
                    title=f"GPIO {user_input[CONF_GPIO]} @ {user_input[CONF_HOST]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                TRANSMITTER_SCHEMA, user_input
            ),
            errors=errors,
        )


class RemoteSubentryFlow(ConfigSubentryFlow):
    """Add or edit a virtual remote.

    The remote id is fixed once created and the rolling code can only go up:
    anything else would desync the motors the remote is paired with.
    """

    def _used_remote_ids(self) -> set[int]:
        return {
            subentry.data[CONF_REMOTE_ID]
            for subentry in self._get_entry().subentries.values()
            if subentry.subentry_type == SUBENTRY_REMOTE
        }

    def _suggest_remote_id(self) -> str:
        used = self._used_remote_ids()
        while True:
            # Stay clear of 0 and the top of the range some remotes use.
            candidate = random.randint(0x100000, 0xEFFFFF)
            if candidate not in used:
                return f"0x{candidate:06X}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a remote, either new or imported from another controller."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                remote_id = parse_remote_id(user_input[CONF_REMOTE_ID])
            except ValueError:
                errors[CONF_REMOTE_ID] = "invalid_remote_id"
            else:
                if remote_id in self._used_remote_ids():
                    errors[CONF_REMOTE_ID] = "remote_id_in_use"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_REMOTE_ID: remote_id,
                            CONF_ROLLING_CODE: user_input[CONF_ROLLING_CODE],
                            CONF_REPETITIONS: user_input[CONF_REPETITIONS],
                            CONF_DEVICE_CLASS: user_input[CONF_DEVICE_CLASS],
                        },
                        unique_id=f"{remote_id:06X}",
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_REMOTE_ID, default=self._suggest_remote_id()): str,
                vol.Required(CONF_ROLLING_CODE, default=DEFAULT_ROLLING_CODE): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=MAX_ROLLING_CODE)
                ),
                vol.Required(
                    CONF_REPETITIONS, default=DEFAULT_REPETITIONS
                ): REPETITIONS_VALIDATOR,
                vol.Required(
                    CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS
                ): DEVICE_CLASS_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders={"max_remote_id": f"0x{MAX_REMOTE_ID:06X}"},
        )

    def _current_rolling_code(self, subentry: ConfigSubentry) -> int:
        entry = self._get_entry()
        remote = RemoteConfig.from_subentry(subentry)
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data.rolling_code(remote)
        return remote.initial_rolling_code

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a remote. The rolling code can only be raised, for recovery."""
        subentry = self._get_reconfigure_subentry()
        current_code = self._current_rolling_code(subentry)
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_ROLLING_CODE] < current_code:
                errors[CONF_ROLLING_CODE] = "rolling_code_lower"
            else:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data={
                        **subentry.data,
                        CONF_ROLLING_CODE: user_input[CONF_ROLLING_CODE],
                        CONF_REPETITIONS: user_input[CONF_REPETITIONS],
                        CONF_DEVICE_CLASS: user_input[CONF_DEVICE_CLASS],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=subentry.title): str,
                vol.Required(CONF_ROLLING_CODE, default=current_code): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=MAX_ROLLING_CODE)
                ),
                vol.Required(
                    CONF_REPETITIONS,
                    default=subentry.data.get(CONF_REPETITIONS, DEFAULT_REPETITIONS),
                ): REPETITIONS_VALIDATOR,
                vol.Required(
                    CONF_DEVICE_CLASS,
                    default=subentry.data.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
                ): DEVICE_CLASS_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "remote_id": f"0x{subentry.data[CONF_REMOTE_ID]:06X}"
            },
        )
