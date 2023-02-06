from dataclasses import dataclass, field


@dataclass
class CtLeaderboardTeam:
    id: str = field(repr=False)
    display_name: str
    score: int
    disbanded: bool
