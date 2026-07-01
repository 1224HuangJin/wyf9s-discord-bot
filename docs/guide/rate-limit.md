# 限速与 Rate Limit

这里的「限速」分为两类：机器人**自定义的指令限速**（应用层），以及 Discord 平台的 **API Rate Limit**（由 discord.py 自动处理）。

## 自定义指令限速

[工具模块](/modules/tools)对以下三个「所有人可用」指令实现了**滑动窗口限速**，防止滥用：

- `random`
- `uuid`
- `2file`

### 工作原理

限速器 `RateLimiter`（`utils.py`）以 `(指令, 用户 ID)` 为 key，记录窗口内的调用时间戳：

```python
def hit(self, key, limit, window) -> tuple[bool, float]:
    # 返回 (是否允许, 若被限则需等待的秒数)
```

- 每个用户对每个指令**独立计数**。
- 超出上限时，机器人回复 `:hourglass: 操作过于频繁, 请在 Ns 后重试`（临时消息）。

### 额度规则

| 用户类型 | 额度 |
| --- | --- |
| **普通用户** | 基础额度（如 `random: 10`） |
| **Mod** | 基础额度 × `mod_multiplier`（默认 ×3） |
| **Admin** | **不受限速** |

> 这里的 Admin 指服务器管理员或配置管理员（`is_admin`）；Mod 指命中 mod 名单者。详见[权限系统](/guide/permissions)。

### 配置

```yaml
tools:
  enabled: true
  ratelimit:
    enabled: true          # 是否启用限速
    window: 60             # 时间窗口 (秒)
    mod_multiplier: 3      # mod 额度倍数 (相对普通用户); admin 不受限速
    random: 10             # random: 普通用户每窗口最大次数
    uuid: 10               # uuid:   普通用户每窗口最大次数
    "2file": 10            # 2file:  普通用户每窗口最大次数
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `true` | 是否启用限速 |
| `window` | `int` | `60` | 时间窗口（秒） |
| `mod_multiplier` | `int` | `3` | mod 相对普通用户的额度倍数 |
| `random` | `int` | `10` | `random` 每窗口最大次数（普通用户） |
| `uuid` | `int` | `10` | `uuid` 每窗口最大次数（普通用户） |
| `2file` | `int` | `10` | `2file` 每窗口最大次数（普通用户，YAML 中写作 `"2file"`） |

::: tip
`2file` 因不是合法的 Python 标识符，在配置模型中通过别名映射（内部字段名 `twofile`）。YAML 中请写作 `"2file"`。
:::

## Discord API Rate Limit

除了应用层限速，Discord 平台本身对 API 调用有 **Rate Limit**。这部分由 **discord.py 自动处理**：库会解析 `X-RateLimit-*` 响应头，在触及限制时自动排队 / 退避重试，无需额外配置。

值得注意的场景：

- **批量清理消息**（`clear-message`）：使用 `bulk_delete`（每批最多 100 条），并且 Discord **不允许批量删除超过 14 天的消息**——超期消息会被单独计数为「因超过 14 天不可删」。
- **表情发送**：会向远程 `base_url` 发起 HTTP 请求（走 `proxy` 配置），受远程服务可用性影响。
- **表情搜索自动补全**：`max_results` 过大可能导致 Discord 自动补全调用失败，默认 `25`。

> 若你在自建大型服务器高频使用，仍建议合理设置自定义限速额度，避免因过量请求触发 Discord 全局限流。
