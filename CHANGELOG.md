# Changelog

## 1.9.5 - 2024-11-17

## Fixed
- Planner reminder tasks shouldn't crash if the bot doesn't have access to a single channel.
- Planner decay ping shouldn't crash if the bot doesn't have access to a single channel.
- Tilestrat thread cleanup doesn't fail if it can't delete a single thread

## 1.9.4 - 2024-11-16

### Fixed
- Bumped `bloonspy` version as to not get blocked by the NinjaKiwi API

## 1.9.3 - 2024-10-30

### Fixed
- Planner should correctly inject new banners on CT start
- Leaderboard emoji making works more reliably

## 1.9.2 - 2024-10-21

### Changed
- The bot now has a custom error message when it doesn't have the permissions to execute something

### Fixed
- The bot no longer throws an error when, after editing a message that previously had a tile code, the new message doesn't have one
- "has tickets" role in the planner should be correctly indented

## 1.9.1 - 2024-10-15

### Changed
- The bot now tracks all messages containing a tile claim in a tracked channel, to prevent making too many API calls when checking if someone else is already doing a specific tile
- Bot default color changed to #0xff1744

## 1.9.0 - 2024-10-04

### Added
- Released [pandehelper.sarto.dev](https://pandehelper.sarto.dev)
- Added `CHANGELOG.md`
- Added `/regs sorted` and `/regs race`
- Added `/ctmap`

### Changed
- `/raceregs` is deprecated in favor of `/regs race` and will be removed in a future version.
- `/tile` now also shows estimated time to complete a tile.
- Planner changes:
  - Planner channels always resend the message when they need to update. This is to avoid rate limits.
  - Team members can now claim 4 tiles *per CT day* instead of in total
  - Banners expiring on Last Day gradually show when they're more worth than a regular tile. They still don't ping.
  - Bot sends less messages when interacting with the UI (e.g. pressing buttons) if not needed
- Tracker changes:
  - Bot reacts with a warning emote when attempting to claim a tile someone else is on
  - When claiming a tile, it autoclaims it in the planner too if possible
