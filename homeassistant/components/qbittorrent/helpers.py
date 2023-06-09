"""Helper functions for qBittorrent."""
from qbittorrentapi.client import Client


def setup_client(host: str, port: int, username: str, password: str, verify_ssl: bool) -> Client:
    """Create a qBittorrent client."""

    client = Client(
        host=host, port=port, username=username,
        password=password, VERIFY_WEBUI_CERTIFICATE=verify_ssl,
        DISABLE_LOGGING_DEBUG_OUTPUT=True
    )
    return client
