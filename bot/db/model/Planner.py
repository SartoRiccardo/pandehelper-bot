import datetime
from dataclasses import dataclass, field


@dataclass
class Planner:
    planner_channel: int
    claims_channel: int
    ping_role: int
    ping_role_with_tickets: int
    ping_channel: int
    cleared_at: datetime.datetime = field(repr=False)
    is_active: bool

    @property
    def team_role(self) -> int:
        return self.ping_role
