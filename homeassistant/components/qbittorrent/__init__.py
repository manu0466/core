"""The qbittorrent component."""
from datetime import timedelta
import logging

import qbittorrent
from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
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
)
from .errors import AuthenticationError, CannotConnect
from .helpers import setup_client
from .qbittorrent_types import Torrent

PLATFORMS = [Platform.SENSOR]

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


async def get_client(hass: HomeAssistant, entry):
    """Creates a new qbittorrent.Client instance"""
    # Get configuration
    url = entry[CONF_URL]
    username = entry[CONF_USERNAME]
    password = entry[CONF_PASSWORD]
    verify_ssl = entry[CONF_VERIFY_SSL]

    try:
        client = await hass.async_add_executor_job(
            setup_client, url, username, password, verify_ssl
        )
    except LoginRequired as err:
        _LOGGER.error("Credentials for qBittorrent client are not valid")
        raise AuthenticationError from err
    except RequestException as err:
        _LOGGER.error("Connecting to the qBittorrent client %s failed", url)
        raise CannotConnect from err

    _LOGGER.debug("Successfully connected to %s", url)
    return client


class QBittorrentClient:
    """QBittorrentClient client object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """QBittorrentClient client constructor"""
        self.hass = hass
        self.config_entry = config_entry
        self.qb_client: qbittorrent.Client = None
        self.qb_data: QBittorrentData = None
        self.unsub_timer = None

    async def async_setup(self) -> None:
        """Sets up the QBittorrentClient instance"""
        try:
            self.qb_client = await get_client(self.hass, self.config_entry.data)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise ConfigEntryNotReady from err

        self.qb_data = QBittorrentData(self.hass, self.config_entry, self.qb_client)

        await self.hass.async_add_executor_job(self.qb_data.init_torrent_list)
        await self.hass.async_add_executor_job(self.qb_data.update)

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
            self.qb_data.update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )


class QBittorrentData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, client: qbittorrent.Client
    ) -> None:
        """Initialize the QBittorrentData"""
        self.hass = hass
        self.config = config
        self.available: bool = True
        self.data: dict[str, str] = {}
        self._client: qbittorrent.Client = client
        self._all_torrents: list[Torrent] = []
        self._torrents: list[Torrent] = []
        self._completed_torrents: list[Torrent] = []
        self._started_torrents: list[Torrent] = []
        self._alternative_speed_enabled: bool = False

    @property
    def url(self):
        """Return the server port."""
        return self.config.data[CONF_URL]

    @property
    def signal_update(self):
        """Update signal per qbittorrent entry."""
        return f"{DATA_UPDATED}-{self.url}"

    def _get_torrents(self) -> list[Torrent]:
        json_torrents = self._client.torrents()
        return [Torrent(json) for json in json_torrents]

    def init_torrent_list(self):
        """Initialize torrent lists."""
        self._torrents = self._get_torrents()
        self._completed_torrents = [
            torrent for torrent in self._torrents if torrent.is_completed
        ]
        self._started_torrents = [
            torrent for torrent in self._torrents if torrent.is_downloading
        ]

    def update(self):
        """Get the latest data from Transmission instance."""
        try:
            self.data = self._client.sync_main_data()
            self._alternative_speed_enabled = (
                self._client.get_alternative_speed_status() == 1
            )
            self._torrents = self._get_torrents()
            self.check_completed_torrent()
            self.check_started_torrent()
            self.check_removed_torrent()
            _LOGGER.debug("Torrent Data for %s Updated", self.url)
            _LOGGER.debug(self.data)

            self.available = True
        except RequestException:
            self.available = False
            _LOGGER.error("Unable to connect to qBittorrent client %s", self.url)

        dispatcher_send(self.hass, self.signal_update)

    def check_completed_torrent(self):
        """Get completed torrent functionality."""
        old_completed_torrent_names = {
            torrent.name for torrent in self._completed_torrents
        }

        current_completed_torrents = [
            torrent for torrent in self._torrents if torrent.is_completed
        ]

        for torrent in current_completed_torrents:
            if torrent.name not in old_completed_torrent_names:
                self.hass.bus.fire(
                    EVENT_DOWNLOADED_TORRENT,
                    {"name": torrent.name, "hash": torrent.hash},
                )

        self._completed_torrents = current_completed_torrents

    def check_started_torrent(self):
        """Get started torrent functionality."""
        old_started_torrent_names = {torrent.name for torrent in self._started_torrents}

        current_started_torrents = [
            torrent for torrent in self._torrents if torrent.is_downloading
        ]

        for torrent in current_started_torrents:
            if torrent.name not in old_started_torrent_names:
                self.hass.bus.fire(
                    EVENT_STARTED_TORRENT, {"name": torrent.name, "hash": torrent.hash}
                )

        self._started_torrents = current_started_torrents

    def check_removed_torrent(self):
        """Get removed torrent functionality."""
        current_torrent_names = {torrent.name for torrent in self._torrents}

        for torrent in self._torrents:
            if torrent.name not in current_torrent_names:
                self.hass.bus.fire(
                    EVENT_REMOVED_TORRENT, {"name": torrent.name, "hash": torrent.hash}
                )

        self._all_torrents = self._torrents.copy()
