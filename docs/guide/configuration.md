# 配置说明

配置文件为项目根目录下的 `config.yaml`（被 `.gitignore` 忽略），可参考 `config.example.yaml`。配置在启动时由 Pydantic 模型校验，字段的**事实来源**是 `config.example.yaml` 与 `config.py`。

::: tip
`config.*.yaml`（如 `config.prod.yaml`、`config.nbt.yaml`）也会被忽略，可用于保存多套环境配置。
:::

## 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | `str` | **必填** | 机器人 Token |
| `proxy` | `str \| null` | `null` | 代理地址（如 `http://localhost:11451`） |
| `command_prefix` | `str` | `\` | 前缀命令的前缀（示例配置为 `//`） |
| `secret_message_delay` | `int` | `600` | 私密消息删除延迟（秒），用于 `uuid` 等 |

## 日志 `log`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `level` | 枚举 | `INFO` | 控制台日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `file` | `str \| null` | `logs/{time:YYYY-MM-DD}.log` | 日志文件路径（Loguru 格式，`null` 禁用） |
| `file_level` | 枚举 \| `null` | `INFO` | 文件日志级别（`null` 则跟随 `level`） |
| `rotation` | `str \| int` | `1 days` | Loguru 轮转周期 |
| `retention` | `str \| int` | `3 days` | Loguru 保留时间 |

## 模块开关

每个指令模块都有以下通用开关：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `enabled` | `false` | 是否启用该模块（默认全部关闭） |
| `slash` | `true` | 是否注册斜杠命令 |
| `prefix` | `true` | 是否注册前缀命令 |

各模块的专属配置：

- [工具 / 管理 `tools`](/modules/tools#配置) — 含限速配置
- [表情 `emoji`](/modules/emoji#配置)
- [频道锁定 `lock`](/modules/lock#配置)
- [语音频道 `voicechannel`](/modules/voice#配置)
- [自动管理 `rmmsg` / `rmtodo`](/modules/manage#配置)
- [反垃圾 `antispam`](/modules/antispam#配置)
- [审计日志 `audit`](/modules/audit#配置)

## 权限名单

```yaml
admins:
  users: []              # 配置管理员用户 ID / 用户名列表 (拥有所有指令权限)

mods:
  users: []              # 全局 mod 列表
  guilds: {}             # 按服务器 mod 列表 { guild_id: [user...] }
```

- 名单项可以是**用户 ID**（数字）或**用户名**（字符串），两者皆可匹配。
- `mods.guilds` 的 key 为服务器 ID（数字或字符串均可）。

详见[权限系统](/guide/permissions)。

## 完整示例

以下为 `config.example.yaml` 的完整内容：

```yaml
token: "YOUR_BOT_TOKEN"
command_prefix: "//"

# 代理地址 (可选)
# proxy: "http://localhost:11451"

# 日志配置
log:
  level: "INFO"
  file: "logs/{time:YYYY-MM-DD}.log"
  file_level: "INFO"
  rotation: "1 days"
  retention: "3 days"

# 管理操作执行日志 (无指令, 服务模块)
audit:
  enabled: false
  global_channel: null
  global_lang: zh
  guilds: {}

# Emoji 模块
emoji:
  enabled: false
  slash: true
  prefix: true
  base_url: "https://ghimg.siiway.top/emoji"
  max_results: 25

# 工具/管理指令模块
tools:
  enabled: false
  slash: true
  prefix: true
  ratelimit:
    enabled: true
    window: 60
    mod_multiplier: 3
    random: 10
    uuid: 10
    "2file": 10               # to-file 的 YAML 键名 (兼容旧称)

# 频道锁定模块
lock:
  enabled: false
  slash: true
  prefix: true

# 自动删除 todo bot 消息 (无指令, 基于事件)
rmtodo:
  enabled: false
  todo_channels: []
  author_id: 782105629572464652
  remove_delay: 3

# 自动删除消息 (无指令, 基于事件)
rmmsg:
  enabled: false
  nicks: []

# 语音频道控制模块
voicechannel:
  enabled: false
  slash: true
  prefix: true
  allowed_user_ids: []

# 反垃圾消息模块 (无指令, 基于事件)
antispam:
  enabled: false
  spam-catcher: {}

# 管理员和权限配置
admins:
  users: []

mods:
  users: []
  guilds: {}
```
