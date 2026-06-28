# wyf9s-discord-bot

多功能 Discord 机器人，基于 discord.py 构建，使用 YAML + Pydantic 配置验证。

## 功能模块

| 模块 | 说明 |
|------|------|
| **工具** (`tools`) | 随机数/UUID 生成、消息删除、批量清理消息（支持丰富过滤条件）、频道移动、内容导出为文件、指令同步 |
| **表情** (`emoji`) | 远程表情包浏览/搜索/发送，查看表情源构建信息 |
| **频道锁定** (`lock`) | 锁定/解锁频道（禁止发言），支持定时计划锁定（单次/每日/每周/每月周期） |
| **语音频道** (`voice`) | 机器人加入/离开语音频道，支持 DAVE 加密 |
| **自动管理** (`manage`) | 按昵称模式自动删消息、自动删除指定频道中特定 bot 的无嵌入消息 |
| **反垃圾** (`antispam`) | 频道级反垃圾规则：陌生人踢/ban、普通用户超时/踢/ban、自动清理消息、审计日志 |
| **审计日志** (`audit`) | 可嵌入审计日志服务，记录操作到指定频道（全局/按服务器） |

## 模块模式

所有模块为普通 Python 类（非 Cog），支持同时注册斜杠命令和前缀命令，通过 `send_msg()` 统一处理交互来源。

## 权限系统

三层自定义权限（非 Discord 内置）：
1. **服务器管理员** — Discord `administrator` 权限
2. **配置管理员** — `config.yaml > admins.users`
3. **Mod** — `mods.users`（全局）或 `mods.guilds[guild_id]`（按服务器）

## 技术栈

- **Python 3.13** — 运行时
- **uv** — 包管理器
- **discord.py** — Discord API
- **Pydantic v2** — 配置模型验证
- **PyYAML** — 配置文件解析
- **Loguru** — 日志记录
- **aiohttp** — 异步 HTTP 请求

## 配置

编辑 `config.yaml`（参考 `config.prod.yaml` / `config.nbt.yaml`）：

```yaml
token: "your_bot_token"
prefix: "//"
# 各模块通过 enabled 开关，slash/prefix 控制命令注册方式
```

## 部署

```bash
git clone https://github.com/wyf9/wyf9s-discord-bot.git --depth 1
cp config.example.yaml config.yaml
nano config.yaml # edit
uv run main.py
```

## 许可

MIT
