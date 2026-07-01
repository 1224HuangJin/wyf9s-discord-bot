# 反垃圾 (antispam)

基于 `on_message` 事件的频道级反垃圾模块，**无指令**。为指定频道配置捕获规则，自动对触发者执行踢出 / 封禁 / 超时，并可清理其近期消息、公开通知、写入审计日志。

- **配置键**：`antispam`
- **源文件**：`modules/antispam.py`（复用 `clear_message.py` 的清理能力）

## 判定流程

对配置了规则的频道内的每条**非机器人**消息：

1. 忽略机器人消息、私信。
2. 命中该频道的 `spam-catcher` 规则后开始判定。
3. 若作者拥有 `ignored-roles` 中任一角色 → **跳过**。
4. 判断作者类别：
   - **陌生账号（spammer）**：没有任何非默认身份组，**或** 其全部身份组都属于 `stranger-roles`。
   - **正常账号（hacked，疑似被盗）**：其余情况。
5. 按类别执行对应动作（`spammer` / `hacked`）。
6. 可选：清理该用户近期消息（`clear-message`）、在频道公开通知（`public-log`）。
7. 将结果（成功 / 失败）写入[审计日志](/modules/audit)（`antispam-auto-catch`，标记为自动操作）。

## 动作与所需权限

| 动作 | 含义 | 机器人所需 Discord 权限 |
| --- | --- | --- |
| `kick` | 踢出成员 | 踢出成员（Kick Members） |
| `ban` | 封禁成员 | 封禁成员（Ban Members） |
| `mute` / 分钟数 | 超时（默认 60 分钟，或指定分钟数） | 超时成员（Moderate Members / Timeout） |

::: warning 身份组层级
若机器人已拥有对应权限但操作仍被拒绝，几乎可以确定是**身份组层级问题**：目标的最高身份组不低于机器人最高身份组。此时需将机器人身份组拖到目标之上。这类失败会以「自动操作失败」记录到审计日志并说明原因。
:::

## 处理结果通知

- **疑似被盗（mute）**：会 @ 该用户，提示账号疑似被盗、已临时禁言、请联系管理员（中英双语）。
- **陌生账号（kick/ban）**：公开记录触发的 antispam 动作（中英双语）。
- 是否公开通知由 `public-log` 控制。

## 消息清理

`clear-message` 指定分钟数时，会清理该用户在**服务器范围**内最近 N 分钟的消息（内部复用批量清理服务，不额外写审计，结果并入本次记录）。设为 `null` / `false` 则禁用。

## 配置

```yaml
antispam:
  enabled: false
  spam-catcher: {}        # 按频道配置的捕获规则
  # 示例:
  # 1514685631316496615:
  #   spammer: ban              # 陌生人处理: kick | ban
  #   hacked: mute              # 疑似被盗处理: kick | ban | mute | 分钟数
  #   clear-message: 3          # 自动清理窗口 (分钟, null/false 禁用)
  #   public-log: true          # 是否在频道公开通知
  #   stranger-roles: [1318980288046698506, "新成员"]
  #   ignored-roles: ["管理员", "成员"]
```

### 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用反垃圾模块 |
| `spam-catcher` | `dict[频道ID, 规则]` | `{}` | 按频道配置的捕获规则 |

### 每条规则字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `spammer` | `kick` / `ban` | `ban` | 陌生账号处理方式 |
| `hacked` | `kick` / `ban` / `mute` / 分钟数(int) | `mute` | 疑似被盗账号处理方式 |
| `clear-message` | `int` / `null` / `false` | `3` | 清理消息窗口（分钟），`null`/`false` 禁用 |
| `public-log` | `bool` | `true` | 是否在频道公开通知处理结果 |
| `stranger-roles` | `list[int \| str]` | `[]` | 视为陌生账号的角色列表（身份组 ID 或名称） |
| `ignored-roles` | `list[int \| str]` | `[]` | 忽略处理的角色列表（拥有任一即跳过） |

- `spam-catcher` 的 key 为频道 ID（数字或字符串均可）。
- 角色列表项支持**身份组 ID** 或**身份组名称**（同名身份组会全部匹配）。
