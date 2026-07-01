---
layout: home

hero:
  name: wyf9s-discord-bot
  text: 多功能 Discord 机器人
  tagline: 基于 discord.py 构建，使用 YAML + Pydantic 配置验证，模块化设计
  actions:
    - theme: brand
      text: 项目介绍
      link: /guide/introduction
    - theme: alt
      text: 快速开始
      link: /guide/getting-started
    - theme: alt
      text: 模块 & 指令
      link: /modules/
    - theme: alt
      text: GitHub
      link: https://github.com/wyf9/wyf9s-discord-bot

features:
  - icon: 🧰
    title: 工具 / 管理
    details: 随机数 / UUID 生成、消息删除、按条件批量清理消息、频道移动、文本转文件
    link: /modules/tools
  - icon: 😄
    title: 表情
    details: 远程表情包浏览 / 搜索 / 发送，支持自动补全与查看表情源构建信息
    link: /modules/emoji
  - icon: 🔒
    title: 频道锁定
    details: 锁定 / 解锁频道，支持定时计划锁定（单次 / 每日 / 每周 / 每月周期）
    link: /modules/lock
  - icon: 🔊
    title: 语音频道
    details: 机器人加入 / 离开语音频道，支持 DAVE 加密与白名单权限控制
    link: /modules/voice
  - icon: ⚙️
    title: 管理 & 热重载
    details: 指令同步 /sync、Cog 热重载 /reload (支持列表补全，15s 冷却防滥用)
    link: /modules/admin
  - icon: 🔐
    title: 动态权限
    details: /perm add/rm/show 管理 perm.yaml 动态权限规则，config.yaml 始终优先
    link: /modules/perm
  - icon: 🤖
    title: 自动管理
    details: 按昵称模式自动删消息、自动删除指定频道中 To-Do Bot 的无嵌入消息
    link: /modules/manage
  - icon: 🛡️
    title: 反垃圾
    details: 频道级反垃圾规则：陌生人踢 / ban、疑似被盗账号超时、自动清理消息、审计日志
    link: /modules/antispam
  - icon: 📋
    title: 审计日志
    details: 可嵌入的审计日志服务，将管理操作记录到指定频道（全局 / 按服务器，支持中英双语）
    link: /modules/audit
  - icon: 🔑
    title: 多层权限系统
    details: 服务器管理员 / 配置管理员 / Mod 三层权限 + 动态权限，声明式装饰器统一控制
    link: /guide/permissions
---

## 这是什么？

`wyf9s-discord-bot` 是一个**多功能、模块化**的 Discord 机器人：

- **模块化**：每个功能都是独立 Cog 模块，通过 `config.yaml` 中的 `enabled` 开关按需启用，支持热重载
- **双命令模式**：所有指令模块同时支持**斜杠命令**（`/cmd`）与**前缀命令**（`//cmd`），可分别开关
- **配置驱动**：使用 YAML + Pydantic v2 强类型校验，启动时验证配置，出错即报
- **多层权限**：服务器管理员 / 配置管理员 / Mod / 动态权限多层体系
- **可观测**：内置审计日志服务，管理操作可记录到指定频道

> 详细技术栈与设计说明见 [项目介绍](/guide/introduction)。
