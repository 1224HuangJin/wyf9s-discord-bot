# AGENTS.md

## Code Quality

After making changes, always run:

```bash
uvx ruff check --fix && uvx ruff format && uvx ty check --fix
```

- `ruff check --fix` - lint and auto-fix
- `ruff format` - format code
- `ty check --fix` - type check and auto-fix

Fix any remaining errors before committing.

## Project Structure

```
config.py            # Pydantic config models + loader
config.yaml          # Runtime config (gitignored)
config.example.yaml  # Example config with docs
schedules.yaml       # Scheduled lock data (auto-generated)
main.py              # Bot entry point, module loading
utils.py             # Shared utilities
modules/
  audit.py           # Audit logging service (shared)
  emoji.py           # Emoji/sticker commands
  tools.py           # Utility/moderation commands
  lock.py            # Channel lock/unlock + scheduled locks
  manage.py          # Auto-delete event handlers
  voice.py           # Voice channel commands
  antispam.py        # Anti-spam message handler
  clear_message.py   # Bulk message clearing service (shared)
```

## Config System

- `config.yaml` - User-editable YAML config
- `config.py` - Pydantic `BaseModel` hierarchy validated on startup
- Each module has `enabled: bool = False` (default off)
- Slash/prefix toggles: `slash: bool = True`, `prefix: bool = True`

## Module Pattern

Modules are plain classes (not Cogs). Commands registered in `__init__`:

```python
class MyModule:
    def __init__(self, config: ConfigModel, client: commands.Bot, audit: AuditLogger | None):
        if self.c.mymodule.slash:
            self._register_slash_commands(client)
        if self.c.mymodule.prefix:
            self._register_prefix_commands(client)

    def _register_slash_commands(self, client):
        @client.tree.command(name='cmd', description='...')
        async def handler(interaction: discord.Interaction):
            await self._handle_cmd(interaction)

    def _register_prefix_commands(self, client):
        @client.command(name='cmd')
        async def handler(ctx: commands.Context):
            await self._handle_cmd(ctx)

    async def _handle_cmd(self, source):
        # Shared logic for both slash and prefix
        if isinstance(source, discord.Interaction):
            await source.response.send_message(msg)
        else:
            await source.send(msg)
```

## Type Checking Notes

- discord.py type stubs are strict about channel types
- Use `type: ignore[arg-type]` for `ctx.channel` / `interaction.channel` where guild context is assumed
- `AuditLogger.log()` accepts `discord.Thread` in channel parameter

## Documentation

- After modifying a module or adding new configuration fields, update `config.example.yaml` and sync `README.md` if needed.
- `config.example.yaml` — example config with inline docs (the source of truth for config fields)
- `README.md` — user-facing feature overview
- `AGENTS.md` — developer/agent instructions only (keep non-overlapping with README)

## Error Handling

- All slash command errors are caught by `client.tree.error` in `main.py`, which logs full tracebacks and sends to the global audit channel.
- Batch operations (e.g. `clear-message`, `announce`, `antispam-auto-catch`) should **not** log individual per-item failures to audit—log one summary at the end. Use `l.warning()` for per-item debug logging to avoid flooding audit channels.
- If audit logging itself fails (e.g. channel not found, Forbidden), catch and silently ignore.

@README.md
