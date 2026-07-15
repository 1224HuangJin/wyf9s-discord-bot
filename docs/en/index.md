---
layout: home

hero:
  name: wyf9s-discord-bot
  text: Multi-purpose Discord bot
  tagline: Built on discord.py, with YAML + Pydantic config validation and a modular design
  actions:
    - theme: brand
      text: Invite the bot
      link: https://discord.com/oauth2/authorize?client_id=1268221966544932945
    - theme: alt
      text: Introduction
      link: /en/guide/introduction
    - theme: alt
      text: Getting Started
      link: /en/guide/getting-started
    - theme: alt
      text: Modules & Commands
      link: /en/modules/
    - theme: alt
      text: GitHub
      link: https://github.com/wyf9/wyf9s-discord-bot

features:
  - icon: 🧰
    title: Tools / Management
    details: Random number / UUID generation, message deletion, conditional bulk message cleanup, channel moving, to-file text-to-file conversion
    link: /en/modules/tools
  - icon: 😄
    title: Emoji
    details: Browse / search / send remote emoji packs, with autocomplete and emoji source build info
    link: /en/modules/emoji
  - icon: 🔒
    title: Channel Lock
    details: Lock / unlock channels, with scheduled locking (one-time / daily / weekly / monthly cycles)
    link: /en/modules/lock
  - icon: 🔊
    title: Voice Channel
    details: Bot joins / leaves voice channels, with DAVE encryption and whitelist-based permission control
    link: /en/modules/voice
  - icon: ⚙️
    title: Management & Hot Reload
    details: Command sync /sync, Cog hot reload /reload (with list autocomplete and a 15s cooldown to prevent abuse)
    link: /en/modules/admin
  - icon: 🔐
    title: Dynamic Permissions
    details: /perm add/rm/show to manage dynamic permission rules in perm.yaml, with config.yaml always taking priority
    link: /en/modules/perm
  - icon: 📢
    title: Announcement Following
    details: Mods subscribe server channels to follow announcement channels, with Discord automatically forwarding messages
    link: /en/modules/announce
  - icon: 🤖
    title: Auto Management
    details: Auto-delete messages by nickname pattern, auto-delete To-Do Bot messages without embeds in specified channels
    link: /en/modules/manage
  - icon: 🛡️
    title: Anti-Spam
    details: "Channel-level anti-spam rules: kick / ban strangers, timeout suspected-compromised accounts, auto-clean messages, audit log"
    link: /en/modules/antispam
  - icon: 📋
    title: Audit Log
    details: An embeddable audit log service that records management actions to a specified channel (global / per-server, bilingual support)
    link: /en/modules/audit
  - icon: 🔑
    title: Multi-tier Permission System
    details: Three-tier permissions (server admin / config admin / Mod) plus dynamic permissions, with unified control via declarative decorators
    link: /en/guide/permissions
  - icon: 🌐
    title: Multilingual (i18n)
    details: /lang switches language per user / server (zh / en), with command descriptions localized to the Discord client language
    link: /en/modules/lang
---
