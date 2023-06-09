"""Constants for qBittorrent."""
from typing import Final

DOMAIN: Final = "qbittorrent"

DEFAULT_NAME = "qBittorrent"
DEFAULT_URL = "http://127.0.0.1:8080"
DEFAULT_SCAN_INTERVAL = 120

DATA_UPDATED = "qbittorrent_data_updated"

EVENT_STARTED_TORRENT = "qbittorrent_started_torrent"
EVENT_REMOVED_TORRENT = "qbittorrent_removed_torrent"
EVENT_DOWNLOADED_TORRENT = "qbittorrent_downloaded_torrent"
