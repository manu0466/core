"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QBittorrentClient
from .const import DOMAIN

_LOGGING = logging.getLogger(__name__)

SWITCH_TYPE_ON_OFF = "on_off"
SWITCH_TYPE_ALTERNATIVE_SPEED = "alternative_speed"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    qb_client = hass.data[DOMAIN][config_entry.entry_id]
    config_entry.data[CONF_NAME]

    dev = [
        QBittorrentSwitch(qb_client, config_entry, "On/Off", "on_off"),
        QBittorrentSwitch(
            qb_client, config_entry, "Alternative speed", SWITCH_TYPE_ALTERNATIVE_SPEED
        ),
    ]
    async_add_entities(dev, True)


class QBittorrentSwitch(SwitchEntity):
    """Representation of a Transmission switch."""

    _attr_should_poll = False

    def __init__(
        self,
        qb_client: QBittorrentClient,
        config_entry: ConfigEntry,
        name: str,
        switch_type: str,
    ):
        """Initialize the Transmission switch."""
        self._name = name
        self.type = switch_type
        self._qb_client = qb_client
        self._state = STATE_OFF
        self.unsub_update = None
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Transmission",
            name=config_entry.title,
        )
        self._config_entry = config_entry

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._config_entry.title} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._config_entry.entry_id}-{self.type}"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._qb_client.api.available

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.type == SWITCH_TYPE_ON_OFF:
            _LOGGING.debug("Starting all torrents")
            self._qb_client.api.resume_all_torrent()
        elif self.type == SWITCH_TYPE_ALTERNATIVE_SPEED:
            _LOGGING.debug("Enable alternative speed")
            self._qb_client.api.set_alternative_speed(True)
        self._qb_client.api.update()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.type == SWITCH_TYPE_ON_OFF:
            _LOGGING.debug("Pausing all torrents")
            self._qb_client.api.pause_all_torrent()
        elif self.type == SWITCH_TYPE_ALTERNATIVE_SPEED:
            _LOGGING.debug("Disabled alternative speed")
            self._qb_client.api.set_alternative_speed(False)
        self._qb_client.api.update()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass,
            self._qb_client.api.signal_update,
            self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        active = None
        if self.type == SWITCH_TYPE_ON_OFF:
            active = self._qb_client.api.active_torrent_count > 0

        elif self.type == SWITCH_TYPE_ALTERNATIVE_SPEED:
            active = self._qb_client.api.alternative_speed_enabled

        if active is None:
            return

        self._state = STATE_ON if active else STATE_OFF
