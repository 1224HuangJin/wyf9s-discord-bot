# Admin Commands (admin)

Provides command syncing and hot-reloading of modules.

- **Config key**: none (always loaded)
- **Source file**: `cogs/admin.py`

## Commands

### `/sync` — Sync slash commands

Syncs the slash command list to Discord (registers / updates the command tree).

| Item | Description |
| --- | --- |
| Permission | Admin (config admins only) |
| Audit | ✅ Logged |

### `/reload` — Hot-reload modules / config

Hot-updates modules or config without restarting the bot.

| Item | Description |
| --- | --- |
| Permission | Admin (config admins only) |
| Parameter | `module` (optional, see behavior below) |
| Cooldown | 15s / user |
| Audit | ✅ Logged (`reload` / `reload-all` / `reload-config`) |

The `module` parameter supports **dynamic autocomplete** (listed live from the `cogs/` directory, results cached for 1 second), with the following behaviors:

| Value | Behavior |
| --- | --- |
| Empty | **Reload all** loaded modules |
| `config` | **Reload config**: re-read `config.yaml` and reload all modules to apply changes |
| `<module name>` (e.g. `lock`) | Reload a single specified module; if the module is not currently loaded, it attempts to load it |

- Voice connections, rate-limit state, planned lock data, language preferences, etc. are stored on the bot instance and are not lost on reload.
- Reloading the `perm` module (or all / config) also reloads the `perm.yaml` dynamic permission data.
- A `config` reload only takes effect for **already loaded** modules; if the config changes a new module from "disabled" to "enabled", use `/reload <module name>` to load it individually or restart.
