import datetime
from dataclasses import dataclass, field


@dataclass
class PlannedTile:
    tile: str
    claimed_at: datetime.datetime  #: Time it was captured
    claimed_by: int or None
    planner_channel: int = field(repr=False)
    claims_channel: int = field(repr=False)
    ping_role: int = field(repr=False)
    ping_channel: int = field(repr=False)
