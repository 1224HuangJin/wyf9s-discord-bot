# 公告推送 (announce)

使用 Discord 内置的**频道关注（Channel Following）**功能推送公告，不占用 Bot 的消息发送速率限制。

- **配置键**：无（始终加载）
- **源文件**：`cogs/announce.py`

## 工作方式

1. Bot Admin 在**公告频道**（News/Announcement Channel）中执行 `/announce`
2. 服务器 Mod 使用 `/subscribe` 让本地频道关注公告频道
3. 消息发布后 Discord 自动转发到所有关注的频道

无需存储订阅数据 — Discord 通过 Webhook 自动管理。

## 指令

### `/subscribe` — 关注公告频道

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 参数 | `target`（可选，默认当前频道） |
| 机器人权限 | **管理 Webhook**（Manage Webhooks）在目标频道 |

- 在公告频道中执行，使目标频道关注此公告频道
- 取消关注：在频道设置中删除名为 `wyf9-announce` 的 Webhook

### `/announce` — 发布公告

在公告频道中发布消息，Discord 自动转发到所有关注频道。

| 项目 | 说明 |
| --- | --- |
| 权限 | Admin（仅 config admins） |
| 参数 | `message` / `file` / `message_id`（三选一） |
| 冷却 | 60s |
| 审计 | ✅ 记录 |

发布流程：
1. 提供消息内容（直接输入 / 上传 .md 文件 / 引用消息 ID）
2. Bot 在当前频道发送**预览**并附带确认 / 取消按钮
3. 仅 config admins 可点击确认或取消
4. 确认后消息发布到公告频道，末尾附发送者和时间
5. Discord 自动转发到所有关注频道
