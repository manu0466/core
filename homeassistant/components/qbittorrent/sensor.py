"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    STATE_IDLE,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QBittorrentClient
from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        name="Status",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        icon="mdi:cloud-download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        icon="mdi:cloud-upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""
    client: QBittorrentClient = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        QBittorrentSensor(description, client, config_entry)
        for description in SENSOR_TYPES
    ]
    async_add_entites(entities, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human-readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(SensorEntity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        qbittorrent_client: QBittorrentClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        self.entity_description = description
        self._client = qbittorrent_client
        self._config_entry = config_entry
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._config_entry.title} {self.entity_description.name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._config_entry.entry_id}-{self.entity_description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._client.qb_data.available

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._client.qb_data.signal_update, update
            )
        )

    def update(self) -> None:
        """Get the latest data from qBittorrent and updates the state."""
        download = self._client.qb_data.data["server_state"]["dl_info_speed"]
        upload = self._client.qb_data.data["server_state"]["up_info_speed"]

        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._state = "up_down"
            elif upload > 0 and download == 0:
                self._state = "seeding"
            elif upload == 0 and download > 0:
                self._state = "downloading"
            else:
                self._state = STATE_IDLE

        elif sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
        elif sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)
