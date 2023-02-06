import dataclasses
import btd6.model.CtLeaderboardTeam
from typing import List
import aiohttp


@dataclasses.dataclass
class Ct:
    id: str
    start: int
    end: int

    async def teams(self, page=1) -> List[btd6.model.CtLeaderboardTeam.CtLeaderboardTeam]:
        if 0 >= page or page > 100:
            return []

        async with aiohttp.ClientSession() as session:
            url = f"https://data.ninjakiwi.com/btd6/ct/{self.id}/leaderboard/team?page={page}"
            async with session.get(url) as response:
                data = await response.json()
                team_leaderboard = []
                for team in data["body"]:
                    team_leaderboard.append(btd6.model.CtLeaderboardTeam.CtLeaderboardTeam(
                        team["profile"][38:], team["displayName"].upper().replace(" (DISBANDED)", ""),
                        team["score"], "(disbanded)" in team["displayName"]
                    ))
                return team_leaderboard
