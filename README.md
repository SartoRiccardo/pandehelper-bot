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
7. Run `ct-ticket-tracker.py`

And you're done! ✨