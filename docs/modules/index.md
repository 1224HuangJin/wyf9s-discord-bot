# 模块总览

机器人由多个模块组成，均通过 `config.yaml` 中的 `enabled` 开关**按需启用**（默认全部关闭）。模块分为三类：

- **指令模块**：注册斜杠 / 前缀命令供用户调用。
- **事件模块**：无指令，监听 Discord 事件（如 `on_message`）自动执行。
- **服务模块**：无指令，为其他模块提供共享能力（如审计日志）。

## 模块清单

| 模块 | 配置键 | 类型 | 指令 | 文档 |
| --- | --- | --- | --- | --- |
| 工具 / 管理 | `tools` | 指令 | `random` `uuid` `2file` `delete` `clear-message` `move-channel` `sync` | [查看](/modules/tools) |
| 表情 | `emoji` | 指令 | `emoji` `emoji-info` `emoji-update` | [查看](/modules/emoji) |
| 频道锁定 | `lock` | 指令 | `lock` `unlock` `plan-lock` `unplan-lock` | [查看](/modules/lock) |
| 语音频道 | `voicechannel` | 指令 | `vc join` `vc leave` | [查看](/modules/voice) |
| 自动管理 | `rmmsg` / `rmtodo` | 事件 | 无 | [查看](/modules/manage) |
| 反垃圾 | `antispam` | 事件 | 无 | [查看](/modules/antispam) |
| 审计日志 | `audit` | 服务 | 无 | [查看](/modules/audit) |

## 指令速查表

| 指令 | 模块 | 权限 | 限速 | 说明 |
| --- | --- | --- | --- | --- |
| `/random` | tools | 所有人 | ✅ | 生成范围随机数 |
| `/uuid` | tools | 所有人 | ✅ | 生成 UUID（私密消息） |
| `/2file` | tools | 所有人 | ✅ | 文本转文件发送 |
| `/delete` | tools | Mod | — | 删除单条消息 |
| `/clear-message` | tools | Mod | — | 按条件批量清理消息 |
| `/move-channel` | tools | Mod | — | 移动频道位置 / 分类 |
| `/sync` | tools | 配置管理员 | — | 同步斜杠指令列表 |
| `/emoji` | emoji | 所有人 | — | 发送库中表情包 |
| `/emoji-info` | emoji | 所有人 | — | 查看表情库信息 |
| `/emoji-update` | emoji | Admin | — | 更新表情库数据 |
| `/lock` | lock | Mod | — | 锁定频道 |
| `/unlock` | lock | Mod | — | 解锁频道 |
| `/plan-lock` | lock | Mod | — | 计划锁定 / 解锁 |
| `/unplan-lock` | lock | Mod | — | 取消计划 |
| `/vc join` | voice | 白名单 / Mod | — | 机器人加入语音频道 |

| `/vc leave` | voice | 白名单 / Mod | — | 机器人离开语音频道 |
> 权限体系详见[权限系统](/guide/permissions)，限速详见[限速与 Rate Limit](/guide/rate-limit)。

## 双命令模式

所有指令模块均可通过 `slash` / `prefix` 开关分别控制斜杠命令与前缀命令的注册。前缀命令的前缀由顶层 `command_prefix` 决定（示例配置为 `//`）。

- 斜杠命令示例：`/random 1 100`
- 前缀命令示例：`//random 1 100`

复杂指令（`clear-message`、`plan-lock`）的前缀形式使用 `--key=value` flag 传参，例如：

```
//clear-message --user=@某人 --within=30m --scope=channel
```
