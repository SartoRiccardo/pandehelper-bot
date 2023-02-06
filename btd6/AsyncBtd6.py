import btd6.model.Ct
from typing import List
import aiohttp


class AsyncBtd6:
    @staticmethod
    async def ct() -> List[btd6.model.Ct.Ct]:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://data.ninjakiwi.com/btd6/ct") as response:
                data = await response.json()
                ct_info = []
                for event in data["body"]:
                    ct_info.append(btd6.model.Ct.Ct(
                        event["id"], event["start"], event["end"]
                    ))
                return ct_info
