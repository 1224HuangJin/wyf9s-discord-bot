import io

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger as l

from modules.audit import AuditLogger
import utils as u
from perm import PermStore


def _perm_permission(
    module: "PermCog",
    user: discord.User | discord.Member,
    guild: discord.Guild | None,
) -> bool:
    if u.is_admin(user, module.c):
        return True
    if u.is_server_admin(user):
        return True
    return False


class PermCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)
        self.perm_store: PermStore = getattr(bot, "perm_store", PermStore())
        bot.perm_store = self.perm_store  # ty:ignore[unresolved-attribute]

    # ========== /perm list ==========

    @app_commands.command(name="perm", description="[ADMIN] Manage dynamic permissions")
    @app_commands.describe(
        action="Action: add / rm / show",
        user="User(s): ID or name, comma-separated (required for add)",
        module="Module name (mutually exclusive with command)",
        command="Command name (mutually exclusive with module)",
        global_scope="Apply globally across all servers (default: False)",
        rid="Rule ID to remove (for rm)",
        scope='Show scope: "global" or "server" (default: server)',
        private="Send result via DM instead of channel",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="rm", value="rm"),
            app_commands.Choice(name="show", value="show"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    @u.requires(_perm_permission)
    async def perm(
        self,
        interaction: discord.Interaction,
        action: str,
        user: str | None = None,
        module: str | None = None,
        command: str | None = None,
        global_scope: bool = False,
        rid: int | None = None,
        scope: str = "server",
        private: bool = False,
    ):
        await self._handle_perm(
            interaction,
            action,
            user,
            module,
            command,
            global_scope,
            rid,
            scope,
            private,
        )

    async def _handle_perm(
        self,
        source,
        action: str,
        user: str | None,
        module: str | None,
        command: str | None,
        global_scope: bool,
        rid: int | None,
        scope: str,
        private: bool,
    ):
        if action == "add":
            await self._perm_add(source, user, module, command, global_scope, private)
        elif action == "rm":
            await self._perm_rm(
                source, user, module, command, rid, global_scope, private
            )
        elif action == "show":
            await self._perm_show(source, user, module, command, scope, private)
        else:
            await self._reply(
                source,
                ":x: **Invalid action. Use: add / rm / show**",
                ephemeral=True,
                private=False,
            )

    async def _perm_add(
        self,
        source,
        user: str | None,
        module: str | None,
        command: str | None,
        global_scope: bool,
        private: bool,
    ):
        is_interaction = isinstance(source, discord.Interaction)
        actor = source.user if is_interaction else source.author

        is_config = u.is_admin(actor, self.c)

        if not is_config and global_scope:
            await self._reply(
                source,
                ":x: **Server admins cannot add global rules**",
                ephemeral=True,
                private=private,
            )
            return

        if not user:
            await self._reply(
                source,
                ":x: **`user` is required for add**",
                ephemeral=True,
                private=private,
            )
            return

        if module and command:
            await self._reply(
                source,
                ":x: **`module` and `command` are mutually exclusive**",
                ephemeral=True,
                private=private,
            )
            return

        if not module and not command:
            await self._reply(
                source,
                ":x: **One of `module` or `command` is required**",
                ephemeral=True,
                private=private,
            )
            return

        users = [u.strip() for u in user.split(",") if u.strip()]
        if not users:
            await self._reply(
                source,
                ":x: **No valid users parsed**",
                ephemeral=True,
                private=private,
            )
            return

        guild_id = source.guild.id if source.guild and not global_scope else None

        rule = self.perm_store.add(
            users=users,
            module=module.lower() if module else None,
            command=command.lower() if command else None,
            global_scope=global_scope,
            guild_id=guild_id,
            created_by=actor.id,
        )

        # Check if any user is in config (locked)
        config_users = {str(x) for x in self.c.admins.users}
        locked_users = [uid for uid in users if uid in config_users]

        msg_lines = [
            f":white_check_mark: **Permission rule added** (ID: `{rule.id}`)",
            f"> Users: `{', '.join(users)}`",
        ]
        if module:
            msg_lines.append(f"> Module: `{module}`")
        if command:
            msg_lines.append(f"> Command: `{command}`")
        msg_lines.append(f"> Scope: {'global' if global_scope else 'server'}")
        if locked_users:
            msg_lines.append(
                f"> :lock: **Note**: user(s) `{', '.join(locked_users)}` "
                f"also in config.yaml (config takes precedence)"
            )

        await self._reply(
            source, "\n".join(msg_lines), ephemeral=False, private=private
        )

        if self.audit:
            await self.audit.log(
                action="perm-add",
                user=actor,
                guild=source.guild,
                channel=source.channel,
                detail=(
                    f"Added perm rule {rule.id}: users={users} "
                    f"module={module} command={command} global={global_scope}"
                ),
            )

    async def _perm_rm(
        self,
        source,
        user: str | None,
        module: str | None,
        command: str | None,
        rid: int | None,
        global_scope: bool,
        private: bool,
    ):
        is_interaction = isinstance(source, discord.Interaction)
        actor = source.user if is_interaction else source.author

        if rid is not None:
            removed = self.perm_store.remove(rid=rid)
            if not removed:
                await self._reply(
                    source,
                    f":x: **Rule ID `{rid}` not found**",
                    ephemeral=True,
                    private=private,
                )
                return
            r = removed[0]
            await self._reply(
                source,
                f":white_check_mark: **Removed rule `{rid}`**: "
                f"users=`{', '.join(r.users)}` "
                f"{'module=' + r.module if r.module else 'command=' + r.command if r.command else ''}",
                ephemeral=False,
                private=private,
            )
            if self.audit:
                await self.audit.log(
                    action="perm-rm",
                    user=actor,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"Removed perm rule {rid}",
                )
            return

        if not user and not module and not command:
            await self._reply(
                source,
                ":x: **Specify `rid` or at least one of `user`/`module`/`command`**",
                ephemeral=True,
                private=private,
            )
            return

        scope = "global" if global_scope else "server"
        guild_id = source.guild.id if source.guild else None
        matches = self.perm_store.find(
            user=user,
            module=module,
            command=command,
            scope=scope,
            guild_id=guild_id,
        )

        if not matches:
            await self._reply(
                source,
                ":x: **No matching rules found**",
                ephemeral=True,
                private=private,
            )
            return

        removed = []
        for m in matches:
            self.perm_store.remove(rid=m.id)
            removed.append(m)

        lines = [f":white_check_mark: **Removed {len(removed)} rule(s)**:"]
        for r in removed:
            lines.append(
                f"  `{r.id}`: users=`{', '.join(r.users)}` "
                f"{'module=' + r.module if r.module else 'command=' + r.command if r.command else ''}"
            )

        await self._reply(source, "\n".join(lines), ephemeral=False, private=private)

        if self.audit:
            await self.audit.log(
                action="perm-rm",
                user=actor,
                guild=source.guild,
                channel=source.channel,
                detail=f"Removed {len(removed)} perm rules",
            )

    async def _perm_show(
        self,
        source,
        user: str | None,
        module: str | None,
        command: str | None,
        scope: str,
        private: bool,
    ):
        guild_id = source.guild.id if source.guild else None
        guild = source.guild

        # Show server admins as built-in :lock: entries
        srv_admin_lines: list[str] = []
        if scope == "server" and guild:
            config_admins = {str(x) for x in self.c.admins.users}
            for member in guild.members:
                if member.guild_permissions.administrator:
                    uid = str(member.id)
                    if uid not in config_admins:
                        srv_admin_lines.append(
                            f"> :lock: :homes: Server Admin: `{member.name}` (`{uid}`)"
                        )

        rules = self.perm_store.find(
            user=user,
            module=module,
            command=command,
            scope=scope,
            guild_id=guild_id,
        )

        if not rules and not srv_admin_lines:
            await self._reply(
                source,
                ":information_source: **No permission rules found**",
                ephemeral=True,
                private=private,
            )
            return

        lines = [f"**Permission Rules** (scope: `{scope}`, {len(rules)} rule(s)):"]
        if srv_admin_lines:
            lines.append("**Built-in (Server Admins):**")
            lines.extend(srv_admin_lines)
            if rules:
                lines.append("**Dynamic Rules:**")
        config_users = {str(x) for x in self.c.admins.users}
        for r in rules:
            locked = any(uid in config_users for uid in r.users)

            lock_str = " :lock:" if locked else ""
            scope_str = ":globe_with_meridians:" if r.global_scope else ":homes:"
            rule_line = (
                f"`{r.id}`{lock_str} {scope_str} "
                f"users=`{', '.join(r.users)}` "
                f"{'module=' + r.module if r.module else 'command=' + r.command if r.command else ''}"
            )
            lines.append(rule_line)

        msg = "\n".join(lines)

        if len(msg) > 1900:
            buf = io.BytesIO(msg.encode("utf-8"))
            file = discord.File(fp=buf, filename="permissions.md")
            await self._reply(
                source,
                "Permissions too long, sent as file:",
                file=file,
                ephemeral=False,
                private=private,
            )
        else:
            await self._reply(source, msg, ephemeral=False, private=private)

    async def _reply(
        self,
        source,
        content: str | None = None,
        *,
        ephemeral: bool = False,
        private: bool = False,
        file: discord.File | None = None,
    ):
        is_interaction = isinstance(source, discord.Interaction)
        actor = source.user if is_interaction else source.author

        if private and is_interaction:
            try:
                dm = await actor.create_dm()
                await dm.send(content=content, file=file)
                if not source.response.is_done():
                    await source.response.send_message(
                        ":white_check_mark: **Sent via DM**", ephemeral=True
                    )
                else:
                    await source.followup.send(
                        ":white_check_mark: **Sent via DM**", ephemeral=True
                    )
            except discord.Forbidden:
                await self._direct_reply(
                    source, ":x: **Cannot DM you (DMs closed)**", ephemeral=True
                )
            return

        if private and not is_interaction:
            try:
                dm = await actor.create_dm()
                await dm.send(content=content, file=file)
                await source.send(":white_check_mark: **Sent via DM**", delete_after=10)
            except discord.Forbidden:
                await source.send(":x: **Cannot DM you (DMs closed)**", delete_after=10)
            return

        await self._direct_reply(source, content, ephemeral=ephemeral, file=file)

    async def _direct_reply(
        self,
        source,
        content: str | None = None,
        *,
        ephemeral: bool = False,
        file: discord.File | None = None,
    ):
        is_interaction = isinstance(source, discord.Interaction)

        if is_interaction:
            if source.response.is_done():
                kwargs = {}
                if file:
                    kwargs["file"] = file
                await source.followup.send(content, ephemeral=ephemeral, **kwargs)
            else:
                kwargs = {}
                if file:
                    kwargs["file"] = file
                await source.response.send_message(
                    content, ephemeral=ephemeral, **kwargs
                )
        else:
            kwargs = {}
            if file:
                kwargs["file"] = file
            await u.send_msg(source, content, ephemeral=ephemeral, **kwargs)  # ty:ignore[invalid-argument-type]


async def setup(bot: commands.Bot):
    if bot.config.perm.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(PermCog(bot))
        l.info("PermCog loaded.")
