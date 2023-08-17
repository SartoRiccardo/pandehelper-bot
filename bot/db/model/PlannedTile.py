import datetime
from dataclasses import dataclass, field


@dataclass
class PlannedTile:
    tile: str
    claimed_at: datetime.datetime  #: Time it was captured
    claimed_by: int or None  #: Member who claimed it *in the planner*, not in game
    planner_channel: int = field(repr=False)
    claims_channel: int = field(repr=False)
    ping_role: int = field(repr=False)
    ping_channel: int = field(repr=False)
    expires_in_hr: int = field(repr=True, default=24)

    @property
    def expires_at(self) -> datetime.datetime:
        return self.claimed_at + datetime.timedelta(hours=self.expires_in_hr)
