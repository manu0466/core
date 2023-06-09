"""The qbittorrent component."""
from collections.abc import Callable
from datetime import timedelta
import logging
from time import sleep
from typing import cast

import qbittorrentapi
from qbittorrentapi import TorrentInfoList, TransferInfoDictionary
from qbittorrentapi.exceptions import (
    APIConnectionError,
    LoginFailed,
    Unauthorized401Error,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DATA_UPDATED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DOWNLOADED_TORRENT,
    EVENT_REMOVED_TORRENT,
    EVENT_STARTED_TORRENT,
    QBITTORRENT_INFO_KEY_DOWNLOAD_LIMIT,
    QBITTORRENT_INFO_KEY_DOWNLOAD_RATE,
    QBITTORRENT_INFO_KEY_UPLOAD_LIMIT,
    QBITTORRENT_INFO_KEY_UPLOAD_RATE,
)
from .errors import AuthenticationError, CannotConnect
from .helpers import setup_client

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up qBittorrent from a config entry."""
    client = QBittorrentClient(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await client.async_setup()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload qBittorrent config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def get_client(hass: HomeAssistant, entry) -> qbittorrentapi.Client:
    """Create a new qbittorrent.Client instance."""
    host = entry[CONF_HOST]
    try:
        client = await hass.async_add_executor_job(
            setup_client,
            host,
            entry[CONF_PORT],
            entry[CONF_USERNAME],
            entry[CONF_PASSWORD],
            entry[CONF_VERIFY_SSL],
        )
    except LoginFailed as err:
        _LOGGER.error("Credentials for qBittorrent client are not valid")
        raise AuthenticationError from err
    except Unauthorized401Error as err:
        _LOGGER.error("Credentials for qBittorrent client are not valid")
        raise AuthenticationError from err
    except APIConnectionError as err:
        _LOGGER.error("Connecting to the qBittorrent client %s failed", host)
        raise CannotConnect from err

    _LOGGER.debug("Successfully connected to %s", host)
    return client


class QBittorrentClient:
    """QBittorrentClient client object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """QBittorrentClient client constructor."""
        self.hass = hass
        self.config_entry = config_entry
        self.api: QBittorrentData = cast(QBittorrentData, None)
        self.unsub_timer: Callable[[], None] | None = None
        self._qb_client: qbittorrentapi.Client | None = None

    async def async_setup(self) -> None:
        """Set up the QBittorrentClient instance."""
        try:
            self._qb_client = await get_client(self.hass, self.config_entry.data)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise ConfigEntryNotReady from err

        self.api = QBittorrentData(self.hass, self.config_entry, self._qb_client)

        await self.hass.async_add_executor_job(self.api.init_torrent_list)
        await self.hass.async_add_executor_job(self.api.update)

        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

    def add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            scan_interval = self.config_entry.data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            options = {
                CONF_SCAN_INTERVAL: scan_interval,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    def set_scan_interval(self, scan_interval):
        """Update scan interval."""

        def refresh(event_time):
            """Get the latest data from Transmission."""
            self.api.update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )


class QBittorrentData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, client: qbittorrentapi.Client
    ) -> None:
        """Initialize the QBittorrentData."""
        self.hass = hass
        self.config = config
        self._client: qbittorrentapi.Client = client
        self._all_torrents: TorrentInfoList = TorrentInfoList([], client)
        self._torrents: TorrentInfoList = TorrentInfoList([], client)
        self._completed_torrents: TorrentInfoList = TorrentInfoList([], client)
        self._started_torrents: TorrentInfoList = TorrentInfoList([], client)
        self.alternative_speed_enabled: bool = False
        # Info about the content of this dictionary
        # https://github.com/qbittorrent/qBittorrent/wik1i/WebUI-API-(qBittorrent-4.1)#get-global-transfer-info
        self._transfer_info: TransferInfoDictionary = TransferInfoDictionary(
            {QBITTORRENT_INFO_KEY_DOWNLOAD_RATE: 0, QBITTORRENT_INFO_KEY_UPLOAD_RATE: 0}
        )
        self._available: bool = True

    def init_torrent_list(self):
        """Initialize torrent lists."""
        self._torrents = self._client.torrents.info()
        self._completed_torrents = [
            torrent for torrent in self._torrents if torrent.info.state_enum.is_complete
        ]
        self._started_torrents = [
            torrent
            for torrent in self._torrents
            if torrent.info.state_enum.is_downloading
        ]

    def update(self):
        """Get the latest data from the qBittorrent instance."""
        try:
            # Torrent update logic
            self._torrents = self._client.torrents.info()
            self.check_completed_torrent()
            self.check_started_torrent()
            self.check_removed_torrent()
            # Server statistics
            self._transfer_info = self._client.transfer.info
            self.alternative_speed_enabled = (
                self._client.transfer.speed_limits_mode == "1"
            )
            _LOGGER.debug("Torrent Data for %s Updated", self.host)
            self._available = True
        except APIConnectionError:
            self._available = False
            _LOGGER.error("Unable to connect to qBittorrent client %s", self.host)

        dispatcher_send(self.hass, self.signal_update)

    def check_completed_torrent(self):
        """Get completed torrent functionality."""
        old_completed_torrent_names = {
            torrent.name for torrent in self._completed_torrents
        }

        current_completed_torrents = [
            torrent for torrent in self._torrents if torrent.state_enum.is_complete
        ]

        for torrent in current_completed_torrents:
            if torrent.name not in old_completed_torrent_names:
                self.hass.bus.fire(
                    EVENT_DOWNLOADED_TORRENT,
                    {"name": torrent["name"], "hash": torrent["hash"]},
                )

        self._completed_torrents = current_completed_torrents

    def check_started_torrent(self):
        """Get started torrent functionality."""
        old_started_torrent_names = {torrent.name for torrent in self._started_torrents}

        current_started_torrents = [
            torrent
            for torrent in self._torrents
            if torrent.state_enum.is_downloading and not torrent.state_enum.is_paused
        ]

        for torrent in current_started_torrents:
            if torrent.name not in old_started_torrent_names:
                self.hass.bus.fire(
                    EVENT_STARTED_TORRENT,
                    {"name": torrent["name"], "hash": torrent["hash"]},
                )
        self._started_torrents = current_started_torrents

    def check_removed_torrent(self):
        """Get removed torrent functionality."""
        current_torrent_names = {torrent.name for torrent in self._torrents}

        for torrent in self._torrents:
            if torrent.name not in current_torrent_names:
                self.hass.bus.fire(
                    EVENT_REMOVED_TORRENT,
                    {"name": torrent["name"], "hash": torrent["hash"]},
                )

        self._all_torrents = self._torrents.copy()

    @property
    def signal_update(self):
        """Update signal per qbittorrent entry."""
        return f"{DATA_UPDATED}-{self.host}-{self.port}"

    @property
    def host(self) -> str:
        """Return the server host."""
        return self.config.data[CONF_HOST]

    @property
    def port(self) -> int:
        """Return the server host."""
        return self.config.data[CONF_PORT]

    @property
    def available(self) -> bool:
        """Gets the availability state of the server."""
        return self._available

    @property
    def download_speed(self) -> int:
        """Gets the server global download speed in bytes/s."""
        return cast(int, self._transfer_info[QBITTORRENT_INFO_KEY_DOWNLOAD_RATE])

    @property
    def download_limit(self) -> int:
        """Gets the server global download speed in bytes/s."""
        return cast(int, self._transfer_info[QBITTORRENT_INFO_KEY_DOWNLOAD_LIMIT])

    @property
    def upload_speed(self) -> int:
        """Gets the server global upload speed in bytes/s."""
        return cast(int, self._transfer_info[QBITTORRENT_INFO_KEY_UPLOAD_RATE])

    @property
    def upload_limit(self) -> int:
        """Gets the server global download speed in bytes/s."""
        return cast(int, self._transfer_info[QBITTORRENT_INFO_KEY_UPLOAD_LIMIT])

    @property
    def active_torrent_count(self):
        """Gets the number of active torrents."""
        return len(self._started_torrents)

    def resume_all_torrent(self):
        """Resume all the torrents."""
        self._client.torrents_resume("all")
        # Delay to give some time to the server to update its state.
        sleep(3)

    def pause_all_torrent(self):
        """Pause all the torrents."""
        self._client.torrents_pause("all")
        # Delay to give some time to the server to update its state.
        sleep(3)

    def set_alternative_speed(self, enabled: bool):
        """Enable/Disable the alternative speed limits."""
        self._client.transfer_set_speed_limits_mode(enabled)
