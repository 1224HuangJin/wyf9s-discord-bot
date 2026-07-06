import io

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger as l

from modules.audit import AuditLogger
from i18n import t as _t, lang_of, ls
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
        u.set_perm_store(self.perm_store)
        self.lang_store = getattr(bot, "lang_store", None)

    def _tr(self, source, key: str, **kwargs) -> str:
        return _t(key, lang_of(source, self.lang_store), **kwargs)

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cur = current.lower()
        return [
            app_commands.Choice(name=name, value=name)
            for name in u.list_cog_names()
            if cur in name.lower()
        ][:25]

    # ========== /perm add | rm | show ==========

    perm_group = app_commands.Group(name="perm", description=ls("perm.cmd_desc"))

    @perm_group.command(name="add", description=ls("perm.cmd_add_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        global_scope=ls("perm.param_global_scope"),
        private=ls("perm.param_private"),
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_add(
        self,
        interaction: discord.Interaction,
        user: str,
        module: str | None = None,
        command: str | None = None,
        global_scope: bool = False,
        private: bool = False,
    ):
        await self._perm_add(interaction, user, module, command, global_scope, private)

    @perm_group.command(name="rm", description=ls("perm.cmd_rm_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        rid=ls("perm.param_rid"),
        global_scope=ls("perm.param_global_scope"),
        private=ls("perm.param_private"),
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_rm(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        module: str | None = None,
        command: str | None = None,
        rid: int | None = None,
        global_scope: bool = False,
        private: bool = False,
    ):
        await self._perm_rm(
            interaction, user, module, command, rid, global_scope, private
        )

    @perm_group.command(name="show", description=ls("perm.cmd_show_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        scope=ls("perm.param_scope"),
        private=ls("perm.param_private"),
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_show(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        module: str | None = None,
        command: str | None = None,
        scope: str = "server",
        private: bool = False,
    ):
        await self._perm_show(interaction, user, module, command, scope, private)

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
                self._tr(source, "perm.no_global_for_server_admin"),
                ephemeral=True,
                private=private,
            )
            return

        if not user:
            await self._reply(
                source,
                self._tr(source, "perm.user_required"),
                ephemeral=True,
                private=private,
            )
            return

        if module and command:
            await self._reply(
                source,
                self._tr(source, "perm.module_command_exclusive"),
                ephemeral=True,
                private=private,
            )
            return

        # neither module nor command -> grant mod (all mod commands)

        users = [u.strip() for u in user.split(",") if u.strip()]
        if not users:
            await self._reply(
                source,
                self._tr(source, "perm.no_valid_users"),
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

        scope_label = self._tr(
            source, "perm.scope_global" if global_scope else "perm.scope_server"
        )
        msg_lines = [
            self._tr(source, "perm.rule_added", id=rule.id),
            self._tr(source, "perm.rule_added_users", users=", ".join(users)),
        ]
        if module:
            msg_lines.append(self._tr(source, "perm.rule_added_module", module=module))
        elif command:
            msg_lines.append(
                self._tr(source, "perm.rule_added_command", command=command)
            )
        else:
            msg_lines.append(self._tr(source, "perm.rule_added_mod"))
        msg_lines.append(self._tr(source, "perm.rule_added_scope", scope=scope_label))
        if locked_users:
            msg_lines.append(
                self._tr(
                    source,
                    "perm.rule_added_locked_note",
                    users=", ".join(locked_users),
                )
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
                    self._tr(source, "perm.rule_not_found", rid=rid),
                    ephemeral=True,
                    private=private,
                )
                return
            r = removed[0]
            await self._reply(
                source,
                self._tr(
                    source,
                    "perm.rule_removed",
                    rid=rid,
                    users=", ".join(r.users),
                    target=self._rule_target(r),
                ),
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
                self._tr(source, "perm.rm_need_args"),
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
                self._tr(source, "perm.no_matching_rules"),
                ephemeral=True,
                private=private,
            )
            return

        removed = []
        for m in matches:
            self.perm_store.remove(rid=m.id)
            removed.append(m)

        lines = [self._tr(source, "perm.removed_count", count=len(removed))]
        for r in removed:
            lines.append(
                f"  `{r.id}`: users=`{', '.join(r.users)}` {self._rule_target(r)}"
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
                            self._tr(
                                source,
                                "perm.show_builtin_admin",
                                name=member.name,
                                id=uid,
                            )
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
                self._tr(source, "perm.no_rules"),
                ephemeral=True,
                private=private,
            )
            return

        lines = [self._tr(source, "perm.show_header", scope=scope, count=len(rules))]
        if srv_admin_lines:
            lines.append(self._tr(source, "perm.show_builtin_header"))
            lines.extend(srv_admin_lines)
            if rules:
                lines.append(self._tr(source, "perm.show_dynamic_header"))
        config_users = {str(x) for x in self.c.admins.users}
        for r in rules:
            locked = any(uid in config_users for uid in r.users)

            lock_str = " :lock:" if locked else ""
            scope_str = ":globe_with_meridians:" if r.global_scope else ":homes:"
            rule_line = (
                f"`{r.id}`{lock_str} {scope_str} "
                f"users=`{', '.join(r.users)}` "
                f"{self._rule_target(r)}"
            )
            lines.append(rule_line)

        msg = "\n".join(lines)

        if len(msg) > 1900:
            buf = io.BytesIO(msg.encode("utf-8"))
            file = discord.File(fp=buf, filename="permissions.md")
            await self._reply(
                source,
                self._tr(source, "perm.too_long"),
                file=file,
                ephemeral=False,
                private=private,
            )
        else:
            await self._reply(source, msg, ephemeral=False, private=private)

    @staticmethod
    def _rule_target(r) -> str:
        if r.module:
            return f"module={r.module}"
        if r.command:
            return f"command={r.command}"
        return "mod"

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
                        self._tr(source, "perm.sent_via_dm"), ephemeral=True
                    )
                else:
                    await source.followup.send(
                        self._tr(source, "perm.sent_via_dm"), ephemeral=True
                    )
            except discord.Forbidden:
                await self._direct_reply(
                    source, self._tr(source, "perm.cannot_dm"), ephemeral=True
                )
            return

        if private and not is_interaction:
            try:
                dm = await actor.create_dm()
                await dm.send(content=content, file=file)
                await source.send(self._tr(source, "perm.sent_via_dm"), delete_after=10)
            except discord.Forbidden:
                await source.send(self._tr(source, "perm.cannot_dm"), delete_after=10)
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
            await u.send_msg(source, content, ephemeral=ephemeral, **kwargs)


async def setup(bot: commands.Bot):
    if bot.config.perm.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(PermCog(bot))
        l.info("PermCog loaded.")
