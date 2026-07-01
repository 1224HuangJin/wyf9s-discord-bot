# 快速开始

## 前置要求

- **Python 3.13**（`pyproject.toml` 要求 `>=3.10`，`.python-version` 指定 `3.13`）
- **[uv](https://docs.astral.sh/uv/)** 包管理器
- 一个 Discord 机器人 Token（在 [Discord Developer Portal](https://discord.com/developers/applications) 创建应用并获取）

## 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/wyf9/wyf9s-discord-bot.git --depth 1
cd wyf9s-discord-bot

# 2. 复制示例配置
cp config.example.yaml config.yaml

# 3. 编辑配置 (至少填入 token)
nano config.yaml

# 4. 运行 (uv 会自动创建虚拟环境并安装依赖)
uv run main.py
```

`update.sh` 可用于更新：

```bash
sh update.sh
```

## 机器人权限与 Intents

### Gateway Intents

机器人在代码中启用了 **Message Content Intent**（`intents.message_content = True`）。你需要在 Discord Developer Portal 的应用设置中打开 **Message Content Intent**（`Bot` → `Privileged Gateway Intents`），否则前缀命令与部分事件功能无法正常工作。

### 邀请机器人所需权限

根据你启用的模块，机器人在服务器中至少需要以下权限：

| 权限 | 用于 |
| --- | --- |
| 查看频道 / 发送消息 / 嵌入链接 / 附加文件 | 基础功能、发送嵌入 / 文件 |
| 管理消息（Manage Messages） | `delete` / `clear-message` / 自动删除 |
| 管理频道（Manage Channels） | `move-channel` |
| 管理身份组 / 管理频道 | `/lock now` `/lock unlock` `/lock plan`（修改频道权限覆盖） |
| 连接 / 使用语音（Connect / Speak） | `vc join` / `vc leave` |
| 踢出成员（Kick Members） | 反垃圾 `kick` |
| 封禁成员（Ban Members） | 反垃圾 `ban` |
| 超时成员（Moderate Members / Timeout） | 反垃圾 `mute` |

::: warning 身份组层级
执行踢出 / 封禁 / 超时 / 修改权限等操作时，**机器人身份组必须高于被操作对象的最高身份组**，否则即使拥有权限也会被 Discord 拒绝（反垃圾模块会在审计日志中明确提示这一点）。
:::

## 最小配置示例

```yaml
token: "YOUR_BOT_TOKEN"
command_prefix: "//"

# 只启用工具模块作为示例
tools:
  enabled: true
  slash: true
  prefix: true

# 你自己的用户 ID / 用户名，赋予配置管理员权限
admins:
  users:
    - 123456789012345678
```

更多配置项见[配置说明](/guide/configuration)。

## 代码质量（开发）

修改代码后请运行：

```bash
uvx ruff check --fix && uvx ruff format && uvx ty check --fix
```

- `ruff check --fix` — lint 并自动修复
- `ruff format` — 格式化
- `ty check --fix` — 类型检查并自动修复
