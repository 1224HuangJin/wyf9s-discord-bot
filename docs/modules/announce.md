# 公告推送 (announce)

向订阅的频道推送全局公告。服务器 Mod 订阅频道，Bot Admin 发布公告。

- **配置键**：无（始终加载）
- **源文件**：`cogs/announce.py`
- **数据文件**：`subscribe.yaml`

## 工作方式

使用 **Discord Webhook** 推送公告，不占用 Bot 的消息发送速率限制：

1. `/subscribe` 在目标频道创建名为 `wyf9-announce` 的 Webhook
2. `/announce` 通过所有 Webhook URL 发送消息（HTTP POST，不计入 Bot API 限速）
3. 同一频道再次执行 `/subscribe` 取消订阅（删除 Webhook）

## 指令

### `/subscribe` — 订阅 / 取消订阅

| 项目 | 说明 |
| --- | --- |
| 权限 | Mod |
| 参数 | `channel`（可选，默认当前频道） |
| 机器人权限 | **管理 Webhook**（Manage Webhooks） |
| 审计 | ✅ 记录 |

- 首次执行：在目标频道创建 Webhook 并订阅
- 再次执行：删除 Webhook 并取消订阅

### `/announce` — 发布公告

向所有已订阅频道推送公告。

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
4. 确认后通过 Webhook 发送到所有订阅频道，末尾附发送者和时间
