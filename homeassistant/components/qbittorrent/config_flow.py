"""Config flow for qBittorrent."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import AuthenticationError, CannotConnect, get_client
from .const import (
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class QbittorrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the qBittorrent integration."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> QBittorrentOptionsFlowHandler:
        """Get the options flow for this handler."""
        return QBittorrentOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user-initiated config flow."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await get_client(self.hass, user_input)
            except AuthenticationError:
                errors = {"base": "invalid_auth"}
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = self.add_suggested_values_to_schema(USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class QBittorrentOptionsFlowHandler(OptionsFlow):
    """Handle qBittorrent client options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize qBittorrent options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the qBittorrent options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
