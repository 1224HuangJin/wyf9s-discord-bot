# Channel Lock (lock)

Lock / unlock channels (preventing `@everyone` from speaking / joining), with support for **scheduled locking** (one-time or daily / weekly / monthly cycles).

- **Config key**: `lock`
- **Source file**: `cogs/lock.py`
- **Data file**: `schedules.yaml` (persistence for scheduled locks, auto-generated)

## How Locking Works

It works by modifying the channel's **permission overwrites** for `@everyone` (`default_role`):

- Text channels: `send_messages` / `send_messages_in_threads` are set to deny.
- Voice / stage channels: `connect` is additionally set to deny.
- Unlocking resets the above permission overwrites to "inherit (None)".

Therefore the bot needs **Manage Roles / Manage Channels** related permissions, with a sufficient role hierarchy.

## Commands

### `/lock now` — Lock a Channel

| Item | Description |
| --- | --- |
| Permission | Mod |
| Parameters | `channel` (optional, default current channel) |
| Audit | ✅ Recorded (`lock`) |

- After locking, a `:lock: Channel locked` message is sent in the channel (voice channels additionally note that joining is not possible).
- Locking clears any existing scheduled lock records for that channel.

### `/lock unlock` — Unlock a Channel

| Item | Description |
| --- | --- |
| Permission | Mod |
| Parameters | `channel` (optional, default current channel) |
| Audit | ✅ Recorded (`unlock`) |

### `/lock plan` — Schedule Lock / Unlock

Set a scheduled lock / unlock plan for a channel, supporting one-time and recurring schedules.

| Item | Description |
| --- | --- |
| Permission | Mod |
| Audit | ✅ Recorded (`plan-lock`) |

#### Parameters

| Parameter | Format / Description |
| --- | --- |
| `channel` | Target channel (optional, default current channel) |
| `lock_day` | Lock date: `yyyy-mm-dd` / `mm-dd` / `dd` |
| `lock_time` | Lock time: `hh-mm` (also supports `hh:mm`) |
| `unlock_day` | Unlock date |
| `unlock_time` | Unlock time |
| `cycle` | Cycle: `daily` / `mon,tue,...` / `1,2,3` / `1-5` |
| `cycle_start` | Cycle start date (`yyyy-mm-dd`) |
| `cycle_end` | Cycle end date (`yyyy-mm-dd`) |

- At least one of the lock or unlock time must be specified.
- Times are parsed as **UTC+8** (China Standard Time) and then converted to UTC for storage.
- `cycle` explanation:
  - `daily`: every day
  - Weekdays: `mon,tue,wed,thu,fri,sat,sun` (also supports Chinese `周一`…`周日`)
  - Days of the month: `1,2,3` or range `1-5`
- One-time schedules are cleared automatically after execution; recurring schedules are kept until `cycle_end` is passed.
- The scheduler **checks once per minute** (started after `on_ready`).

#### Prefix Command Flags

```
//lock plan --channel=#announcements --lock-time=22-00 --unlock-time=08-00 --cycle=daily
```

Supported flags: `--channel` `--lock-day` `--lock-time` `--unlock-day` `--unlock-time` `--cycle` `--cycle-start` `--cycle-end`.

### `/lock unplan` — Cancel a Schedule

Cancel an existing scheduled lock.

| Item | Description |
| --- | --- |
| Permission | Mod |
| Parameters | `index` (schedule number, slash command has **autocomplete**) |
| Audit | ✅ Recorded (`unplan-lock`) |

- If an invalid number is passed, all current schedules and their numbers are listed for selection.

## Configuration

```yaml
lock:
  enabled: false
  slash: true
  prefix: true
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Whether to enable the lock module |
| `slash` | `bool` | `true` | Whether to register slash commands |
| `prefix` | `bool` | `true` | Whether to register prefix commands |

::: warning
Execution of scheduled locks is unaffected by whether the caller is online; it only requires the bot to be running. Schedule data is saved in `schedules.yaml` and remains in effect after a restart.
:::
