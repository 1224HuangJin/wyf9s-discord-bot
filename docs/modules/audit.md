# 审计日志 (audit)

一个**共享服务模块**，将管理操作以嵌入（embed）形式记录到指定频道。**无指令**，被其他模块调用。

- **配置键**：`audit`
- **源文件**：`modules/audit.py`

## 工作方式

其他模块在执行敏感操作后会调用 `AuditLogger.log(...)`，日志会被发送到：

- **全局频道**：`global_channel`，所有服务器的操作都发送到这里。
- **按服务器频道**：`guilds` 中为对应服务器单独配置的频道。

两者**互不影响**：若同时配置，两个频道都会收到日志（按频道去重，全局优先）。每种语言的 embed 只构建一次并缓存。

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

| 来源模块 | 操作名 |
| --- | --- |
| tools | `delete`、`clear-message`、`move-channel`、`to-file` |
| admin | `/sync`、`/reload` |
| emoji | `emoji-update` |
| lock | `lock`、`unlock`、`plan-lock`、`unplan-lock` |
| voice | `joinvc`、`leavevc` |
| antispam | `antispam-auto-catch`（自动操作，含失败记录） |
| perm | `perm-add`、`perm-rm` |
| announce | `subscribe` |

## 多语言

支持中英双语，可分别为全局与各服务器设置：

| 语言值 | 说明 |
| --- | --- |
| `zh` | 中文（默认） |
| `en` | English |

## 配置

```yaml
audit:
  enabled: false
  global_channel: null    # 全局日志频道 ID (null 禁用)
  global_lang: zh         # 全局日志语言: zh (默认) / en
  guilds: {}              # 按服务器配置的日志频道
  # 示例 (两种写法均可):
  #   123456789:  987654321              # 仅频道 ID, 语言默认 zh
  #   123456789:                         # 或指定语言
  #     channel: 987654321
  #     lang: en
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用审计日志 |
| `global_channel` | `int \| null` | `null` | 全局日志频道 ID（`null` 禁用全局日志） |
| `global_lang` | `zh` / `en` | `zh` | 全局日志语言 |
| `guilds` | `dict` | `{}` | 按服务器配置，见下 |

### `guilds` 写法

key 为服务器 ID（数字或字符串），value 可以是：

- **频道 ID**（数字）：语言默认 `zh`；
- 或对象 `{ channel: 频道ID, lang: zh/en }`。

```yaml
audit:
  enabled: true
  global_channel: 111111111111111111
  global_lang: zh
  guilds:
    222222222222222222: 333333333333333333      # 简写: 仅频道 ID
    444444444444444444:
      channel: 555555555555555555
      lang: en
```

::: tip
若某模块启用但 `audit.enabled` 为 `false`，相关操作不会记录日志（模块仍正常工作）。
:::
