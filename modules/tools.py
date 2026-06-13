# c!ding: utf-8
from uuid import uuid4 as uuid
from datetime import datetime
import io
import random
import re

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel
from modules.audit import AuditLogger
from modules.clear_message import CLEAR_MESSAGE_MARKER, ClearMessageService
import utils as u


def _parse_flags(content: str) -> dict[str, str]:
    """
    从消息内容中解析 --key=value 格式的标志 (deprecated, use u.parse_flags)
    """
    return u.parse_flags(content)


class ClearMessageResultView(discord.ui.View):
    """clear-message 结果消息的视图, 提供一个 OK 按钮用于删除该结果消息 (权限与指令相同)"""

    def __init__(self, tools: "ToolsModule", guild: discord.Guild | None):
        super().__init__(timeout=None)
        self.tools = tools
        self.guild = guild

    @discord.ui.button(label="OK", style=discord.ButtonStyle.secondary)
    async def btn_ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.tools._can_use_clear_message(interaction.user, self.guild):
            await interaction.response.send_message(
                ":x: **你没有权限使用此指令** :x:", ephemeral=True
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

        # fallback (ephemeral 消息): 删除原始交互响应
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass


class ConfirmClearView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed: bool | None = None

    @discord.ui.button(label="确认删除", style=discord.ButtonStyle.danger)
    async def btn_confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":broom: **正在执行...**", view=None
        )

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def btn_cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":x: **操作已取消**", view=None
        )

    async def on_timeout(self):
        self.confirmed = False


class ToolsModule:
    c: ConfigModel
    client: commands.Bot
    audit: AuditLogger | None

    def __init__(
        self, config: ConfigModel, client: commands.Bot, audit: AuditLogger | None
    ):
        self.c = config
        self.client = client
        self.audit = audit
        self.clear_message = ClearMessageService(
            config=config, client=client, audit=audit
        )

        # ========== Slash Commands ==========

        if self.c.tools.slash:
            self._register_slash_commands(client)

        # ========== Prefix Commands ==========

        if self.c.tools.prefix:
            self._register_prefix_commands(client)

    def _register_slash_commands(self, client: commands.Bot):
        # ----- Random - 随机数 -----

        @client.tree.command(name="random", description="生成自定义范围的随机数")
        @app_commands.describe(
            min_num="最小值 (默认: 1)", max_num="最大值 (默认: 114514)"
        )
        async def slash_random_number(
            interaction: discord.Interaction, min_num: int = 1, max_num: int = 114514
        ):
            await self._handle_random(interaction, min_num, max_num)

        # ----- UUID -----

        @client.tree.command(name="uuid", description="生成一个 UUID")
        @app_commands.describe(delete_after="在多久后删除 (s)")
        async def slash_random_uuid(
            interaction: discord.Interaction,
            delete_after: int = self.c.secret_message_delay,
        ):
            await self._handle_uuid(interaction, delete_after)

        # ----- Delete Message - 删除消息 -----

        @client.tree.command(name="delete", description="删除消息")
        @app_commands.describe(
            message_id="要删除的消息 ID", show_to_public="是否公开显示删除结果"
        )
        async def delete_message(
            interaction: discord.Interaction,
            message_id: str,
            show_to_public: bool = False,
        ):
            await self._handle_delete(interaction, message_id, show_to_public)

        # ----- Clear Message - 批量清除消息 -----

        @client.tree.command(name="clear-message", description="按条件批量清除消息")
        @app_commands.describe(
            user="目标用户 (单个, 选择器)",
            user_ids="目标用户 ID 列表 (逗号分隔, 可填多个)",
            webhook_ids="目标 Webhook ID 列表 (逗号分隔, 可填多个)",
            nick_pattern='目标昵称通配符 (fnmatch, 例如 "*bot*")',
            content_pattern='消息内容通配符 (fnmatch, 例如 "*error*")',
            message_count="每个频道最多检查多少条消息 (不填/0 = 不限制但较慢)",
            within_minutes="仅清除最近几分钟内的消息 (不填/0 = 不限制)",
            scope='清除消息的范围: "channel" (单个频道, 默认) 或 "server" (整个服务器)',
            channel="指定频道 (仅在 scope=channel 时生效, 未设置则使用指令所在频道)",
            start='起始范围: 消息ID 或 相对/绝对时间 (例如 "1234567890" / "30m" / "2h" / "1d" / ISO时间)',
            end='结束范围: 消息ID 或 相对/绝对时间 (例如 "1234567890" / "30m" / "2h" / "1d" / ISO时间)',
        )
        async def clear_message(
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
            await self._handle_clear_message(
                interaction,
                user=user,
                user_ids=user_ids,
                webhook_ids=webhook_ids,
                nick_pattern=nick_pattern,
                content_pattern=content_pattern,
                message_count=message_count,
                within_minutes=within_minutes,
                scope=scope,
                channel=channel,
                start=start,
                end=end,
            )

        # ========== Others ==========

        @client.tree.command(
            name="move-channel", description="移动当前或指定频道到指定分类或频道的前/后"
        )
        @app_commands.describe(
            target_channel="要操作的频道 (可选，默认为当前频道)",
            category="目标分类 (可选)",
            before="在这个频道之前 (可选)",
            after="在这个频道之后 (可选)",
            sync_perm="是否同步目标分类的权限 (可选，默认为 True)",
        )
        async def move_channel(
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

        @client.tree.command(name="sync", description="同步指令列表")
        async def sync(interaction: discord.Interaction):
            if not self._is_config_admin(interaction.user):
                await self._deny(interaction, ":x: **你没有权限使用此指令** :x:")
                return

            await interaction.response.defer()
            await client.tree.sync()
            l.info("Command tree synced.")
            await interaction.followup.send("**:white_check_mark: 斜杠指令列表已同步**")
            if self.audit:
                await self.audit.log(
                    action="/sync",
                    user=interaction.user,
                    guild=interaction.guild,
                    channel=interaction.channel,
                    detail="同步斜杠指令列表",
                )

        # ----- 2File - 文本转文件 -----

        @client.tree.command(name="2file", description="将文本内容以文件形式发送")
        @app_commands.describe(name="文件名", content="文件内容")
        async def twofile(interaction: discord.Interaction, name: str, content: str):
            await self._handle_2file(interaction, name, content)

    def _register_prefix_commands(self, client: commands.Bot):
        # ----- Random - 随机数 -----

        @client.command(name="random")
        async def prefix_random(
            ctx: commands.Context, min_num: int = 1, max_num: int = 114514
        ):
            await self._handle_random(ctx, min_num, max_num)

        # ----- UUID -----

        @client.command(name="uuid")
        async def prefix_uuid(ctx: commands.Context, delete_after: int = 0):
            if delete_after <= 0:
                delete_after = self.c.secret_message_delay
            await self._handle_uuid(ctx, delete_after)

        # ----- Delete Message - 删除消息 -----

        @client.command(name="delete")
        async def prefix_delete(
            ctx: commands.Context, message_id: str, show_to_public: bool = False
        ):
            await self._handle_delete(ctx, message_id, show_to_public)

        # ----- Clear Message - 批量清除消息 -----

        @client.command(name="clear-message")
        async def prefix_clear_message(ctx: commands.Context):
            flags = _parse_flags(ctx.message.content)

            # 解析 user (mention 或 ID)
            user = None
            if "user" in flags:
                user_str = flags["user"]
                # 尝试从 mention 解析 <@123> 或 <@!123>
                mention_match = re.match(r"<@!?(\d+)>", user_str)
                if mention_match:
                    user_id = int(mention_match.group(1))
                    try:
                        user = await client.fetch_user(user_id)
                    except discord.NotFound:
                        pass
                elif user_str.isdigit():
                    try:
                        user = await client.fetch_user(int(user_str))
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
                        self._mark_clear_message(":x: **count 参数必须为整数**"),
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
                            ":x: **within 格式无效 (例如: 30m, 2h, 1d)**"
                        ),
                        delete_after=10,
                    )
                    return

            scope = flags.get("scope", "channel")

            channel = None
            if "channel" in flags:
                channel_str = flags["channel"]
                mention_match = re.match(r"<#(\d+)>", channel_str)
                if mention_match:
                    channel = client.get_channel(int(mention_match.group(1)))
                elif channel_str.isdigit():
                    channel = client.get_channel(int(channel_str))

            start = flags.get("start") or None
            end = flags.get("end") or None

            # 构造一个伪 interaction 对象来复用逻辑
            await self._handle_clear_message_prefix(
                ctx,
                user=user,
                user_ids=user_ids,
                webhook_ids=webhook_ids,
                nick_pattern=nick_pattern,
                content_pattern=content_pattern,
                message_count=message_count,
                within_minutes=within_minutes,
                scope=scope,
                channel=channel,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
                start=start,
                end=end,
            )

        # ----- Move Channel -----

        @client.command(name="move-channel")
        async def prefix_move_channel(
            ctx: commands.Context,
            target_channel: discord.abc.GuildChannel | None = None,
            category: discord.CategoryChannel | None = None,
        ):
            await self._handle_move_channel(
                ctx, target_channel, category, None, None, True
            )

        # ----- Sync -----

        @client.command(name="sync")
        async def prefix_sync(ctx: commands.Context):
            if not self._is_config_admin(ctx.author):
                await ctx.send("**:x: 你没有权限使用此指令**", delete_after=10)
                return

            await ctx.defer()
            await client.tree.sync()
            await ctx.send("**:white_check_mark: 斜杠指令列表已同步**")
            if self.audit:
                await self.audit.log(
                    action="sync (prefix)",
                    user=ctx.author,
                    guild=ctx.guild,
                    channel=ctx.channel,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
                    detail="同步斜杠指令列表",
                )

        # ----- Sync Commands (legacy) -----

        @client.command(name="sync-commands")
        async def sync_commands(ctx: commands.Context):
            if not self._is_config_admin(ctx.author):
                await ctx.send("**:x: 你没有权限使用此指令**", delete_after=10)
                return

            await ctx.defer()
            await client.tree.sync()
            await ctx.send("**:white_check_mark: 斜杠指令列表已同步**")
            if self.audit:
                await self.audit.log(
                    action="sync-commands (prefix)",
                    user=ctx.author,
                    guild=ctx.guild,
                    channel=ctx.channel,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
                    detail="同步斜杠指令列表",
                )

        # ----- 2File - 文本转文件 -----

        @client.command(name="2file")
        async def prefix_2file(ctx: commands.Context, name: str, *, content: str):
            await self._handle_2file(ctx, name, content)

    # ========== Shared Logic ==========

    async def _handle_random(self, source, min_num: int = 1, max_num: int = 114514):
        try:
            if min_num > max_num:
                min_num, max_num = max_num, min_num

            result = random.randint(min_num, max_num)
            await u.send_msg(
                source, f":game_die: `{min_num}` - `{max_num}` 的随机数：**`{result}`**"
            )
        except ValueError:
            await u.send_msg(
                source, ":x: 请输入有效的整数范围！", ephemeral=True, delete_after=10
            )

    async def _handle_uuid(self, source, delete_after: int):
        now = int(datetime.now().timestamp())
        await u.send_msg(
            source,
            f":lock: 随机生成 UUID: **```{uuid()}```**> 此条消息仅你可见, 且将在 <t:{now + delete_after}:R> 删除",
            ephemeral=True,
            delete_after=delete_after,
        )

    async def _handle_2file(self, source, name: str, content: str):
        bio = io.BytesIO(content.encode("utf-8"))
        await u.send_msg(
            source,
            "",
            file=discord.File(fp=bio, filename=name),
        )

        user = source.user if isinstance(source, discord.Interaction) else source.author
        if self.audit:
            await self.audit.log(
                action="/2file",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"发送文件: `{name}`",
            )

    async def _handle_delete(
        self, source, message_id: str, show_to_public: bool = False
    ):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._can_use_delete(user):
            await u.send_msg(
                source,
                ":x: **你没有权限使用此指令** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        if not message_id:
            await u.send_msg(
                source,
                ":x: **未指定要删除的消息 (通过回复消息或指定消息 ID)** :x:",
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
                ":x: **权限不足, 无法删除此消息** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except discord.NotFound:
            await u.send_msg(
                source,
                f":x: **找不到 ID 为 `{message_id}` 的消息** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except ValueError:
            await u.send_msg(
                source,
                f":x: **消息 ID 不为整数: `{message_id}`** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source,
                f":x: **删除消息 `{message_id}` 时出错: `{e}`** :x:",
                ephemeral=True,
                delete_after=10,
            )
        else:
            await u.send_msg(
                source,
                f":white_check_mark: **删除消息 `{message_id}` 成功!** :white_check_mark:",
                ephemeral=not show_to_public,
            )
            if self.audit:
                await self.audit.log(
                    action="delete",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"删除消息 ID `{message_id}`",
                )

    async def _handle_clear_message(
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
        channel: discord.abc.GuildChannel | None = None,
        start: str | None = None,
        end: str | None = None,
    ):
        if not self._can_use_clear_message(interaction.user, interaction.guild):
            await self._deny(interaction, ":x: **你没有权限使用此指令** :x:")
            return

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
        await u.send_msg(interaction, result, ephemeral=True, view=view)

    async def _handle_clear_message_prefix(
        self,
        ctx: commands.Context,
        user: discord.User | None = None,
        user_ids: str | None = None,
        webhook_ids: str | None = None,
        nick_pattern: str | None = None,
        content_pattern: str | None = None,
        message_count: int | None = None,
        within_minutes: int | None = None,
        scope: str = "channel",
        channel: discord.abc.GuildChannel | None = None,
        start: str | None = None,
        end: str | None = None,
    ):
        if not self._can_use_clear_message(ctx.author, ctx.guild):
            await ctx.send(
                self._mark_clear_message(":x: **你没有权限使用此指令** :x:"),
                delete_after=10,
            )
            return

        await ctx.defer()

        result = await self._do_clear_message(
            ctx.author,
            ctx.guild,
            ctx.channel,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
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

        # 成功结果已带标记 (附带 OK 按钮), 错误结果仅补标记以防被自己清除
        is_success = CLEAR_MESSAGE_MARKER in result
        view = ClearMessageResultView(self, ctx.guild) if is_success else None
        await u.send_msg(ctx, self._mark_clear_message(result), view=view)

    async def _do_clear_message(
        self,
        author: discord.User | discord.Member,
        guild: discord.Guild | None,
        channel: discord.abc.GuildChannel
        | discord.abc.PrivateChannel
        | discord.Thread
        | None,
        user: discord.User | None = None,
        user_ids: str | None = None,
        webhook_ids: str | None = None,
        nick_pattern: str | None = None,
        content_pattern: str | None = None,
        message_count: int | None = None,
        within_minutes: int | None = None,
        scope: str = "channel",
        channel_target: discord.abc.GuildChannel | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        return await self.clear_message.do_clear_message(
            author=author,
            guild=guild,
            channel=channel,
            user=user,
            user_ids=user_ids,
            webhook_ids=webhook_ids,
            nick_pattern=nick_pattern,
            content_pattern=content_pattern,
            message_count=message_count,
            within_minutes=within_minutes,
            scope=scope,
            channel_target=channel_target,
            start=start,
            end=end,
        )

    async def _handle_move_channel(
        self,
        source,
        target_channel: discord.abc.GuildChannel | None = None,
        category: discord.CategoryChannel | None = None,
        before: discord.abc.GuildChannel | None = None,
        after: discord.abc.GuildChannel | None = None,
        sync_perm: bool = True,
    ):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not category and not before and not after:
            await u.send_msg(
                source,
                ":x: **参数错误：请至少提供 `category`、`before` 或 `after` 中的一个参数**",
                ephemeral=True,
                delete_after=10,
            )
            return

        if before and after:
            await u.send_msg(
                source,
                ":x: **参数错误：不能同时指定 `before` 和 `after`**",
                ephemeral=True,
                delete_after=10,
            )
            return

        channel = target_channel or source.channel
        if not isinstance(channel, discord.abc.GuildChannel):
            await u.send_msg(
                source,
                ":x: **此指令只能对服务器频道使用**",
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
            await channel.edit(**kwargs)  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]

            msg_parts = []
            if category:
                msg_parts.append(f"分类 `{category.name}`")
            if before:
                msg_parts.append(f"`{before.name}` 之前")
            elif after:
                msg_parts.append(f"`{after.name}` 之后")

            await u.send_msg(
                source,
                f":white_check_mark: **已成功将 {channel.mention} 移动到 {' / '.join(msg_parts)}**",
            )

            if self.audit:
                await self.audit.log(
                    action="move-channel",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"将频道 `{channel.name}` 移动到 {' / '.join(msg_parts)}",
                )
        except discord.Forbidden:
            await u.send_msg(
                source,
                ":x: **权限不足：我需要 `管理频道 (Manage Channels)` 权限才能执行此操作，或者我的角色层级不够**",
                ephemeral=True,
                delete_after=10,
            )
        except discord.HTTPException as e:
            await u.send_msg(
                source,
                f":x: **移动失败：API 请求错误 ({e.status} - {e.text})**",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source,
                f":x: **移动失败：发生未知错误：`{e}`**",
                ephemeral=True,
                delete_after=10,
            )

    # ========== Permission Helpers ==========

    def _matches_identity(
        self, user: discord.User | discord.Member, values: list[int | str]
    ) -> bool:
        for value in values:
            if user.id == value or user.name == value:
                return True
            if isinstance(value, str) and value.isdigit() and user.id == int(value):
                return True
        return False

    def _is_server_admin(self, user: discord.User | discord.Member) -> bool:
        return isinstance(user, discord.Member) and user.guild_permissions.administrator

    def _is_config_admin(self, user: discord.User | discord.Member) -> bool:
        return self._matches_identity(user, self.c.admins.users)

    def _is_mod(
        self, user: discord.User | discord.Member, guild: discord.Guild | None = None
    ) -> bool:
        if self._is_server_admin(user) or self._is_config_admin(user):
            return True

        if isinstance(user, discord.Member):
            if self._matches_identity(user, self.c.mods.users):
                return True

            if guild is not None:
                guild_users = self.c.mods.guilds.get(
                    guild.id, self.c.mods.guilds.get(str(guild.id), [])
                )
                return self._matches_identity(user, guild_users)

        return False

    def _can_use_clear_message(
        self, user: discord.User | discord.Member, guild: discord.Guild | None = None
    ) -> bool:
        return self._is_mod(user, guild)

    @staticmethod
    def _mark_clear_message(text: str) -> str:
        """为 clear-message 的非 ephemeral 消息追加标记, 避免被自己批量清除"""
        if CLEAR_MESSAGE_MARKER in text:
            return text
        return f"{text}\n-# {CLEAR_MESSAGE_MARKER}"

    def _can_use_delete(self, user: discord.User | discord.Member) -> bool:
        return self._is_mod(user)

    async def _deny(self, interaction: discord.Interaction, message: str):
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
