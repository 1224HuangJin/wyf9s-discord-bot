# Auto Management (manage)

Automatic deletion based on the `on_message` event, with **no commands**. It contains two independent sub-features, controlled respectively by the `rmmsg` and `rmtodo` config.

- **Config keys**: `rmmsg` (delete messages by nickname), `rmtodo` (delete To-Do Bot messages)
- **Source file**: `cogs/manage.py`

::: tip Enabling condition
As long as either `rmmsg.enabled` **or** `rmtodo.enabled` is true, the module is loaded and registers the `on_message` listener.
:::

## rmmsg — Auto-delete messages by nickname pattern

When the message author's **username** matches any pattern in `nicks`, the message is automatically deleted (with a 2-second delay).

- Matching uses `fnmatch` and **supports wildcards** (e.g. `[DC] @system`, `*bot*`).
- The bot needs the **Manage Messages** permission.

### Configuration

```yaml
rmmsg:
  enabled: false
  nicks: []               # List of nickname patterns to auto-delete (wildcards supported)
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Whether to enable |
| `nicks` | `list[str]` | `[]` | List of nickname patterns to auto-delete (fnmatch wildcards) |

## rmtodo — Auto-delete To-Do Bot messages without embeds

In the specified todo channels, if a message meets **all** of the following conditions, it is deleted after a delay:

1. The channel ID is in `todo_channels`;
2. The author is the specified To-Do Bot (`author_id`);
3. The message **contains no embeds**.

Used to clean up plain-text / embed-less notification messages produced by the To-Do List Bot, while keeping the formal content that has embeds.

### Configuration

```yaml
rmtodo:
  enabled: false
  todo_channels: []                 # List of todo channel IDs
  author_id: 782105629572464652     # The To-Do Bot's user ID
  remove_delay: 3                   # Seconds to wait before deleting
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Whether to enable |
| `todo_channels` | `list[int]` | `[]` | List of todo channel IDs where it takes effect |
| `author_id` | `int` | `782105629572464652` | The To-Do Bot's user ID |
| `remove_delay` | `int` | `3` | Seconds to wait before deleting |
