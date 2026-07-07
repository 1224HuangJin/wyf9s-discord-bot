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
        u.set_bot_guild_lookup(self._lookup_member)
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

    @staticmethod
    def _bool_choices() -> list[app_commands.Choice[int]]:
        return [
            app_commands.Choice(name="True", value=1),
            app_commands.Choice(name="False", value=0),
        ]

    @staticmethod
    def _scope_choices() -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name="server", value="server"),
            app_commands.Choice(name="global", value="global"),
        ]

    def _lookup_member(
        self, guild_id: int, user_id: int | str
    ) -> discord.Member | None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None
        uid = (
            int(user_id) if isinstance(user_id, str) and user_id.isdigit() else user_id
        )
        return guild.get_member(uid) if isinstance(uid, int) else None

    # ========== /perm add | rm | show ==========

    perm_group = app_commands.Group(name="perm", description=ls("perm.cmd_desc"))

    @perm_group.command(name="add", description=ls("perm.cmd_add_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        role=ls("perm.param_role"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        global_scope=ls("perm.param_global_scope"),
        private=ls("perm.param_private"),
    )
    @app_commands.choices(global_scope=_bool_choices(), private=_bool_choices())
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_add(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        role: discord.Role | None = None,
        module: str | None = None,
        command: str | None = None,
        global_scope: int = 0,
        private: int = 0,
    ):
        await self._perm_add(
            interaction, user, role, module, command, bool(global_scope), bool(private)
        )

    @perm_group.command(name="rm", description=ls("perm.cmd_rm_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        role=ls("perm.param_role"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        rid=ls("perm.param_rid"),
        global_scope=ls("perm.param_global_scope"),
        private=ls("perm.param_private"),
    )
    @app_commands.choices(global_scope=_bool_choices(), private=_bool_choices())
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_rm(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        role: discord.Role | None = None,
        module: str | None = None,
        command: str | None = None,
        rid: int | None = None,
        global_scope: int = 0,
        private: int = 0,
    ):
        await self._perm_rm(
            interaction,
            user,
            role,
            module,
            command,
            rid,
            bool(global_scope),
            bool(private),
        )

    @perm_group.command(name="show", description=ls("perm.cmd_show_desc"))
    @app_commands.describe(
        user=ls("perm.param_user"),
        role=ls("perm.param_role"),
        module=ls("perm.param_module"),
        command=ls("perm.param_command"),
        scope=ls("perm.param_scope"),
        private=ls("perm.param_private"),
        show_server_mods=ls("perm.param_show_server_mods"),
        show_global=ls("perm.param_show_global"),
    )
    @app_commands.choices(  # ty:ignore[invalid-argument-type]
        scope=_scope_choices(),
        private=_bool_choices(),
        show_server_mods=_bool_choices(),
        show_global=_bool_choices(),
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @u.requires(_perm_permission)
    async def perm_show(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        role: discord.Role | None = None,
        module: str | None = None,
        command: str | None = None,
        scope: str = "server",
        private: int = 0,
        show_server_mods: int = 1,
        show_global: int = 0,
    ):
        await self._perm_show(
            interaction,
            user,
            role,
            module,
            command,
            scope,
            bool(private),
            bool(show_server_mods),
            bool(show_global),
        )

    async def _perm_add(
        self,
        source,
        user: str | None,
        role: discord.Role | None,
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

        if bool(user) == bool(role):
            await self._reply(
                source,
                self._tr(source, "perm.user_role_required"),
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

        users = (
            [part.strip() for part in user.split(",") if part.strip()] if user else []
        )
        roles = [str(role.id)] if role else []
        if not users and not roles:
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
            roles=roles,
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
        ]
        if users:
            msg_lines.append(
                self._tr(source, "perm.rule_added_users", users=", ".join(users))
            )
        if role:
            msg_lines.append(
                self._tr(source, "perm.rule_added_role", role=role.name, id=role.id)
            )
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
                    f"roles={roles} module={module} command={command} global={global_scope}"
                ),
            )

    async def _perm_rm(
        self,
        source,
        user: str | None,
        role: discord.Role | None,
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
                    subjects=self._rule_subject(r),
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

        if not user and role is None and not module and not command:
            await self._reply(
                source,
                self._tr(source, "perm.rm_need_args"),
                ephemeral=True,
                private=private,
            )
            return

        if user and role is not None:
            await self._reply(
                source,
                self._tr(source, "perm.user_role_required"),
                ephemeral=True,
                private=private,
            )
            return

        scope = "global" if global_scope else "server"
        guild_id = source.guild.id if source.guild else None
        matches = self.perm_store.find(
            user=user,
            role=role.id if role else None,
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
            lines.append(f"  `{r.id}`: {self._rule_subject(r)} {self._rule_target(r)}")

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
        role: discord.Role | None,
        module: str | None,
        command: str | None,
        scope: str,
        private: bool,
        show_server_mods: bool,
        show_global: bool,
    ):
        actor = (
            source.user if isinstance(source, discord.Interaction) else source.author
        )
        is_config_admin = u.is_admin(actor, self.c)
        guild_id = source.guild.id if source.guild else None
        guild = source.guild

        builtin_lines: list[str] = []
        if scope == "server" and guild and show_server_mods:
            builtin_lines.extend(self._collect_builtin_mod_lines(source, guild))

        global_lines: list[str] = []
        if private and show_global:
            if not is_config_admin:
                await self._reply(
                    source,
                    self._tr(source, "perm.no_permission_show_global"),
                    ephemeral=True,
                    private=False,
                )
                return
            global_lines = self._collect_global_visibility_lines(source)

        rules = self.perm_store.find(
            user=user,
            role=role.id if role else None,
            module=module,
            command=command,
            scope=scope,
            guild_id=guild_id,
        )

        if not rules and not builtin_lines and not global_lines:
            await self._reply(
                source,
                self._tr(source, "perm.no_rules"),
                ephemeral=True,
                private=private,
            )
            return

        lines = [self._tr(source, "perm.show_header", scope=scope, count=len(rules))]
        if builtin_lines:
            lines.append(self._tr(source, "perm.show_builtin_header"))
            lines.extend(builtin_lines)
            if rules:
                lines.append(self._tr(source, "perm.show_dynamic_header"))
        if global_lines:
            lines.append(self._tr(source, "perm.show_global_header"))
            lines.extend(global_lines)
            if rules and self._tr(source, "perm.show_dynamic_header") not in lines:
                lines.append(self._tr(source, "perm.show_dynamic_header"))
        config_users = {str(x) for x in self.c.admins.users}
        for r in rules:
            locked = any(uid in config_users for uid in r.users)

            lock_str = " :lock:" if locked else ""
            scope_str = ":globe_with_meridians:" if r.global_scope else ":homes:"
            rule_line = (
                f"`{r.id}`{lock_str} {scope_str} "
                f"{self._rule_subject(r)} "
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

    @staticmethod
    def _rule_subject(r) -> str:
        parts = []
        if r.users:
            parts.append(f"users=`{', '.join(r.users)}`")
        if r.roles:
            parts.append(f"roles=`{', '.join(r.roles)}`")
        return " ".join(parts) if parts else "subjects=`-`"

    def _collect_builtin_mod_lines(self, source, guild: discord.Guild) -> list[str]:
        owner_id = guild.owner_id
        config_admins = {str(x) for x in self.c.admins.users}
        config_mods = {str(x) for x in self.c.mods.users}
        guild_mods = {
            str(x)
            for x in self.c.mods.guilds.get(
                guild.id, self.c.mods.guilds.get(str(guild.id), [])
            )
        }
        lines: list[str] = []
        seen: set[int] = set()
        ordered_members = sorted(guild.members, key=lambda m: (m.id != owner_id, m.id))
        for member in ordered_members:
            uid = str(member.id)
            if member.id == owner_id:
                lines.append(
                    self._tr(
                        source, "perm.show_builtin_owner", name=member.name, id=uid
                    )
                )
                seen.add(member.id)
        for member in ordered_members:
            uid = str(member.id)
            if member.id in seen:
                continue
            if member.guild_permissions.administrator and uid not in config_admins:
                lines.append(
                    self._tr(
                        source, "perm.show_builtin_admin", name=member.name, id=uid
                    )
                )
                seen.add(member.id)
        for member in ordered_members:
            uid = str(member.id)
            if member.id in seen:
                continue
            if uid in config_mods or uid in guild_mods:
                lines.append(
                    self._tr(source, "perm.show_builtin_mod", name=member.name, id=uid)
                )
                seen.add(member.id)
        return lines

    def _collect_global_visibility_lines(self, source) -> list[str]:
        lines = []
        for uid in self.c.admins.users:
            lines.append(self._tr(source, "perm.show_global_admin", id=uid))
        for uid in self.c.mods.users:
            lines.append(self._tr(source, "perm.show_global_mod", id=uid))
        return lines

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
            await u.send_msg(source, content, ephemeral=ephemeral, file=file)


async def setup(bot: commands.Bot):
    if bot.config.perm.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(PermCog(bot))
        l.info("PermCog loaded.")
