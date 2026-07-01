# 工具 / 管理 (tools)

提供常用工具与管理指令：随机数 / UUID 生成、消息删除、批量清理消息、频道移动、文本转文件、指令同步。

- **配置键**：`tools`
- **源文件**：`cogs/tools.py`（批量清理逻辑在 `modules/clear_message.py`）

## 指令

### `random` — 生成随机数

生成指定范围内的随机整数。

| 项目 | 说明 |
| --- | --- |
| 权限 | 所有人 |
| 限速 | ✅ 受限（`random`，默认 10 次 / 60s） |
| 参数 | `min_num`（默认 `1`）、`max_num`（默认 `114514`） |

- 若 `min_num > max_num` 会自动交换。
- 斜杠：`/random min_num:1 max_num:100`；前缀：`//random 1 100`

### `uuid` — 生成 UUID

生成一个随机 UUID，以**私密消息（ephemeral）**发送，并在延迟后自动删除。

| 项目 | 说明 |
| --- | --- |
| 权限 | 所有人 |
| 限速 | ✅ 受限（`uuid`，默认 10 次 / 60s） |
| 参数 | `delete_after`（删除延迟秒数，默认 `secret_message_delay` = 600） |

- 前缀命令中 `delete_after <= 0` 时使用默认值。

### `2file` — 文本转文件

将一段文本内容作为文件发送。

| 项目 | 说明 |
| --- | --- |
| 权限 | 所有人 |
| 限速 | ✅ 受限（`2file`，默认 10 次 / 60s） |
| 参数 | `name`（文件名）、`content`（文件内容） |
| 审计 | ✅ 记录（`/2file`） |

- 前缀：`//2file 文件名.txt 剩余内容作为文件正文`（`content` 为剩余全部文本）。

### `delete` — 删除消息

删除**当前频道**中指定 ID 的单条消息。

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 参数 | `message_id`（消息 ID）、`show_to_public`（是否公开显示结果，默认 `false`） |
| 机器人权限 | 管理消息（Manage Messages） |
| 审计 | ✅ 记录（`delete`） |

- 错误处理：权限不足 / 找不到消息 / ID 非整数等都会返回明确提示。

### `clear-message` — 批量清除消息

按多种过滤条件批量清除消息，支持单频道或整个服务器。

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 机器人权限 | 管理消息（Manage Messages）；读取历史消息 |
| 审计 | ✅ 记录（`clear-message`） |

#### 参数

| 参数 | 说明 |
| --- | --- |
| `user` | 目标用户（单个，选择器） |
| `user_ids` | 目标用户 ID 列表（逗号分隔） |
| `webhook_ids` | 目标 Webhook ID 列表（逗号分隔） |
| `nick_pattern` | 昵称通配符（fnmatch，如 `*bot*`） |
| `content_pattern` | 消息内容通配符（fnmatch，如 `*error*`） |
| `message_count` | 每个频道最多检查多少条消息（不填 / 0 = 不限制但较慢） |
| `within_minutes` | 仅清除最近几分钟内的消息（不填 / 0 = 不限制） |
| `scope` | 范围：`channel`（单频道，默认）或 `server`（整个服务器） |
| `channel` | 指定频道（仅 `scope=channel` 时生效，默认当前频道） |
| `start` | 起始范围：消息 ID 或时间（`30m` / `2h` / `1d` / ISO 时间） |
| `end` | 结束范围：消息 ID 或时间 |

#### 约束

- `start`/`end` 不能与 `within_minutes`/`message_count` **同时使用**。
- 若不使用时间范围，`message_count` 与 `within_minutes` 至少设置一个。
- 若无任何范围限制，则必须至少提供一种匹配过滤条件。
- **超过 14 天的消息无法批量删除**（Discord 限制），会单独计为「因超过 14 天不可删」。
- 机器人自己发出的、带 `[clear-message]` 标记的结果消息会被自动跳过，避免误删。

#### 前缀命令 flag

前缀模式用 `--key=value` 传参：

```
//clear-message --user=@某人 --within=30m
//clear-message --nick="*bot*" --scope=server --count=500
//clear-message --content="*spam*" --start=1d --end=2h
```

- 支持别名：`--user-ids` / `--webhook-ids` / `--nick`(=`--nick-pattern`) / `--content`(=`--content-pattern`) / `--count` / `--within` / `--scope` / `--channel` / `--start` / `--end`
- `--within` 支持 `30m` / `2h` / `1d` 或纯分钟数。

#### 结果消息 OK 按钮

清理结果消息附带一个 **OK 按钮**，点击可删除该结果消息（点击者需与指令相同的 Mod 权限）。

### `move-channel` — 移动频道

将当前或指定频道移动到某分类，或某频道之前 / 之后。

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 机器人权限 | 管理频道（Manage Channels），且身份组层级足够 |
| 审计 | ✅ 记录（`move-channel`） |

#### 参数

| 参数 | 说明 |
| --- | --- |
| `target_channel` | 要操作的频道（默认当前频道） |
| `category` | 目标分类 |
| `before` | 移动到此频道之前 |
| `after` | 移动到此频道之后 |
| `sync_perm` | 是否同步目标分类权限（默认 `true`） |

- 必须至少提供 `category` / `before` / `after` 之一。
- `before` 与 `after` 不能同时指定。
- 前缀命令仅支持 `target_channel` 与 `category` 两个位置参数。

::: tip `/sync` 已迁移至 [管理指令](/modules/admin)
指令同步 `/sync` 和热重载 `/reload` 现在由 `cogs/admin.py` 提供。
:::

## 限速

`random` / `uuid` / `2file` 受滑动窗口限速，Admin 不受限、Mod 额度为普通用户的 `mod_multiplier` 倍。详见[限速与 Rate Limit](/guide/rate-limit)。

## 配置

```yaml
tools:
  enabled: false
  slash: true
  prefix: true
  ratelimit:              # 仅作用于 random / uuid / 2file
    enabled: true
    window: 60            # 时间窗口 (秒)
    mod_multiplier: 3     # mod 额度倍数; admin 不受限速
    random: 10
    uuid: 10
    "2file": 10
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用工具模块 |
| `slash` | `bool` | `true` | 是否注册斜杠指令 |
| `prefix` | `bool` | `true` | 是否注册前缀指令 |
| `ratelimit.*` | — | — | 限速配置，详见[限速页](/guide/rate-limit) |
