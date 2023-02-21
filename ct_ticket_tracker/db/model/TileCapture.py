import datetime
from dataclasses import dataclass, field


@dataclass
class TileCapture:
    user_id: int = field(repr=False)
    tile: str
    channel_id: int = field(repr=False)
    message_id: int = field(repr=False)
    claimed_at: datetime.datetime
