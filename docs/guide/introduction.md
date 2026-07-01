# 项目介绍

`wyf9s-discord-bot` 是一个多功能 Discord 机器人，基于 [discord.py](https://discordpy.readthedocs.io/) 构建，使用 YAML + [Pydantic v2](https://docs.pydantic.dev/) 进行配置验证，采用模块化设计。

## 整体架构

```
config.py            # Pydantic 配置模型 + 加载器
config.yaml          # 运行时配置 (被 gitignore)
config.example.yaml  # 带内联文档的示例配置 (配置字段的事实来源)
schedules.yaml       # 计划锁定数据 (自动生成)
main.py              # 机器人入口，模块加载
utils.py             # 共享工具 (权限判定、限速器、消息发送等)
modules/
  audit.py           # 审计日志服务 (共享)
  emoji.py           # 表情 / 贴纸指令
  tools.py           # 工具 / 管理指令
  lock.py            # 频道锁定 / 解锁 + 计划锁定
  manage.py          # 自动删除事件处理
  voice.py           # 语音频道指令
  antispam.py        # 反垃圾消息处理
  clear_message.py   # 批量清理消息服务 (共享)
```

## 启动流程

`main.py` 的启动过程如下：

1. **初始化日志**：先配置 [Loguru](https://loguru.readthedocs.io/)，并将标准库 `logging`（含 discord.py 的日志）拦截转发到 Loguru。
2. **加载配置**：`Config()` 读取 `config.yaml`，用 Pydantic 模型校验。校验失败或文件缺失会直接退出。
3. **重配置日志**：根据配置的日志等级、文件路径、轮转/保留策略重新设置输出。
4. **创建客户端**：`commands.Bot`，启用 `message_content` intent，可选配置代理。
5. **按需加载模块**：根据各模块的 `enabled` 开关实例化对应模块，注册斜杠 / 前缀指令。
6. **登录**：`on_ready` 时同步斜杠指令（若有）、同步表情列表、启动锁定计划任务。

## 核心设计

### 模块模式

所有模块都是**普通 Python 类**（不是 discord.py 的 Cog）。指令在 `__init__` 中注册，斜杠命令与前缀命令共用同一套处理逻辑：

```python
class MyModule:
    def __init__(self, config, client, audit):
        if self.c.mymodule.slash:
            self._register_slash_commands(client)
        if self.c.mymodule.prefix:
            self._register_prefix_commands(client)

    async def _handle_cmd(self, source):
        # 同时处理 Interaction (斜杠) 与 Context (前缀)
        await u.send_msg(source, "...")
```

`utils.send_msg()` 统一处理两种交互来源（`discord.Interaction` / `commands.Context`），前缀模式下会自动回复原消息。

### 声明式权限控制

通过 `@u.requires(Permission.MOD)` 装饰器统一进行权限判定，详见 [权限系统](/guide/permissions)。

### 双命令模式

| 模式 | 触发方式 | 配置开关 |
| --- | --- | --- |
| 斜杠命令 | `/random` | 各模块的 `slash: true` |
| 前缀命令 | `//random`（前缀由 `command_prefix` 决定） | 各模块的 `prefix: true` |

::: tip 关于前缀命令的参数
斜杠命令通过 Discord 原生参数 UI 传参；前缀命令部分复杂指令（如 `clear-message`、`plan-lock`）使用 `--key=value` 形式的 flag 传参（支持带引号的值）。
:::

## 技术栈

| 组件 | 说明 |
| --- | --- |
| **Python 3.13** | 运行时（`pyproject.toml` 要求 `>=3.10`） |
| **[uv](https://docs.astral.sh/uv/)** | 包管理器 |
| **[discord.py](https://discordpy.readthedocs.io/)** `[voice]` | Discord API 封装 |
| **[Pydantic v2](https://docs.pydantic.dev/)** | 配置模型验证 |
| **[PyYAML](https://pyyaml.org/)** | 配置文件解析 |
| **[Loguru](https://loguru.readthedocs.io/)** | 日志记录 |
| **[aiohttp](https://docs.aiohttp.org/)** | 异步 HTTP 请求 |
| **davey / PyNaCl** | 语音 / DAVE 加密支持 |

## 功能模块一览

| 模块 | 键名 | 类型 | 说明 |
| --- | --- | --- | --- |
| [工具 / 管理](/modules/tools) | `tools` | 指令 | 随机数 / UUID、删消息、批量清理、频道移动、文本转文件、指令同步 |
| [表情](/modules/emoji) | `emoji` | 指令 | 远程表情包浏览 / 搜索 / 发送 |
| [频道锁定](/modules/lock) | `lock` | 指令 | 锁定 / 解锁频道，计划锁定 |
| [语音频道](/modules/voice) | `voicechannel` | 指令 | 加入 / 离开语音频道 |
| [自动管理](/modules/manage) | `rmmsg` / `rmtodo` | 事件 | 自动删除消息 |
| [反垃圾](/modules/antispam) | `antispam` | 事件 | 频道级反垃圾规则 |
| [审计日志](/modules/audit) | `audit` | 服务 | 记录管理操作到指定频道 |

> 每个模块的详细指令、用法、所需权限见[模块总览](/modules/)。
