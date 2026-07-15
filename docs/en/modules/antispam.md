# Anti-Spam (antispam)

A channel-level anti-spam module based on the `on_message` event, with **no commands**. It configures catch rules for specified channels, automatically kicks / bans / times out the triggering user, and can clean up their recent messages, notify publicly, and write to the audit log.

- **Config key**: `antispam`
- **Source file**: `cogs/antispam.py` (reuses the cleanup capability of `modules/clear_message.py`)

## Decision Flow

For every **non-bot** message in a channel that has rules configured:

1. Ignore bot messages and direct messages.
2. Begin evaluation once the channel's `spam-catcher` rule is hit.
3. If the author has any role in `ignored-roles` → **skip**.
4. Determine the author's category:
   - **Stranger account (spammer)**: has no roles at all, **OR** all of its roles belong to `stranger-roles`.
   - **Normal account (hacked, suspected-compromised)**: all other cases.
5. Execute the corresponding action by category (`spammer` / `hacked`).
6. Optional: clean up the user's recent messages (`clear-message`), notify publicly in the channel (`public-log`).
7. Write the result (success / failure) to the [audit log](/en/modules/audit) (`antispam-auto-catch`, marked as an automatic operation).

## Actions and Required Permissions

| Action | Meaning | Discord permission the bot needs |
| --- | --- | --- |
| `kick` | Kick the member | Kick Members |
| `ban` | Ban the member | Ban Members |
| `mute` / minutes | Timeout (default 60 minutes, or a specified number of minutes) | Moderate Members / Timeout |

::: warning Role hierarchy
If the bot already has the corresponding permission but the operation is still denied, it is almost certainly a **role hierarchy problem**: the target's highest role is not lower than the bot's highest role. In this case, drag the bot's role above the target's. Such failures are recorded to the audit log as "automatic operation failed" with an explanation of the reason.
:::

## Result Notifications

- **Suspected compromised (mute)**: @s the user, indicating the account is suspected to be compromised, has been temporarily muted, and to contact an administrator (in both Chinese and English).
- **Stranger account (kick/ban)**: publicly records the triggered antispam action (in both Chinese and English). Since an @ mention of a member who has been kicked / banned will over time show as "Unknown User", the notification appends `` (`username`) `` after the mention for later identification.
- Whether to notify publicly is controlled by `public-log`.

## Message Snapshot (Audit)

When writing to the audit log, the triggering message is **forwarded** to the audit channel and a `Processing...` placeholder message is replied; once cleanup and other processing are complete, that placeholder message is edited into the final "automatic operation log" (with an undo button).

- It uses **forwarding** rather than building a snapshot: forwarding keeps a copy of the content in the audit channel, so even if the original message is subsequently cleaned up and deleted, images / attachments will not 404.
- Forwarding must complete **before** the original message is cleaned up and deleted; if forwarding fails, it falls back to building a self-made snapshot embed.

## Message Cleanup

When `clear-message` specifies a number of minutes, it cleans up the user's messages from the last N minutes across the **server scope** (internally reusing the bulk cleanup service, writing no extra audit entry, with the result merged into this record). Set to `null` / `false` to disable.

## Configuration

```yaml
antispam:
  enabled: false
  spam-catcher: {}        # Catch rules configured per channel
  # Example:
  # 1514685631316496615:
  #   spammer: ban              # Stranger handling: kick | ban
  #   hacked: mute              # Suspected-compromised handling: kick | ban | mute | minutes
  #   clear-message: 3          # Auto-cleanup window (minutes, null/false to disable)
  #   public-log: true          # Whether to notify publicly in the channel
  #   stranger-roles: [1318980288046698506, "New Member"]
  #   ignored-roles: ["Admin", "Member"]
```

### Top-level fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Whether to enable the anti-spam module |
| `spam-catcher` | `dict[channel ID, rule]` | `{}` | Catch rules configured per channel |

### Per-rule fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `spammer` | `kick` / `ban` | `ban` | How to handle stranger accounts |
| `hacked` | `kick` / `ban` / `mute` / minutes(int) | `mute` | How to handle suspected-compromised accounts |
| `clear-message` | `int` / `null` / `false` | `3` | Message cleanup window (minutes); `null`/`false` to disable |
| `public-log` | `bool` | `true` | Whether to notify the result publicly in the channel |
| `stranger-roles` | `list[int \| str]` | `[]` | List of roles treated as stranger accounts (role ID or name) |
| `ignored-roles` | `list[int \| str]` | `[]` | List of roles to skip processing (having any one is enough to skip) |

- The keys of `spam-catcher` are channel IDs (either numbers or strings).
- Role list items support **role ID** or **role name** (roles with the same name will all be matched).
