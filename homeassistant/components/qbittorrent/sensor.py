"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_IDLE,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import QBittorrentClient
from .const import DOMAIN, STATE_DOWNLOADING, STATE_SEEDING, STATE_UP_DOWN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""
    client: QBittorrentClient = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        QBittorrentSpeedSensor(client, config_entry, "Down Speed", SENSOR_TYPE_DOWNLOAD_SPEED),
        QBittorrentSpeedSensor(client, config_entry, "Up Speed", SENSOR_TYPE_UPLOAD_SPEED),
        QBittorrentStateSensor(client, config_entry, "Status", SENSOR_TYPE_CURRENT_STATUS)
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
            qbittorrent_client: QBittorrentClient,
            config_entry: ConfigEntry,
            name: str,
            key: str,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        self._client = qbittorrent_client
        self._config_entry = config_entry
        self._name = name
        self._key = key
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._config_entry.title} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._config_entry.entry_id}-{self._key}"

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


class QBittorrentSpeedSensor(QBittorrentSensor):
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 2
    _attr_suggested_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND

    def __init__(self, qbittorrent_client: QBittorrentClient, config_entry: ConfigEntry, name: str, key: str):
        super().__init__(qbittorrent_client, config_entry, name, key)
        if key == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._attr_icon = "mdi:cloud-download"
        elif key == SENSOR_TYPE_UPLOAD_SPEED:
            self._attr_icon = "mdi:cloud-upload"

    def update(self) -> None:
        """Get the latest data from qBittorrent and updates the state."""
        download = self._client.qb_data.download_speed
        upload = self._client.qb_data.upload_speed

        sensor_type = self._key
        if sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
        elif sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)


class QBittorrentStateSensor(QBittorrentSensor):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_IDLE, STATE_UP_DOWN, STATE_SEEDING, STATE_DOWNLOADING]
    _attr_translation_key = "qbittorrent_status"

    def update(self) -> None:
        """Get the latest data from qBittorrent and updates the state."""
        download = self._client.qb_data.download_speed
        upload = self._client.qb_data.upload_speed

        if upload > 0 and download > 0:
            self._state = STATE_UP_DOWN
        elif upload > 0 and download == 0:
            self._state = STATE_SEEDING
        elif upload == 0 and download > 0:
            self._state = STATE_DOWNLOADING
        else:
            self._state = STATE_IDLE
