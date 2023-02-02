# CT Ticket Tracker
Tracks ticket usage on Pandemonium.

## Usage

Requires a postgres database

### Setup

1. Clone the repo
2. Install the dependencies in `requirements.txt`
3. Rename `config.example.py` into `config.py` and fill it out accordingly
4. Execute the contents of `db_init.sql` into your postgres database
5. Run the `ct-ticket-tracker.py`

### Setting up the tile log channel

Type `,,,track [channel-mention]`. The bot will start checking that channel for tile claims.

To unclaim a channel, type `,,,untrack [channel-mention]`.

**You need admin perms to run these commands.**

### Check ticket usage

To check ticket usage, type `,,,tickets [channel-mention]`. This will tell you how many tiles were claim by each user on which days on that channel.

To check past events, type `,,,tickets [channel-mention] [event-number]`.

**You need admin perms to run this command.**

### Logging a tile

A tile is considered logged when a member reacts to the tile claim message with ✅ or 👍.