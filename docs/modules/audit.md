# 操作 / 审计日志 (audit)

一个**共享服务模块**，将操作以嵌入（embed）形式记录到指定频道。**无指令**，被其他模块调用。

- **配置键**：`audit`
- **源文件**：`modules/audit.py`

## 两类日志

日志分为两个**互相独立**的类别，各自配置目标频道；**未配置的类别不发送**：

| 类别 | 含义 | 包含 |
| --- | --- | --- |
| **action** | 普通指令操作日志 | 用户手动执行的命令（sync/reload/delete/lock/move/emoji/subscribe/perm...） |
| **audit** | 审计日志 | 自动化处置与错误（反垃圾自动踢 / ban / 禁言、斜杠命令错误） |

## 工作方式

其他模块在执行操作后会调用 `AuditLogger.log(..., category=...)`，日志按类别发送到：

- **全局频道**：`global_action` / `global_audit`，所有服务器对应类别的操作都发送到这里。
- **按服务器频道**：`guilds` 中为对应服务器单独配置的 `action` / `audit` 频道。

全局与按服务器**互不影响**：若同时配置，两个频道都会收到对应类别的日志（按频道去重，全局优先）。每种语言的 embed 只构建一次并缓存。

机器人需要对日志频道拥有**发送消息 / 嵌入链接**权限；目标必须是文字频道或帖子（Thread），否则会被跳过并告警。

## 日志内容

每条日志是一个 embed，包含（按配置语言显示）：

- **标题**：区分手动 / 自动操作、成功 / 失败（✅ / ❌ / 🚨 / ⚠️）。
- **操作（Action）**：如 `/delete`、`clear-message`、`antispam-auto-catch`。
- **执行者（Actor）**：提及 + 用户名 + ID。
- **服务器（Server）**、**频道（Channel）**（若有）。
- **详情（Detail）**：操作说明（上限 1024 字符）。
- **时间戳**（UTC）。

## 哪些操作会被记录？

| 来源模块 | 操作名 | 类别 |
| --- | --- | --- |
| tools | `delete`、`clear-message`、`move-channel`、`to-file` | action |
| admin | `sync`、`reload`、`reload-all`、`reload-config` | action |
| emoji | `emoji-update` | action |
| lock | `lock`、`unlock`、`plan-lock`、`unplan-lock` | action |
| voice | `joinvc`、`leavevc` | action |
| perm | `perm-add`、`perm-rm` | action |
| announce | `subscribe` | action |
| antispam | `antispam-auto-catch`（自动操作，含失败记录） | **audit** |
| （全局错误处理） | `slash-error/<cmd>` | **audit** |

## 多语言

支持中英双语。语言通过 `/lang` 命令设置（优先级：用户设置 > 服务器设置 > 默认 `zh`），详见 [lang 模块文档](lang.md)。

| 语言值 | 说明 |
| --- | --- |
| `zh` | 中文（默认） |
| `en` | English |

## 配置

```yaml
audit:
  enabled: false
  global_action: null     # 全局「操作日志」频道 ID (null 禁用)
  global_audit: null      # 全局「审计日志」频道 ID (null 禁用)
  guilds: {}              # 按服务器配置的日志频道
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用日志 |
| `global_action` | `int \| null` | `null` | 全局「操作日志」频道 ID（`null` 禁用） |
| `global_audit` | `int \| null` | `null` | 全局「审计日志」频道 ID（`null` 禁用） |
| `global_channel` | `int \| null` | `null` | **[兼容旧配置]** `global_audit` 的别名 |
| `guilds` | `dict` | `{}` | 按服务器配置，见下 |

### `guilds` 写法

key 为服务器 ID（数字或字符串），value 可为：

- 对象 `{ action: 频道ID, audit: 频道ID }`：分别配置两类频道（任一可省略）。
- 频道 ID（数字）：**[兼容旧配置]** 作为该服务器的 `audit` 频道。

```yaml
audit:
  enabled: true
  global_action: 111111111111111111
  global_audit: 222222222222222222
  guilds:
    333333333333333333:            # 分别配置两类
      action: 444444444444444444
      audit: 555555555555555555
    666666666666666666: 777777777777777777   # 兼容旧配置: 仅频道 ID -> audit
```

::: tip
- 某一类别（action / audit）**全局与服务器均未配置**时，该类别的日志不会发送。
- 若某模块启用但 `audit.enabled` 为 `false`，相关操作不会记录日志（模块仍正常工作）。
:::
