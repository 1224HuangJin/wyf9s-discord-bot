# 多语言 (lang)

切换用户 / 服务器的语言偏好，机器人所有面向用户的文本均支持多语言（i18n）。

- **配置键**：无（该模块始终启用）
- **源文件**：`cogs/lang.py`、`i18n.py`、`lang_store.py`、`lang/*.yaml`

## 语言解析优先级

机器人为每条消息按以下优先级解析应使用的语言：

1. **用户偏好** — 用户通过 `/lang` 设置的个人语言
2. **服务器偏好** — 服务器管理员通过 `/lang scope:server` 设置的语言
3. **默认语言** — `zh`（简体中文）

偏好持久化到 `lang_settings.yaml`（自动生成）。

## 指令

### `/lang` — 设置 / 查看语言偏好

| 项目 | 说明 |
| --- | --- |
| 权限 | 所有人（`scope:server` 需要「管理服务器」权限或配置管理员） |
| 参数 | `lang`（可选，`zh` / `en`，留空则查看当前设置）、`scope`（可选，`user`（默认）/ `server`） |

- `/lang lang:en` — 将**你的**语言设为英文。
- `/lang lang:zh scope:server` — 将**本服务器**默认语言设为中文（需管理权限）。
- `/lang` — 查看你当前的语言偏好。
- `/lang scope:server` — 查看本服务器的语言偏好。

## 覆盖范围

多语言分为两类文本，处理方式不同：

| 类型 | 示例 | 本地化方式 |
| --- | --- | --- |
| **运行时消息** | 命令回复、报错、审计日志、反垃圾提示 | 按上述优先级**逐用户 / 逐服务器**解析 |
| **斜杠命令 / 参数描述** | Discord 指令面板中的说明文字 | 通过 discord.py 命令本地化（`locale_str` + `Translator`），随用户 **Discord 客户端语言** 显示 |

> 命令**名称**（如 `/random`）保持不变，不做本地化。

## 支持的语言

| 代码 | 语言 | Discord Locale |
| --- | --- | --- |
| `zh` | 简体中文（默认） | `zh-CN` / `zh-TW` |
| `en` | English | `en-US` / `en-GB` |

## 新增语言

1. 复制 `lang/zh.yaml` 为 `lang/<code>.yaml` 并翻译其中所有值（保持键不变）。
2. 在 `i18n.py` 中将 `<code>` 加入 `SUPPORTED_LANGS`。
3. 如需 Discord 客户端语言联动，在 `i18n.py` 的 `_LOCALE_TO_LANG` 中补充 locale 映射。

> `lang/zh.yaml` 与 `lang/en.yaml` 必须保持**键完全一致**，新增文本时需同步两个文件。
