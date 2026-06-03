# AGENTS.md

## Project Overview

Discord bot built with discord.py, using YAML config with Pydantic validation.

## Tech Stack

- **Python 3.13** (managed by **uv**)
- **discord.py** - Discord API
- **Pydantic v2** - Config validation
- **PyYAML** - Config file parsing
- **Loguru** - Logging
- **aiohttp** - Async HTTP requests

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
config.yaml        # Runtime config (gitignored)
config.py          # Pydantic config models + loader
main.py            # Bot entry point, module loading
utils.py           # Shared utilities
modules/
  audit.py         # Audit logging service (shared)
  emoji.py         # Emoji/sticker commands
  tools.py         # Utility/moderation commands
  manage.py        # Auto-delete event handlers
  voice.py         # Voice channel commands
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

## Permissions

Three-tier custom system (not Discord built-in):
1. **Server admins** - Discord `administrator` permission
2. **Config admins** - `config.yaml > admins.users`
3. **Mods** - `mods.users` (global) or `mods.guilds[guild_id]`

## Deployment

- pm2 on serv00 server
- `update.sh` for deployment

## Type Checking Notes

- discord.py type stubs are strict about channel types
- Use `type: ignore[arg-type]` for `ctx.channel` / `interaction.channel` where guild context is assumed
- `AuditLogger.log()` accepts `discord.Thread` in channel parameter
