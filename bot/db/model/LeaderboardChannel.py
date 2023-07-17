from dataclasses import dataclass


@dataclass
class LeaderboardChannel:
    guild_id: int
    channel_id: int
