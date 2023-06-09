"""qBittorrent types."""
from enum import Enum


class TorrentState(Enum):
    """Enum that represents the status of a torrent."""

    DOWNLOADING = "downloading"
    UNKNOWN = "unknown"
    FAIL = "fail"
    SEEDING = "seeding"
    PAUSED = "seeding"
    DONE = "done"
    QUEUED = "queued"
    CHECKING = "checking"
    MOVING = "moving"
    STALLED = "stalled"
    METADATA = "metadata"

    @staticmethod
    def from_qbittorrent_state(state: str):
        """Create an instance of TorrentState from the state string received from qBittorrent."""
        match state:
            case "downloading":
                return TorrentState.DOWNLOADING
            case "forcedDL":
                return TorrentState.DOWNLOADING
            case "error":
                return TorrentState.FAIL
            case "missingFiles":
                return TorrentState.FAIL
            case "uploading":
                return TorrentState.SEEDING
            case "forcedUP":
                return TorrentState.SEEDING
            case "stalledUP":
                return TorrentState.SEEDING
            case "pausedDL":
                return TorrentState.PAUSED
            case "pausedUP":
                return TorrentState.DONE
            case "queuedUP":
                return TorrentState.QUEUED
            case "queuedDL":
                return TorrentState.QUEUED
            case "allocating":
                return TorrentState.CHECKING
            case "checkingDL":
                return TorrentState.CHECKING
            case "checkingUP":
                return TorrentState.CHECKING
            case "checkingResumeData":
                return TorrentState.CHECKING
            case "metaDL":
                return TorrentState.METADATA
            case "stalledDL":
                return TorrentState.STALLED
            case "moving":
                return TorrentState.MOVING
            case _:
                return TorrentState.UNKNOWN


class Torrent:
    """Class that represents a torrent."""

    def __init__(self, data) -> None:
        """Initialize the Torrent object."""
        self.added_on = data["added_on"]
        self.amount_left = data["amount_left"]
        self.auto_tmm = data["auto_tmm"]
        self.availability = data["availability"]
        self.category = data["category"]
        self.completed = data["completed"]
        self.completion_on = data["completion_on"]
        self.content_path = data["content_path"]
        self.dl_limit = data["dl_limit"]
        self.dlspeed = data["dlspeed"]
        self.download_path = data["download_path"]
        self.downloaded = data["downloaded"]
        self.downloaded_session = data["downloaded_session"]
        self.eta = data["eta"]
        self.f_l_piece_prio = data["f_l_piece_prio"]
        self.force_start = data["force_start"]
        self.hash = data["hash"]
        self.infohash_v1 = data["infohash_v1"]
        self.infohash_v2 = data["infohash_v2"]
        self.last_activity = data["last_activity"]
        self.magnet_uri = data["magnet_uri"]
        self.max_ratio = data["max_ratio"]
        self.max_seeding_time = data["max_seeding_time"]
        self.name = data["name"]
        self.num_complete = data["num_complete"]
        self.num_incomplete = data["num_incomplete"]
        self.num_leechs = data["num_leechs"]
        self.num_seeds = data["num_seeds"]
        self.priority = data["priority"]
        self.progress = data["progress"]
        self.ratio = data["ratio"]
        self.ratio_limit = data["ratio_limit"]
        self.save_path = data["save_path"]
        self.seeding_time = data["seeding_time"]
        self.seeding_time_limit = data["seeding_time_limit"]
        self.seen_complete = data["seen_complete"]
        self.seq_dl = data["seq_dl"]
        self.size = data["size"]
        self.state = TorrentState.from_qbittorrent_state(data["state"])
        self.super_seeding = data["super_seeding"]
        self.tags = data["tags"]
        self.time_active = data["time_active"]
        self.total_size = data["total_size"]
        self.tracker = data["tracker"]
        self.trackers_count = data["trackers_count"]
        self.up_limit = data["up_limit"]
        self.uploaded = data["uploaded"]
        self.uploaded_session = data["uploaded_session"]
        self.upspeed = data["upspeed"]

    @property
    def is_completed(self) -> bool:
        """Tells if the torrent has completed."""
        return self.state == TorrentState.SEEDING or self.state == TorrentState.DONE

    @property
    def is_downloading(self) -> bool:
        """Tells if the torrent is being downloaded."""
        return self.state == TorrentState.DOWNLOADING
