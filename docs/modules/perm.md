# 动态权限 (perm)

通过 `/perm` 指令管理动态权限规则，存储于 `perm.yaml`。`config.yaml` 中的配置始终优先。

- **配置键**：`perm`
- **源文件**：`cogs/perm.py`、`perm.py`
- **数据文件**：`perm.yaml`

## 工作原理

动态权限作为 `config.yaml` 中 `mods` / `admins` 的**补充**：

1. 先检查 `config.yaml`：命中则通过（显示 :lock: 锁定）
2. 若未命中，回退到 `perm.yaml` 规则
3. `config.yaml` 始终优先，无法被 `/perm` 覆盖

## 指令

### `/perm add` — 添加规则

| 项目 | 说明 |
| --- | --- |
| 权限 | Admin（config admins）或服务器管理员（仅限 server scope） |
| 参数 | `user`（必填，逗号分隔多个用户）、`module` / `command`（二选一）、`global`（bool） |

- 服务器管理员仅可添加 `global=False` 的规则。

### `/perm rm` — 删除规则

| 项目 | 说明 |
| --- | --- |
| 权限 | Admin 或服务器管理员 |
| 参数 | `rid`（规则 ID）或 `user` / `module` / `command` 组合筛选 |

### `/perm show` — 查看规则

| 项目 | 说明 |
| --- | --- |
| 权限 | Admin 或服务器管理员 |
| 参数 | `user`、`module`、`command`（可选筛选）、`scope`（`server` 默认 / `global`）、`private`（DM 发送） |

- 服务器管理员自动显示 :lock: 标记
- 结果超过 2000 字符时以 `.md` 文件附件发送

## 配置

```yaml
perm:
  enabled: false
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- |
| `enabled` | `bool` | `false` | 是否启用动态权限模块 |

::: tip 权限数据
规则数据存储在 `perm.yaml` 中，建议通过 `/perm` 指令管理而非手动编辑。示例见 `perm.example.yaml`。
:::
