# CT Ticket Tracker
Tracks ticket usage on Pandemonium.

## Usage

### Setup

1. Clone the repo
2. Rename `config.example.py` into `config.py` and fill it out accordingly
3. Run the `ct-ticket-tracker.py`

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