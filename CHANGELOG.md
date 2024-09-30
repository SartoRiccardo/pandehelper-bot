# Changelog

## 1.9.0 - 2024-XX-XX

### Added
- Added [pandehelper.sarto.dev](https://pandehelper.sarto.dev)
- Added `CHANGELOG.md`
- Added `/regs sorted` and `/regs race`

### Changed
- `/raceregs` is deprecated in favor of `/regs race` and will be removed in a future version.
- `/tile` now also shows estimated time to complete a tile.
- Planner changes:
  - Planner channels always resend the message when they need to update. This is to avoid rate limits.
  - Team members can now claim 4 tiles *per CT day* instead of in total
  - Banners expiring on Last Day gradually show when they're more worth than a regular tile. They still don't ping.
  - Bot sends less messages when interacting with the UI (e.g. pressing buttons) if not needed
