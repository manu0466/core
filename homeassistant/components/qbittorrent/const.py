"""Constants for qBittorrent."""
from typing import Final

DOMAIN: Final = "qbittorrent"

DEFAULT_NAME = "qBittorrent"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 120

DATA_UPDATED = "qbittorrent_data_updated"

EVENT_STARTED_TORRENT = "qbittorrent_started_torrent"
EVENT_REMOVED_TORRENT = "qbittorrent_removed_torrent"
EVENT_DOWNLOADED_TORRENT = "qbittorrent_downloaded_torrent"

QBITTORRENT_INFO_KEY_DOWNLOAD_RATE = "dl_info_speed"
QBITTORRENT_INFO_KEY_UPLOAD_RATE = "up_info_speed"
QBITTORRENT_INFO_KEY_DOWNLOAD_LIMIT = "dl_rate_limit"
QBITTORRENT_INFO_KEY_UPLOAD_LIMIT = "up_rate_limit"

STATE_UP_DOWN = "up_down"
STATE_SEEDING = "seeding"
STATE_DOWNLOADING = "downloading"
