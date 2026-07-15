# Module Overview

The bot is composed of multiple modules, all **enabled on demand** via the `enabled` switch in `config.yaml` (disabled by default). Modules fall into three categories:

- **Command modules**: register slash / prefix commands for users to invoke (using the discord.py Cog architecture).
- **Event modules**: no commands; listen to Discord events (such as `on_message`) and run automatically.
- **Service modules**: no commands; provide shared capabilities to other modules (such as audit logging).

## Module List

| Module | Config Key | Type | Commands | Docs |
| --- | --- | --- | --- | --- |
| Tools / Admin | `tools` | Command | `random` `uuid` `to-file` `delete` `clear-message` `move-channel` | [View](/en/modules/tools) |
| Emoji | `emoji` | Command | `/e` `/emoji info` `/emoji update` | [View](/en/modules/emoji) |
| Channel Lock | `lock` | Command | `/lock now` `/lock unlock` `/lock plan` `/lock unplan` | [View](/en/modules/lock) |
| Voice Channel | `voicechannel` | Command | `/vc join` `/vc leave` | [View](/en/modules/voice) |
| Admin Commands | — | Command | `/sync` `/reload` | [View](/en/modules/admin) |
| Dynamic Permissions | `perm` | Command | `/perm add` `/perm rm` `/perm show` | [View](/en/modules/perm) |
| Announcement Push | `announce` | Command | `/subscribe` | [View](/en/modules/announce) |
| Multilingual | — (always enabled) | Command | `/lang` | [View](/en/modules/lang) |
| Auto Management | `rmmsg` / `rmtodo` | Event | None | [View](/en/modules/manage) |
| Anti-spam | `antispam` | Event | None | [View](/en/modules/antispam) |
| Audit Log | `audit` | Service | None | [View](/en/modules/audit) |

## Command Quick Reference

| Command | Module | Permission | Rate Limit | Description |
| --- | --- | --- | --- | --- |
| `/random` | tools | Everyone | ✅ | Generate a random number within a range |
| `/uuid` | tools | Everyone | ✅ | Generate a UUID (ephemeral message) |
| `/to-file` | tools | Everyone | ✅ | Send text as a file |
| `/delete` | tools | Mod | — | Delete a single message |
| `/clear-message` | tools | Mod | — | Batch clear messages by conditions |
| `/move-channel` | tools | Mod | — | Move channel position / category |
| `/e` | emoji | Everyone | — | Send an emoji from the library |
| `/emoji info` | emoji | Everyone | — | View emoji library info |
| `/emoji update` | emoji | Admin | — | Update emoji library data |
| `/lock now` | lock | Mod | — | Lock a channel |
| `/lock unlock` | lock | Mod | — | Unlock a channel |
| `/lock plan` | lock | Mod | — | Schedule lock / unlock |
| `/lock unplan` | lock | Mod | — | Cancel a schedule |
| `/vc join` | voice | Whitelist / Mod | — | Bot joins a voice channel |
| `/vc leave` | voice | Whitelist / Mod | — | Bot leaves a voice channel |
| `/sync` | admin | Config admin | — | Sync the slash command list |
| `/reload` | admin | Admin | 15s CD | Hot reload modules |
| `/perm add` | perm | Admin | — | Add a permission rule |
| `/perm rm` | perm | Admin | — | Remove a permission rule |
| `/perm show` | perm | Admin | — | View permission rules |
| `/subscribe` | announce | Mod | — | Follow an announcement channel |
| `/lang` | lang | Everyone (server scope requires admin permission) | ✅ | Switch / view language preference |

> For the permission system, see [Permission System](/en/guide/permissions); for rate limiting, see [Rate Limit](/en/guide/rate-limit).

## Dual Command Mode

All command modules can control the registration of slash and prefix commands separately via the `slash` / `prefix` switches. The prefix for prefix commands is determined by the top-level `command_prefix` (the example config uses `//`).

- Slash command example: `/random 1 100`
- Prefix command example: `//random 1 100`

Complex commands (`clear-message`, `lock plan`) use `--key=value` flags to pass arguments in their prefix form, for example:

```
//lock plan --channel=#announcements --lock-time=22-00 --unlock-time=08-00 --cycle=daily
```
