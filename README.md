# wyf9s-discord-bot

多功能 Discord 机器人，基于 discord.py 构建，使用 YAML + Pydantic 配置验证。模块使用 discord.py Cog 架构，支持热重载。

## 功能模块

| 模块 | 说明 |
|------|------|
| **工具** (`tools`) | 随机数/UUID 生成、消息删除、批量清理消息（支持丰富过滤条件）、频道移动、内容导出为文件 |
| **表情** (`emoji`) | 远程表情包浏览/搜索/发送 (`/e`)，查看表情源构建信息 (`/emoji info`)，更新表情库 (`/emoji update`) |
| **频道锁定** (`lock`) | 锁定/解锁频道（禁止发言），支持定时计划锁定（单次/每日/每周/每月周期）— 使用 `/lock now/unlock/plan/unplan` |
| **语音频道** (`voice`) | 机器人加入/离开语音频道，支持 DAVE 加密 |
| **自动管理** (`manage`) | 按昵称模式自动删消息、自动删除指定频道中特定 bot 的无嵌入消息 |
| **反垃圾** (`antispam`) | 频道级反垃圾规则：陌生人踢/ban、普通用户超时/踢/ban、自动清理消息、审计日志 |
| **审计日志** (`audit`) | 可嵌入审计日志服务，记录操作到指定频道（全局/按服务器） |
| **管理** (`admin`) | 指令同步 `/sync`、模块热重载 `/reload` |
| **动态权限** (`perm`) | `/perm add/rm/show` — 动态权限管理，存储于 `perm.yaml`，`config.yaml` 始终优先 |

## Cog 架构

所有命令模块使用 discord.py **Cog** 架构：

- **热重载**：`/reload [module]` 可热更新单个模块（支持自动补全），有 15s 冷却防滥用
- **状态保持**：语音连接 (voice_client)、emoji 缓存、限速数据、计划锁定数据等存储在 bot 实例上，重载 Cog 不会丢失
- **子命令分组**：相关指令使用 Group 组织（如 `/emoji update`、`/lock plan`）
- **权限集成**：Cog 层统一权限检查，支持 `config.yaml` + `perm.yaml` 双层权限

## 权限系统

三层权限（`config.yaml` 优先于 `perm.yaml`）：

1. **服务器管理员** — Discord `administrator` 权限
2. **配置管理员** — `config.yaml > admins.users`（显示 :lock:锁定，不可被 perm.yaml 覆盖）
3. **Mod** — `mods.users`（全局）或 `mods.guilds[guild_id]`（按服务器）
4. **动态权限** — `perm.yaml` 通过 `/perm add/rm/show` 管理，作为 Mod 权限的补充

## 指令一览

| 指令 | 权限 | 说明 |
|------|------|------|
| `/e <name>` | 所有人 | 发送表情包 |
| `/emoji update` | Admin | 更新表情库 |
| `/emoji info` | 所有人 | 表情库信息 |
| `/random [min] [max]` | 所有人 | 随机数 |
| `/uuid` | 所有人 | 生成 UUID |
| `/2file <name> <content>` | 所有人 | 内容导出为文件 |
| `/delete <id>` | Mod | 删除消息 |
| `/clear-message ...` | Mod | 批量清理消息 |
| `/move-channel ...` | Mod | 移动频道 |
| `/lock now [channel]` | Mod | 锁定频道 |
| `/lock unlock [channel]` | Mod | 解锁频道 |
| `/lock plan ...` | Mod | 计划锁定 |
| `/lock unplan <index>` | Mod | 取消计划 |
| `/joinvc [channel]` | Mod/白名单 | 加入语音 |
| `/leavevc` | Mod/白名单 | 离开语音 |
| `/sync` | Config Admin | 同步斜杠指令 |
| `/reload [module]` | Admin | 热重载模块 |
| `/perm add <user> [module\|command]` | Admin | 添加权限规则 |
| `/perm rm [rid\|user]` | Admin | 删除权限规则 |
| `/perm show [filters]` | Admin | 查看权限规则 |

## 技术栈

- **Python 3.13** — 运行时
- **uv** — 包管理器
- **discord.py** — Discord API (Cog 架构)
- **Pydantic v2** — 配置模型验证
- **PyYAML** — 配置文件解析
- **Loguru** — 日志记录
- **aiohttp** — 异步 HTTP 请求

## 配置

编辑 `config.yaml`（参考 `config.example.yaml`）：

```yaml
token: "your_bot_token"
command_prefix: "//"
# 各模块通过 enabled 开关，slash/prefix 控制命令注册方式
```

动态权限配置示例见 `perm.example.yaml`。

## 部署

```bash
git clone https://github.com/wyf9/wyf9s-discord-bot.git --depth 1
cp config.example.yaml config.yaml
nano config.yaml # edit
uv run main.py
```

## 许可

MIT
