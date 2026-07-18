# wyf9s-discord-bot

多功能 Discord 机器人，基于 discord.py 构建，使用 YAML + Pydantic 配置验证。模块使用 discord.py Cog 架构，支持热重载。内置多语言（i18n）支持，可按用户 / 服务器切换语言。

## 功能模块

| 模块 | 说明 |
|------|------|
| **工具** (`tools`) | 随机数/UUID 生成、消息删除、批量清理消息（支持丰富过滤条件）、频道移动、内容导出为文件 |
| **表情** (`emoji`) | 远程表情包浏览/搜索/发送 (`/e`)，查看表情源构建信息 (`/emoji info`)，更新表情库 (`/emoji update`) |
| **频道锁定** (`lock`) | 锁定/解锁频道（禁止发言），支持定时计划锁定（单次/每日/每周/每月周期）— 使用 `/lock now/unlock/plan/unplan` |
| **语音频道** (`voice`) | 机器人加入/离开语音频道，支持 DAVE 加密 |
| **自动管理** (`manage`) | 按昵称模式自动删消息、自动删除指定频道中特定 bot 的无嵌入消息 |
| **反垃圾** (`antispam`) | 频道级反垃圾规则：陌生人踢/ban、普通用户超时/踢/ban、自动清理消息、审计日志 |
| **审计日志** (`audit`) | 可嵌入审计日志服务，仅记录 [ADMIN]/[MOD] 指令、服务器 scope 修改、反垃圾自动处置与错误（全局/按服务器） |
| **管理** (`admin`) | 指令同步 `/sync`、模块/配置热重载 `/reload`（留空重载全部、`config` 重载配置） |
| **动态权限** (`perm`) | `/perm add/rm/show` 子指令 — 动态权限管理（按模块 / 指令 / 或不填授予 mod 权限），存储于 `perm.yaml`，`config.yaml` 始终优先 |
| **公告推送** (`announce`) | `/subscribe` 关注公告频道 |
| **多语言** (`lang`) | `/lang` 切换用户 / 服务器语言（`zh` / `en`），偏好持久化到 `lang_settings.yaml` |

## 多语言 (i18n)

- 所有面向用户的文本通过 `lang/zh.yaml`（默认）与 `lang/en.yaml` 提供翻译。
- **运行时消息**：按 `用户 > 服务器 > 默认(zh)` 的优先级解析语言，由 `/lang` 设置。
- **斜杠命令 / 参数描述**：通过 discord.py 的命令本地化（`locale_str` + `Translator`）随用户 Discord 客户端语言显示（`en-US` / `zh-CN` 等）。
- 新增语言：添加 `lang/<code>.yaml` 并在 `i18n.py` 中扩展 `SUPPORTED_LANGS` 与 locale 映射。

## Cog 架构

所有命令模块使用 discord.py **Cog** 架构：

- **热重载**：`/reload [module]` 可热更新模块（动态自动补全，1s 缓存）；留空重载全部、`config` 重载配置，有 15s 冷却防滥用
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
| `/to-file <name> <content>` | 所有人 | 内容导出为文件 |
| `/delete <id>` | Mod | 删除消息 |
| `/clear-message ...` | Mod | 批量清理消息（支持论坛帖子清理 / 删除整帖） |
| `/move-channel ...` | Mod | 移动频道 |
| `/lock now [channel]` | Mod | 锁定频道 |
| `/lock unlock [channel]` | Mod | 解锁频道 |
| `/lock plan ...` | Mod | 计划锁定 |
| `/lock unplan <index>` | Mod | 取消计划 |
| `/vc join [channel]` | Mod/白名单 | 加入语音 |
| `/vc leave` | Mod/白名单 | 离开语音 |
| `/sync` | Config Admin | 同步斜杠指令 |
| `/reload [module]` | Admin | 热重载模块（留空全部 / `config` 重载配置） |
| `/perm add <user\|role> [module\|command]` | Admin | 添加权限规则（`user` 与 `role` 二选一；module 可下拉选择；都不填 = 授予 mod） |
| `/perm rm [rid\|user]` | Admin | 删除权限规则 |
| `/perm show` | Admin | 查看权限规则 |
| `/subscribe [channel]` | Mod | 关注公告频道 |
| `/lang [lang] [scope]` | 所有人（server 范围需管理权限） | 切换语言偏好 |

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

可通过启动参数（或对应环境变量，命令行优先）指定配置 / token 来源：

```bash
uv run main.py --config /path/to/config.yaml   # 指定配置文件 (env: W9DCBOT_CONFIG)
uv run main.py --token-file /path/to/tk.yaml   # 指定 token 文件 (env: W9DCBOT_TOKEN_FILE)
uv run main.py --token "YOUR_BOT_TOKEN"         # 直接指定 token   (env: W9DCBOT_TOKEN)
uv run main.py --data-dir /path/to/data         # 数据文件目录     (env: W9DCBOT_DATA_DIR)
```

Token 优先级：`--token` / `W9DCBOT_TOKEN` > token 文件（`tk.yaml`）> `config.yaml`。

数据文件（`perm.yaml` / `lang_settings.yaml` / `schedules.yaml`）及日志文件默认存放于 `./data/`，可用 `--data-dir` 指定；读取时若不存在会回退到程序目录。多实例部署请为各实例指定独立的数据目录以避免数据互相干扰。

### （可选）Systemd — 后台运行、进程守护、自动重启与开机自启动

若您希望该 Bot 在后台运行，具备进程守护、崩溃自动重启以及开机自启动能力，推荐使用 `systemd` 来管理。

1. **创建服务文件**：

```bash
sudo nano /etc/systemd/system/wyf9s-bot.service
```

2. **粘贴以下内容（请根据实际情况修改）**：

```
[Unit]
Description=wyf9s Discord Bot Service
After=network.target

[Service]
Type=simple
ExecStart=/root/.local/bin/uv run /root/wyf9s-discord-bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target  
```

并 `ctrl + x` 输入 `y` 并使用 `enter` 键。

3. **并依次执行**：

```bash
sudo systemctl daemon-reload
sudo systemctl start wyf9s-bot
sudo systemctl enable wyf9s-bot
```

<details>
<summary>Systemd 常用命令</summary>
<br>

|操作|命令|
|:---|:---:|
|查看状态|sudo systemctl status wyf9s-bot|
|启动服务|sudo systemctl start wyf9s-bot|
|停止服务|sudo systemctl stop wyf9s-bot|
|重启服务|sudo systemctl restart wyf9s-bot|
|查看日志|sudo journalctl -u wyf9s-bot -f|
|查看最近 50 行日志|sudo journalctl -u wyf9s-bot -n 50 --no-pager|
|禁用开机自启|sudo systemctl disable wyf9s-bot|

</details>

#### 如果需要运行多个 Bot 实例：

1. **首先创建第二个服务文件**：

```bash
sudo nano /etc/systemd/system/wyf9s-bot-2.service
```

2. **粘贴以下内容**：

* 请注意修改 `YOUR_TOKEN` 至您的Discord Bot Token。

```
[Unit]
Description=wyf9s Discord Bot Service 2
After=network.target

[Service]
Type=simple
ExecStart=/root/.local/bin/uv run /root/wyf9s-discord-bot/main.py --token "YOUR_TOKEN"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. **并依次执行**：

```bash
sudo systemctl daemon-reload
sudo systemctl start wyf9s-bot-2
sudo systemctl enable wyf9s-bot-2
```

## 许可

[MIT](https://github.com/wyf9/wyf9s-discord-bot?tab=MIT-1-ov-file)
