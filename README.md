# CT Ticket Tracker
Originally a bot to track ticket usage in Pandemonium, it grew out of its scope and can now
be a versatile helper for many Contested territory Teams.

# Usage

If you are not interested in hosting your own instace, the `/help` command should provide all
the information you need.

# Hosting your own instance

## Requirements
1. A PostgreSQL database
   * If you can't get one, you must rewrite all functions in `cogs/db` to fit the stack you're using
2. Python 3.10 or higher

## Setup

1. Clone the repo
```bash
git clone https://github.com/SartoRiccardo/ct-ticket-tracker/
```
2. Install Python dependencies
```bash
python -m pip install -r requirements.txt
```
3. Rename `config.example.py` into `config.py` and populate it accordingly
4. Execute the contents of `db_init.sql` into your PostgreSQL database
   * Make sure the user you set in `config.py` has read/write permissions on that database and its tables
5. Change the emojis in `bot/utils/emojis.py`, chances are they'll be broken
6. Rename `bot/files/json/tags.example.json` into `bot/files/json/tags.json`
   1. Add/edit new tags if you want to
7. Rename `bot/files/json/banners.example.json` into `bot/files/json/banners.json`
   1. This file contains a list of banner tile codes that is used for the `Planner` cog. There is currently no command to update it so if you want to change it between CT events you have to rewrite the file yourself.
   2. If you don't want to use the `Planner` cog, you can leave the file with an empty array, but it **must** exist and contain valid JSON.
8. Run `ct-ticket-tracker.py`
9. To register its commands, type `,,,sync` to register them in all servers, or `,,,sync .` if you just want to sync them in your current guild.
10. If you want to load/unload specific cogs, type `,,,cog load [cogname]` or `,,,cog unload [cogname]`.
    1. Use `,,,cog list` to check which cogs are currently loaded
    2. Cog names are in camelCase and do not include the word `Cog` at the end. E.g.: `,,,cog load leaderboard`, `,,,cog load raidLog`

And you're done! ✨

## Cogs
The bot's functionality is divided into cogs.

### `Tracker`
The original purpose of this bot. Checks a channel for tile claims and logs them to a database, so you can look at an overview of ticket usage later.

### `Leaderboard`
Posts the global leaderboard hourly & calculates eco. Note that eco calcs are not perfect due to caching issues from Ninja Kiwi's API. Scores have a 5 or 10 minute margin of error.

### `Utils`
Various miscellaneous utilities that don't really fit in any other cog.

### `Verify`
Ties an user's OAK to their Discord account. Unused in my own hosted instance, due to the OAKs being currently useless for CT, but the modules is there and fully functional should it become relevant.
You can code other uses for OAK-Discord connections if you want, such as a special role if you have certain badges, etc...

### `Planner`
The current best planner bot around.
Posts an overview of tiles that must be constantly refreshed (e.g. banners), when they'll expire, and allows users to claim them early so the team can plan out recaptures.
When pinging people for missed recaptures, only pings people who still have tickets left.
Best used in combination with the `Tracker` cog, but is fully functional without it as well.

### `Owner`
Commands only accessible to the bot's owner, such as loading/unloading cogs and syncing the command tree.

### Janky cogs
These cogs are so specific to the Pandemonium server that many values (channel IDs, etc...) are hardcoded. Can be used if you change those values, though.
* `Welcome`: Creates a new, private channel for every new member that joins the server and automatically deletes it when a role is assigned to that member or when they leave.
* `RaidLogLegacy`: A fallback tilestrat forum in case the data to make `RaidLog` work becomes unavailable. Makes accessing a thread easy since Discord's search feature sucks. Served us well for 13 events.
  * There should be exactly 163 threads with the tile's code in the title, and each thread is reused for every season.
  * Those threads have to be created manually, there's no function to do that.

### Private cogs
These cogs don't work unless you have a way of getting specific data.
Feel free to unload all of these upon starting your bot.
You could even take them out of `ct-ticket-tracker.py`'s list of cogs to auto-load.

They will be made public once this data is made public as well through an API or something.
* `RaidLog`: The prettiest forum to post tile strats around.
* `Tiles`: Information about the map's tiles.
