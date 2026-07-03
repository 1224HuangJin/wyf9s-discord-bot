# 自动管理 (manage)

基于 `on_message` 事件的自动删除功能，**无指令**。包含两个独立子功能，分别由 `rmmsg` 和 `rmtodo` 配置控制。

- **配置键**：`rmmsg`（按昵称删消息）、`rmtodo`（删 To-Do Bot 消息）
- **源文件**：`cogs/manage.py`

::: tip 启用条件
只要 `rmmsg.enabled` **或** `rmtodo.enabled` 任一为真，模块即会加载并注册 `on_message` 监听。
:::

## rmmsg — 按昵称模式自动删消息

当消息作者的**用户名**匹配 `nicks` 中任一模式时，自动删除该消息（延迟 2 秒）。

- 匹配使用 `fnmatch`，**支持通配符**（如 `[DC] @system`、`*bot*`）。
- 机器人需要 **管理消息（Manage Messages）** 权限。

### 配置

```yaml
rmmsg:
  enabled: false
  nicks: []               # 要自动删除的昵称模式列表 (支持通配符)
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用 |
| `nicks` | `list[str]` | `[]` | 要自动删除的昵称模式列表（fnmatch 通配符） |

## rmtodo — 自动删除 To-Do Bot 无嵌入消息

在指定的 todo 频道中，若某条消息满足以下**全部条件**，则延迟删除：

1. 频道 ID 在 `todo_channels` 中；
2. 作者是指定的 To-Do Bot（`author_id`）；
3. 消息**不含 embeds**（无嵌入内容）。

用于清理 To-Do List Bot 产生的纯文本 / 无嵌入通知消息，保留带嵌入的正式内容。

### 配置

```yaml
rmtodo:
  enabled: false
  todo_channels: []                 # todo 频道 ID 列表
  author_id: 782105629572464652     # To-Do Bot 的用户 ID
  remove_delay: 3                   # 删除前等待秒数
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用 |
| `todo_channels` | `list[int]` | `[]` | 生效的 todo 频道 ID 列表 |
| `author_id` | `int` | `782105629572464652` | To-Do Bot 的用户 ID |
| `remove_delay` | `int` | `3` | 删除前等待秒数 |
