
async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()
