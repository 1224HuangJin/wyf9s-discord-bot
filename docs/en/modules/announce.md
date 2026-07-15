# Announcement Following (announce)

Uses Discord's built-in **Channel Following** feature. A Mod uses `/subscribe` to make a local channel follow the announcement channel specified in the config, and messages are forwarded automatically.

- **Config key**: `announce`
- **Source file**: `cogs/announce.py`

## Configuration

```yaml
announce:
  source_channel: null  # Announcement channel ID (News Channel)
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `source_channel` | `int \| null` | `null` | Announcement channel ID; set to null to disable |

## Commands

### `/subscribe` — Follow the announcement channel

Makes the target channel in this server follow the configured announcement channel.

| Item | Description |
| --- | --- |
| Permission | Mod |
| Parameter | `target` (optional, defaults to the current channel) |
| Bot permission | **Manage Webhooks** in the target channel |

- After following, Discord automatically forwards messages from the announcement channel to the target channel
- To unfollow: delete the corresponding Webhook under channel settings → Integrations → Webhooks
