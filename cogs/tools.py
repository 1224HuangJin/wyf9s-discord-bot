from uuid import uuid4 as uuid
from datetime import datetime
import io
import random
import re

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
from modules.clear_message import CLEAR_MESSAGE_MARKER, ClearMessageService
import utils as u


def _parse_flags(content: str) -> dict[str, str]:
    return u.parse_flags(content)


class ClearMessageResultView(discord.ui.View):
    def __init__(self, tools: "ToolsCog", guild: discord.Guild | None):
        super().__init__(timeout=None)
        self.tools = tools
        self.guild = guild

    @discord.ui.button(label="OK", style=discord.ButtonStyle.secondary)
    async def btn_ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not u.is_mod(interaction.user, self.tools.c, self.guild):
            await interaction.response.send_message(
                ":x: **No permission** :x:", ephemeral=True
            )
            return
        self.stop()
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass
        msg = interaction.message
        if msg is not None:
            try:
                await msg.delete()
                return
            except discord.HTTPException:
                pass
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass


class ConfirmClearView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed: bool | None = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def btn_confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":broom: **Running...**", view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def btn_cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(content=":x: **Cancelled**", view=None)

    async def on_timeout(self):
        self.confirmed = False


class ToolsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)
        self.rate_limiter = getattr(bot, "rate_limiter", u.RateLimiter())
        self.clear_message = ClearMessageService(
            config=self.c, client=bot, audit=self.audit
        )

    # ========== Slash Commands ==========

    @app_commands.command(name="random", description="Generate a random number")
    @app_commands.describe(min_num="Min (default: 1)", max_num="Max (default: 114514)")
    async def slash_random(
        self, interaction: discord.Interaction, min_num: int = 1, max_num: int = 114514
    ):
        await self._handle_random(interaction, min_num, max_num)

    @app_commands.command(name="uuid", description="Generate a UUID")
    @app_commands.describe(delete_after="Seconds before deletion")
    async def slash_uuid(self, interaction: discord.Interaction, delete_after: int = 0):
        if delete_after <= 0:
            delete_after = self.c.secret_message_delay
        await self._handle_uuid(interaction, delete_after)

    @app_commands.command(name="delete", description="[MOD] Delete a message by ID")
    @app_commands.describe(
        message_id="Message ID", show_to_public="Show result publicly"
    )
    @u.requires(u.Permission.MOD, perm_module="tools")
    async def slash_delete(
        self,
        interaction: discord.Interaction,
        message_id: str,
        show_to_public: bool = False,
    ):
        await self._handle_delete(interaction, message_id, show_to_public)

    @app_commands.command(name="clear-message", description="[MOD] Bulk clear messages")
    @app_commands.describe(
        user="Target user",
        user_ids="Target user IDs (comma-separated)",
        webhook_ids="Target webhook IDs (comma-separated)",
        nick_pattern='Nickname pattern (fnmatch, e.g. "*bot*")',
        content_pattern='Content pattern (fnmatch, e.g. "*error*")',
        message_count="Max messages per channel (0 = unlimited)",
        within_minutes="Only messages within N minutes",
        scope='"channel" (default) or "server"',
        channel="Target channel (scope=channel only)",
        start='Start: message ID or time (e.g. "30m"/"2h"/"1d"/ISO)',
        end="End: message ID or time",
    )
    @u.requires(u.Permission.MOD, perm_module="tools")
    async def slash_clear_message(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
        user_ids: str | None = None,
        webhook_ids: str | None = None,
        nick_pattern: str | None = None,
        content_pattern: str | None = None,
        message_count: int | None = None,
        within_minutes: int | None = None,
        scope: str = "channel",
        channel: discord.TextChannel
        | discord.VoiceChannel
        | discord.StageChannel
        | None = None,
        start: str | None = None,
        end: str | None = None,
    ):
        await interaction.response.defer()
        result = await self._do_clear_message(
            interaction.user,
            interaction.guild,
            interaction.channel,
            user=user,
            user_ids=user_ids,
            webhook_ids=webhook_ids,
            nick_pattern=nick_pattern,
            content_pattern=content_pattern,
            message_count=message_count,
            within_minutes=within_minutes,
            scope=scope,
            channel_target=channel,
            start=start,
            end=end,
        )
        view = (
            ClearMessageResultView(self, interaction.guild)
            if CLEAR_MESSAGE_MARKER in result
            else None
        )
        await interaction.followup.send(result, ephemeral=True, view=view)  # ty:ignore[invalid-argument-type]

    @app_commands.command(name="move-channel", description="[MOD] Move a channel")
    @app_commands.describe(
        target_channel="Channel to move (default: current)",
        category="Target category",
        before="Place before this channel",
        after="Place after this channel",
        sync_perm="Sync category permissions (default: True)",
    )
    @u.requires(u.Permission.MOD, perm_module="tools")
    async def slash_move_channel(
        self,
        interaction: discord.Interaction,
        target_channel: discord.abc.GuildChannel | None = None,
        category: discord.CategoryChannel | None = None,
        before: discord.abc.GuildChannel | None = None,
        after: discord.abc.GuildChannel | None = None,
        sync_perm: bool = True,
    ):
        await self._handle_move_channel(
            interaction, target_channel, category, before, after, sync_perm
        )

    @app_commands.command(name="to-file", description="Send text as a file")
    @app_commands.describe(name="Filename", content="File content")
    async def slash_to_file(
        self, interaction: discord.Interaction, name: str, content: str
    ):
        await self._handle_to_file(interaction, name, content)

    # ========== Prefix Commands ==========

    @commands.command(name="random")
    async def prefix_random(
        self, ctx: commands.Context, min_num: int = 1, max_num: int = 114514
    ):
        await self._handle_random(ctx, min_num, max_num)

    @commands.command(name="uuid")
    async def prefix_uuid(self, ctx: commands.Context, delete_after: int = 0):
        if delete_after <= 0:
            delete_after = self.c.secret_message_delay
        await self._handle_uuid(ctx, delete_after)

    @commands.command(name="delete")
    @u.requires(u.Permission.MOD, perm_module="tools")
    async def prefix_delete(
        self, ctx: commands.Context, message_id: str, show_to_public: bool = False
    ):
        await self._handle_delete(ctx, message_id, show_to_public)

    @commands.command(name="clear-message")
    @u.requires(
        u.Permission.MOD,
        deny=f":x: **No permission** :x:\n-# {CLEAR_MESSAGE_MARKER}",
        perm_module="tools",
    )
    async def prefix_clear_message(self, ctx: commands.Context):
        flags = _parse_flags(ctx.message.content)

        user = None
        if "user" in flags:
            user_str = flags["user"]
            m = re.match(r"<@!?(\d+)>", user_str)
            if m:
                try:
                    user = await self.bot.fetch_user(int(m.group(1)))
                except discord.NotFound:
                    pass
            elif user_str.isdigit():
                try:
                    user = await self.bot.fetch_user(int(user_str))
                except discord.NotFound:
                    pass

        user_ids = flags.get("user-ids") or flags.get("user_ids") or None
        webhook_ids = flags.get("webhook-ids") or flags.get("webhook_ids") or None
        nick_pattern = (
            flags.get("nick")
            or flags.get("nick-pattern")
            or flags.get("nick_pattern")
            or None
        )
        content_pattern = (
            flags.get("content")
            or flags.get("content-pattern")
            or flags.get("content_pattern")
            or None
        )

        message_count = None
        if "count" in flags:
            try:
                message_count = int(flags["count"])
            except ValueError:
                await ctx.send(
                    self._mark_clear_message(":x: **count must be an integer**"),
                    delete_after=10,
                )
                return

        within_minutes = None
        if "within" in flags:
            val = flags["within"]
            m = re.fullmatch(r"(\d+)([dhm])", val)
            if m:
                n = int(m.group(1))
                unit = m.group(2)
                if unit == "d":
                    within_minutes = n * 1440
                elif unit == "h":
                    within_minutes = n * 60
                elif unit == "m":
                    within_minutes = n
            elif val.isdigit():
                within_minutes = int(val)
            else:
                await ctx.send(
                    self._mark_clear_message(
                        ":x: **Invalid within format (e.g. 30m, 2h, 1d)**"
                    ),
                    delete_after=10,
                )
                return

        scope = flags.get("scope", "channel")

        channel = None
        if "channel" in flags:
            ch_str = flags["channel"]
            m = re.match(r"<#(\d+)>", ch_str)
            if m:
                channel = self.bot.get_channel(int(m.group(1)))
            elif ch_str.isdigit():
                channel = self.bot.get_channel(int(ch_str))

        start = flags.get("start") or None
        end = flags.get("end") or None

        await ctx.defer()
        result = await self._do_clear_message(
            ctx.author,
            ctx.guild,
            ctx.channel,
            user=user,
            user_ids=user_ids,
            webhook_ids=webhook_ids,
            nick_pattern=nick_pattern,
            content_pattern=content_pattern,
            message_count=message_count,
            within_minutes=within_minutes,
            scope=scope,
            channel_target=channel,
            start=start,
            end=end,
        )
        is_success = CLEAR_MESSAGE_MARKER in result
        view = ClearMessageResultView(self, ctx.guild) if is_success else None
        await ctx.send(self._mark_clear_message(result), view=view)  # ty:ignore[no-matching-overload]

    @commands.command(name="move-channel")
    @u.requires(u.Permission.MOD, perm_module="tools")
    async def prefix_move_channel(
        self,
        ctx: commands.Context,
        target_channel: discord.abc.GuildChannel | None = None,
        category: discord.CategoryChannel | None = None,
    ):
        await self._handle_move_channel(ctx, target_channel, category, None, None, True)

    @commands.command(name="to-file")
    async def prefix_to_file(self, ctx: commands.Context, name: str, *, content: str):
        await self._handle_to_file(ctx, name, content)

    # ========== Shared Logic ==========

    async def _handle_random(self, source, min_num: int = 1, max_num: int = 114514):
        if not await self._check_rate_limit(source, "random"):
            return
        try:
            if min_num > max_num:
                min_num, max_num = max_num, min_num
            result = random.randint(min_num, max_num)
            await u.send_msg(
                source,
                f":game_die: `{min_num}` - `{max_num}` random: **`{result}`**",
            )
        except ValueError:
            await u.send_msg(
                source,
                ":x: Please enter valid integers!",
                ephemeral=True,
                delete_after=10,
            )

    async def _handle_uuid(self, source, delete_after: int):
        if not await self._check_rate_limit(source, "uuid"):
            return
        now = int(datetime.now().timestamp())
        await u.send_msg(
            source,
            f":lock: Random UUID: **```{uuid()}```**> "
            f"Private message, deletes <t:{now + delete_after}:R>",
            ephemeral=True,
            delete_after=delete_after,
        )

    async def _handle_to_file(self, source, name: str, content: str):
        if not await self._check_rate_limit(source, "to-file"):
            return
        bio = io.BytesIO(content.encode("utf-8"))
        await u.send_msg(source, "", file=discord.File(fp=bio, filename=name))
        user = source.user if isinstance(source, discord.Interaction) else source.author
        if self.audit:
            await self.audit.log(
                action="to-file",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"Sent file: `{name}`",
            )

    async def _handle_delete(
        self, source, message_id: str, show_to_public: bool = False
    ):
        user = source.user if isinstance(source, discord.Interaction) else source.author
        if not message_id:
            await u.send_msg(
                source,
                ":x: **No message ID specified** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return
        try:
            message_id_int = int(message_id)
            channel = source.channel
            message = channel.get_partial_message(message_id_int)
            await message.delete()
        except discord.Forbidden:
            await u.send_msg(
                source,
                ":x: **Permission denied** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except discord.NotFound:
            await u.send_msg(
                source,
                f":x: **Message `{message_id}` not found** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except ValueError:
            await u.send_msg(
                source,
                f":x: **Invalid message ID: `{message_id}`** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source,
                f":x: **Error deleting `{message_id}`: `{e}`** :x:",
                ephemeral=True,
                delete_after=10,
            )
        else:
            await u.send_msg(
                source,
                f":white_check_mark: **Deleted message `{message_id}`** :white_check_mark:",
                ephemeral=not show_to_public,
            )
            if self.audit:
                await self.audit.log(
                    action="delete",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"Deleted message `{message_id}`",
                )

    async def _do_clear_message(
        self,
        author,
        guild,
        channel,
        **kwargs,
    ) -> str:
        return await self.clear_message.do_clear_message(
            author=author, guild=guild, channel=channel, **kwargs
        )

    async def _handle_move_channel(
        self,
        source,
        target_channel=None,
        category=None,
        before=None,
        after=None,
        sync_perm=True,
    ):
        user = source.user if isinstance(source, discord.Interaction) else source.author
        if not category and not before and not after:
            await u.send_msg(
                source,
                ":x: **Need at least one of: category, before, after**",
                ephemeral=True,
                delete_after=10,
            )
            return
        if before and after:
            await u.send_msg(
                source,
                ":x: **Cannot set both before and after**",
                ephemeral=True,
                delete_after=10,
            )
            return
        channel = target_channel or source.channel
        if not isinstance(channel, discord.abc.GuildChannel):
            await u.send_msg(
                source,
                ":x: **Only server channels supported**",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Safety: non-admin mods must have manage_channels on the target channel
        if not u.is_admin(user, self.c) and not u.is_server_admin(user):
            if isinstance(user, discord.Member):
                perms = channel.permissions_for(user)
                if not perms.manage_channels:
                    await u.send_msg(
                        source,
                        ":x: **You do not have Manage Channels permission on this channel**",
                        ephemeral=True,
                        delete_after=10,
                    )
                    return

        kwargs = {}
        update_category = False
        target_category = None
        if category:
            target_category = category
            update_category = True
        if before:
            if not update_category:
                target_category = getattr(before, "category", None)
                update_category = True
            kwargs["position"] = before.position
        elif after:
            if not update_category:
                target_category = getattr(after, "category", None)
                update_category = True
            kwargs["position"] = after.position + 1
        if update_category:
            kwargs["category"] = target_category
            if sync_perm:
                kwargs["sync_permissions"] = True
        try:
            await channel.edit(**kwargs)  # type: ignore[attr-defined]
            msg_parts = []
            if category:
                msg_parts.append(f"category `{category.name}`")
            if before:
                msg_parts.append(f"before `{before.name}`")
            elif after:
                msg_parts.append(f"after `{after.name}`")
            await u.send_msg(
                source,
                f":white_check_mark: **Moved {channel.mention} to {' / '.join(msg_parts)}**",
            )
            if self.audit:
                await self.audit.log(
                    action="move-channel",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"Moved channel `{channel.name}` to {' / '.join(msg_parts)}",
                )
        except discord.Forbidden:
            await u.send_msg(
                source,
                ":x: **Permission denied: need Manage Channels**",
                ephemeral=True,
                delete_after=10,
            )
        except discord.HTTPException as e:
            await u.send_msg(
                source,
                f":x: **API error ({e.status} - {e.text})**",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source,
                f":x: **Unexpected error: `{e}`**",
                ephemeral=True,
                delete_after=10,
            )

    async def _check_rate_limit(self, source, command: str) -> bool:
        rl = self.c.tools.ratelimit
        if not rl.enabled:
            return True
        user = source.user if isinstance(source, discord.Interaction) else source.author
        if u.is_admin(user, self.c):
            return True
        base = rl.limit_for(command)
        if base is None:
            return True
        guild = getattr(source, "guild", None)
        limit = base * rl.mod_multiplier if u.is_mod(user, self.c, guild) else base
        allowed, retry_after = self.rate_limiter.hit(
            (command, user.id), limit, rl.window
        )
        if not allowed:
            await u.send_msg(
                source,
                f":hourglass_flowing_sand: **Rate limited, retry in `{retry_after:.0f}s`**",
                ephemeral=True,
                delete_after=10,
            )
            return False
        return True

    @staticmethod
    def _mark_clear_message(text: str) -> str:
        if CLEAR_MESSAGE_MARKER in text:
            return text
        return f"{text}\n-# {CLEAR_MESSAGE_MARKER}"


async def setup(bot: commands.Bot):
    if bot.config.tools.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(ToolsCog(bot))
        l.info("ToolsCog loaded.")
