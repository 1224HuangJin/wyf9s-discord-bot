# 权限系统

本机器人使用**三层自定义权限**（非 Discord 内置角色权限），在 `utils.py` 中实现。

## 三层权限

| 层级 | 判定依据 | 说明 |
| --- | --- | --- |
| **服务器管理员** | Discord `administrator` 权限 | 拥有服务器 `administrator` 权限的成员 |
| **配置管理员** | `config.yaml > admins.users` | 命中 `admins` 名单的用户 |
| **Mod** | `config.yaml > mods.users`（全局）或 `mods.guilds[guild_id]`（按服务器） | 命中 mod 名单的用户 |

### 包含关系

判定是**向上包含**的：

```
服务器管理员  ⊆  admin (is_admin)
配置管理员    ⊆  admin (is_admin)
admin         ⊆  mod   (is_mod)
```

- `is_admin(user)` = 服务器管理员 **或** 配置管理员
- `is_mod(user, guild)` = `is_admin` **或** 全局 mod **或** 该服务器的 mod

也就是说：**admin 自动拥有 mod 权限**，服务器管理员自动拥有 admin 与 mod 权限。

## 名单匹配规则

`admins.users` / `mods.users` / `mods.guilds[*]` 中的每一项可以是：

- **用户 ID**（数字，如 `123456789012345678`）
- **用户名**（字符串，如 `"wyf9"`）
- 数字字符串同样按 ID 匹配

```python
def matches_identity(user, values):
    for value in values:
        if user.id == value or user.name == value:
            return True
        if isinstance(value, str) and value.isdigit() and user.id == int(value):
            return True
    return False
```

::: warning
用户名匹配基于 Discord 全局用户名（`user.name`），并非服务器昵称（`display_name`）。推荐优先使用**用户 ID** 以避免歧义。
:::

## 声明式权限控制

指令的处理方法通过 `@u.requires(...)` 装饰器声明所需权限等级：

```python
@u.requires(u.Permission.MOD)
async def _handle_lock(self, source, channel=None):
    ...
```

权限等级枚举 `Permission`：

| 等级 | 含义 |
| --- | --- |
| `Permission.EVERYONE` | 所有人可用 |
| `Permission.MOD` | 需要 mod（含 admin） |
| `Permission.ADMIN` | 需要 admin（服务器管理员 / 配置管理员） |

也支持传入**自定义判定函数** `(module, user, guild) -> bool`，例如[语音模块](/modules/voice)的白名单判定。

当权限不通过时，机器人会回复 `:x: 你没有权限使用此指令 :x:`（临时消息，10 秒后删除）并中止执行。

## 各指令所需权限速查

| 指令 | 所需权限 |
| --- | --- |
| `random` / `uuid` / `2file` | 所有人（受[限速](/guide/rate-limit)） |
| `emoji` / `emoji-info` | 所有人 |
| `delete` / `clear-message` / `move-channel` | Mod |
| `lock` / `unlock` / `plan-lock` / `unplan-lock` | Mod |
| `vc join` / `vc leave` | 白名单用户或 Mod（见[语音模块](/modules/voice)） |
| `emoji-update` | Admin |
| `sync` / `sync-commands` | 配置管理员（`admins.users`） |

::: tip `sync` 的特殊性
`sync` / `sync-commands` 使用 `is_config_admin` 判定，即**仅限 `admins.users` 名单**，服务器管理员权限不足以使用它。
:::
