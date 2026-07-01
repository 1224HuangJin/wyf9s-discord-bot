import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'zh-CN',
  title: 'wyf9s-discord-bot',
  description: '多功能 Discord 机器人 · 文档',

  // 使用自定义域名 dc-bot.wyf9.top，站点部署在根路径
  base: '/',

  lastUpdated: true,
  cleanUrls: true,
  ignoreDeadLinks: true,

  head: [
    ['meta', { name: 'theme-color', content: '#5865F2' }],
  ],

  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: '指南', link: '/guide/introduction' },
      { text: '模块 & 指令', link: '/modules/' },
      { text: '配置', link: '/guide/configuration' },
      {
        text: '相关链接',
        items: [
          { text: 'GitHub 仓库', link: 'https://github.com/wyf9/wyf9s-discord-bot' },
          { text: 'discord.py 文档', link: 'https://discordpy.readthedocs.io/' },
        ],
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: '开始',
          items: [
            { text: '项目介绍', link: '/guide/introduction' },
            { text: '快速开始', link: '/guide/getting-started' },
            { text: '配置说明', link: '/guide/configuration' },
            { text: '权限系统', link: '/guide/permissions' },
            { text: '限速与 Rate Limit', link: '/guide/rate-limit' },
          ],
        },
      ],
      '/modules/': [
        {
          text: '总览',
          items: [{ text: '模块总览', link: '/modules/' }],
        },
        {
          text: '指令模块',
          items: [
            { text: '工具 / 管理 (tools)', link: '/modules/tools' },
            { text: '表情 (emoji)', link: '/modules/emoji' },
            { text: '频道锁定 (lock)', link: '/modules/lock' },
            { text: '语音频道 (voice)', link: '/modules/voice' },
          ],
        },
        {
          text: '事件 / 服务模块',
          items: [
            { text: '自动管理 (manage)', link: '/modules/manage' },
            { text: '反垃圾 (antispam)', link: '/modules/antispam' },
            { text: '审计日志 (audit)', link: '/modules/audit' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/wyf9/wyf9s-discord-bot' },
    ],

    editLink: {
      pattern:
        'https://github.com/wyf9/wyf9s-discord-bot/edit/main/docs/:path',
      text: '在 GitHub 上编辑此页',
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    outline: {
      label: '本页目录',
      level: [2, 3],
    },

    lastUpdated: {
      text: '最后更新于',
      formatOptions: { dateStyle: 'short', timeStyle: 'short' },
    },

    footer: {
      message: '基于 MIT 许可发布',
      copyright: 'Copyright © 2025 wyf9',
    },

    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            noResultsText: '无法找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: {
              selectText: '选择',
              navigateText: '切换',
              closeText: '关闭',
            },
          },
        },
      },
    },

    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '菜单',
    returnToTopLabel: '返回顶部',
    langMenuLabel: '切换语言',
  },
})
