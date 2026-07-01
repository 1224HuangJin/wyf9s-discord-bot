# 公告推送 (announce)

使用 Discord 内置的**频道关注（Channel Following）**功能。Mod 通过 `/subscribe` 使本地频道关注配置中指定的公告频道，消息自动转发。

- **配置键**：`announce`
- **源文件**：`cogs/announce.py`

## 配置

```yaml
announce:
  source_channel: null  # 公告频道 ID (News Channel)
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- |
| `source_channel` | `int \| null` | `null` | 公告频道 ID，设置为 null 禁用 |

## 指令

### `/subscribe` — 关注公告频道

使本服务器的目标频道关注配置的公告频道。

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 参数 | `target`（可选，默认当前频道） |
| 机器人权限 | **管理 Webhook**（Manage Webhooks）在目标频道 |

- 关注后 Discord 自动将公告频道的消息转发到目标频道
- 取消关注：在频道设置 → 集成 → Webhook 中删除对应 Webhook
