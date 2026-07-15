# Audit Log (audit)

A **shared service module** that records **operations that require auditing** as embeds to a specified channel. It has **no commands** and is called by other modules.

- **Config key**: `audit`
- **Source file**: `modules/audit.py`

## Recording Scope

Only **meaningful admin / server-level operations** are recorded, to avoid useless logs taking up space:

- Commands marked with **[ADMIN]** / **[MOD]** (such as `/delete`, `/lock`, `/reload`, `/perm`…).
- Modifications / operations at **server scope** (such as `/lang scope:server`, `/vc join/leave`, `/move-channel`).
- Automated actions and errors (anti-spam auto kick / ban / mute, slash command errors).

Ordinary user-scope commands (such as `/random`, `/uuid`, `/to-file`, `/lang` (user scope)) are **not recorded**.

## How It Works

After performing the operations above, other modules call `AuditLogger.log(...)`, and the log is sent to:

- **Global channel**: `global_channel`, where operations from all servers are sent.
- **Per-server channel**: a channel configured individually for the corresponding server in `guilds`.

The two are **independent**: if both are configured, both channels receive the log (deduplicated per channel, with the global one taking precedence). The embed for each language is built only once and cached.

The bot needs **Send Messages / Embed Links** permissions in the log channel; the target must be a text channel or a thread, otherwise it will be skipped with a warning.

## Log Content

Each log is an embed containing (displayed in the configured language):

- **Title**: distinguishes manual / automatic operations and success / failure (✅ / ❌ / 🚨 / ⚠️).
- **Action**: e.g. `/delete`, `clear-message`, `antispam-auto-catch`.
- **Actor**: mention + username + ID.
- **Server**, **Channel** (if any).
- **Detail**: operation description (max 1024 characters).
- **Timestamp** (UTC).

## Which Operations Are Recorded

| Source module | Action name |
| --- | --- |
| tools | `delete`, `clear-message`, `move-channel` |
| admin | `sync`, `reload`, `reload-all`, `reload-config` |
| emoji | `emoji-update` |
| lock | `lock`, `unlock`, `plan-lock`, `unplan-lock` |
| voice | `joinvc`, `leavevc` |
| perm | `perm-add`, `perm-rm` |
| announce | `subscribe` |
| lang | `lang-server` (server scope modifications only) |
| antispam | `antispam-auto-catch` (automatic operation, includes failure records) |
| (global error handling) | `slash-error/<cmd>` |

## Localization

Supports both Chinese and English. The language is set via the `/lang` command (priority: user setting > server setting > default `zh`); see the [lang module docs](/en/modules/lang) for details.

| Language value | Description |
| --- | --- |
| `zh` | Chinese (default) |
| `en` | English |

## Configuration

```yaml
audit:
  enabled: false
  global_channel: null    # Global log channel ID (null to disable)
  guilds: {}              # Log channels configured per server
  # Example (channel ID only):
  #   123456789:  987654321
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Whether to enable the audit log |
| `global_channel` | `int \| null` | `null` | Global log channel ID (`null` to disable the global log) |
| `guilds` | `dict` | `{}` | Configured per server, see below |

### How to write `guilds`

The key is the server ID (a number or string), and the value is a channel ID (a number) or an object `{ channel: channel ID }`.

```yaml
audit:
  enabled: true
  global_channel: 111111111111111111
  guilds:
    222222222222222222: 333333333333333333      # Shorthand: channel ID only
    444444444444444444:
      channel: 555555555555555555
```

::: tip
If a module is enabled but `audit.enabled` is `false`, the related operations will not be logged (the module still works normally).
:::
